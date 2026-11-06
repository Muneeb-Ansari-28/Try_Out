"""
backend/ai_tryon.py

Photorealistic Virtual Try-On Service using IDM-VTON (CVPR 2024 / Hugging Face).
Connects to official public GPU clusters via gradio_client with zero API keys required.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
from gradio_client import Client, handle_file

logger = logging.getLogger("AITryOn")

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "backend" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = ROOT / "backend" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job registry: job_id -> dict
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()

# Global lazy-initialized Gradio client
_client: Client | None = None
_client_lock = threading.Lock()


def get_client() -> Client:
    """Lazy-initialize the IDM-VTON Gradio client."""
    global _client
    with _client_lock:
        if _client is None:
            logger.info("Initializing Hugging Face IDM-VTON client (yisol/IDM-VTON)...")
            _client = Client("yisol/IDM-VTON")
            logger.info("Connected to IDM-VTON successfully.")
        return _client


def find_garment_file(garment_id: str) -> Path | None:
    """Find the best garment image file (prefer raw photo, fall back to processed PNG)."""
    raw_dir = ROOT / "garments" / "raw"
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        p = raw_dir / f"{garment_id}{ext}"
        if p.exists():
            return p

    proc_dir = ROOT / "garments" / "processed"
    proc_png = proc_dir / f"{garment_id}.png"
    if proc_png.exists():
        return proc_png

    return None


def _run_tryon_worker(job_id: str, person_img_path: str, garment_path: str, garment_name: str) -> None:
    """Background worker that calls IDM-VTON and updates JOBS."""
    t0 = time.time()
    try:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["progress"] = "Submitting to AI neural try-on cluster..."

        client = get_client()

        with JOBS_LOCK:
            JOBS[job_id]["progress"] = "Generating photorealistic garment fit..."

        result = client.predict(
            dict={
                "background": handle_file(person_img_path),
                "layers": [],
                "composite": None,
            },
            garm_img=handle_file(garment_path),
            garment_des=garment_name,
            is_checked=True,       # Auto-masking enabled (detects human pose and clothes)
            is_checked_crop=False, # Keep natural full framing
            denoise_steps=24,      # Optimal balance of speed and sharp fabric details
            seed=42,
            api_name="/tryon",
        )

        output_path = result[0] if isinstance(result, (list, tuple)) else result
        dest_filename = f"{job_id}.png"
        dest_path = RESULTS_DIR / dest_filename
        shutil.copy(output_path, dest_path)

        elapsed = round(time.time() - t0, 2)
        logger.info(f"Job {job_id} completed in {elapsed}s: saved to {dest_path}")

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["result_url"] = f"/results/{dest_filename}"
            JOBS[job_id]["elapsed_s"] = elapsed
            JOBS[job_id]["progress"] = "Completed!"

    except Exception as exc:
        logger.exception(f"Job {job_id} failed")
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(exc)
            JOBS[job_id]["progress"] = "Generation failed. Please try again."

    finally:
        # Clean up temporary captured person image
        try:
            if os.path.exists(person_img_path):
                os.remove(person_img_path)
        except OSError:
            pass


def start_ai_tryon(frame_bgr, garment_id: str, garment_name: str | None = None) -> str:
    """
    Initiates an asynchronous AI Virtual Try-On job.
    Returns the job_id immediately so the caller can poll status.
    """
    job_id = str(uuid.uuid4())[:8]

    # Save current frame to temporary file
    temp_person_file = TEMP_DIR / f"person_{job_id}.jpg"
    cv2.imwrite(str(temp_person_file), frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

    # Find garment image
    garment_file = find_garment_file(garment_id)
    if garment_file is None:
        raise FileNotFoundError(f"Garment '{garment_id}' image file not found")

    display_name = garment_name or garment_id.replace("_", " ")

    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "garment_id": garment_id,
            "garment_name": display_name,
            "progress": "Queued for processing...",
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_tryon_worker,
        args=(job_id, str(temp_person_file), str(garment_file), display_name),
        daemon=True,
    )
    thread.start()

    return job_id


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Retrieve the current state of a try-on job."""
    with JOBS_LOCK:
        return JOBS.get(job_id)
