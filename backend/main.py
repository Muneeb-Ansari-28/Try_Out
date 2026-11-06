"""
backend/main.py

FastAPI streaming server with MJPEG live feed and garment catalog endpoints.
[FIX C4] Paths anchored to ROOT.
[FIX H7] Async mjpeg_stream with disconnect detection, frame deduplication, and thread stop_event.
[FIX H8] Secure local 127.0.0.1 binding without --reload.
[FIX C2, M2] /api/status exposes real engine stats and backend state.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# [FIX C4] Anchor all paths to the project root
ROOT = Path(__file__).resolve().parent.parent
GARMENT_DIR = ROOT / "garments" / "processed"
CATALOG = ROOT / "backend" / "garments.json"

sys.path.insert(0, str(ROOT / "backend"))
from camera import Camera
from tryon_engine import TryOnEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VTONServer")

# ── State ─────────────────────────────────────────────────────────────
engine: TryOnEngine | None = None
_cam: Camera | None = None
latest_frame: bytes | None = None
frame_id: int = 0  # [FIX H7] Frame counter for deduplication
frame_lock = threading.Lock()
stop_event = threading.Event()  # [FIX H7] Clean shutdown trigger


def camera_loop() -> None:
    """
    [PATCH P5] Capture via the threaded Camera; always process the newest
    frame and drop stale ones instead of queueing up latency.
    """
    global latest_frame, frame_id, _cam
    _cam = Camera(0)
    logger.info("Camera capture loop started with threaded frame-dropping")

    while not stop_event.is_set():
        frame = _cam.read()
        if frame is None:
            time.sleep(0.005)
            continue

        frame = cv2.flip(frame, 1)  # Mirror view

        if engine:
            frame = engine.process_frame(frame)

        # Encode as JPEG (quality 80 = optimal balance of visual fidelity and low bandwidth)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with frame_lock:
            latest_frame = buf.tobytes()
            frame_id += 1  # [FIX H7] Increment frame counter

        time.sleep(0.001)  # Yield CPU

    logger.info("Camera capture loop stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + clean shutdown. [FIX H7, PATCH P5]"""
    global engine
    logger.info("🚀 Starting TryOn Engine...")
    engine = TryOnEngine(str(GARMENT_DIR), str(CATALOG))

    stop_event.clear()
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    yield
    logger.info("🛑 Shutting down server...")
    stop_event.set()  # [FIX H7] Signal camera loop to stop
    await asyncio.sleep(0.1)
    if _cam is not None:
        _cam.release()
    logger.info("✅ Camera released cleanly")


# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(title="VTON Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [FIX C4] Mount static files with absolute path
if not GARMENT_DIR.exists():
    GARMENT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/garments", StaticFiles(directory=GARMENT_DIR), name="garments")

# ── Routes ────────────────────────────────────────────────────────────


async def mjpeg_stream(request: Request):
    """[FIX H7] Async generator: stops on client disconnect and skips duplicate frames."""
    last_sent_id = -1
    while not await request.is_disconnected():
        with frame_lock:
            fid = frame_id
            frame = latest_frame

        if frame is None or fid == last_sent_id:
            await asyncio.sleep(0.005)  # Wait briefly for new frame
            continue

        last_sent_id = fid
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
        )


@app.get("/video-feed")
async def video_feed(request: Request):
    """MJPEG stream endpoint — consumed directly by <img src='...'> in browser."""
    return StreamingResponse(
        mjpeg_stream(request),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


class GarmentSelectRequest(BaseModel):
    garment_id: str


@app.post("/api/select-garment")
async def select_garment(req: GarmentSelectRequest):
    """Switch active garment [FIX C3: uses string slug ID]."""
    if engine is None:
        raise HTTPException(503, "Engine not ready")
    success = engine.set_garment(req.garment_id)
    if not success:
        raise HTTPException(404, f"Garment '{req.garment_id}' not found")
    return {"status": "ok", "active": req.garment_id}


@app.post("/api/clear-garment")
async def clear_garment():
    """Remove active garment overlay."""
    if engine:
        engine.clear_garment()
    return {"status": "cleared"}


@app.get("/api/garments")
async def get_garments():
    """[FIX C4] Return catalog anchored to ROOT, filtered by loaded garments."""
    items = []
    if CATALOG.exists():
        try:
            items = json.loads(CATALOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            items = []

    if engine:
        # Only return garments the engine actually loaded (prevents 404 on select)
        items = [g for g in items if g.get("id") in engine.garments]
        known = {g.get("id") for g in items}
        items += [
            {
                "id": k,
                "name": k.replace("_", " ").title(),
                "file": f"{k}.png",
                "price": 49.99,
                "category": "upper",
                "collection": "default",
            }
            for k in engine.garments
            if k not in known
        ]
    return items


@app.get("/api/status")
async def status():
    """[FIX C2, M2] Expose real backend state and profiler numbers."""
    return {
        "engine_ready": engine is not None,
        "active_garment": engine.current_garment_id if engine else None,
        "garment_count": len(engine.garments) if engine else 0,
        "backend_used": getattr(engine, "backend_used", "warp"),
        "stats": getattr(engine, "stats", {}),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "garments": len(engine.garments) if engine else 0}
