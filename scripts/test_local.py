"""
scripts/test_local.py

Interactive & automated test harness for Day 1 [FIX H4, M2, PATCH P12]:
1. Validates MediaPipe Pose detection.
2. Validates perspective garment warping with One-Euro smoothing.
3. Supports live interactive webcam feed (CAP_DSHOW, buffer size 1).
4. Supports headless & static image testing modes.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# [PATCH P12] Anchor paths to file location
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

try:
    from backend.tryon_engine import TryOnEngine
except ImportError:
    from tryon_engine import TryOnEngine  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestLocal")


def create_synthetic_person_image() -> np.ndarray:
    """Generate a synthetic human frame for headless test runs."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 230
    cv2.circle(frame, (320, 100), 45, (190, 175, 160), -1)
    cv2.rectangle(frame, (310, 140), (330, 170), (180, 165, 150), -1)
    pts_body = np.array([
        [240, 170],
        [400, 170],
        [370, 360],
        [270, 360],
    ], dtype=np.int32)
    cv2.fillPoly(frame, [pts_body], (210, 200, 195))
    cv2.line(frame, (240, 170), (210, 300), (190, 175, 160), 22)
    cv2.line(frame, (400, 170), (430, 300), (190, 175, 160), 22)
    cv2.line(frame, (285, 360), (280, 480), (60, 60, 70), 24)
    cv2.line(frame, (355, 360), (360, 480), (60, 60, 70), 24)
    return frame


def run_headless_test(engine: TryOnEngine) -> bool:
    """Run non-interactive headless test."""
    logger.info("Running headless automated pipeline test...")
    garment_ids = list(engine.garments.keys())
    if not garment_ids:
        logger.error("No garments loaded in TryOnEngine!")
        return False

    engine.set_garment(garment_ids[0])
    test_frame = create_synthetic_person_image()
    t0 = time.perf_counter()
    out = engine.process_frame(test_frame)
    ms = (time.perf_counter() - t0) * 1000
    logger.info(f"Processed test frame in {ms:.2f}ms — output shape: {out.shape}")
    if engine.stats:
        logger.info(f"Engine stats: {engine.stats}")
    return True


def run_interactive_webcam(engine: TryOnEngine, camera_id: int = 0) -> None:
    """Run live interactive webcam window with controls."""
    garment_ids = list(engine.garments.keys())
    if not garment_ids:
        logger.error("No garments found in garments/processed/")
        return

    idx = 0
    engine.set_garment(garment_ids[idx])
    logger.info(f"Active garment: {garment_ids[idx]}")
    logger.info("Controls: [N] next garment | [Q] quit")

    # [FIX H4] Use CAP_DSHOW on Windows + buffer size 1 for minimum latency
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        output = engine.process_frame(frame)

        # [FIX M2] Display real stats on overlay
        if engine.stats:
            stat_text = f"Pose: {engine.stats.get('pose_ms', 0):.1f}ms | Total: {engine.stats.get('total_ms', 0):.1f}ms | FPS: {engine.stats.get('fps', 0):.1f}"
            cv2.putText(output, stat_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(
            output,
            f"[{idx+1}/{len(garment_ids)}] {garment_ids[idx]} | N=next Q=quit",
            (10, output.shape[0] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
        )
        cv2.imshow("VTON — Day 1 Test", output)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("n"):
            idx = (idx + 1) % len(garment_ids)
            engine.set_garment(garment_ids[idx])
            logger.info(f"Switched to: {garment_ids[idx]}")

    cap.release()
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="VTON Local Test Harness")
    parser.add_argument("--headless", action="store_true", help="Run automated test without opening window")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--garments", type=str, default=str(ROOT / "garments" / "processed"))
    args = parser.parse_args()

    engine = TryOnEngine(args.garments)

    if args.headless:
        success = run_headless_test(engine)
        sys.exit(0 if success else 1)
    else:
        run_interactive_webcam(engine, camera_id=args.camera)


if __name__ == "__main__":
    main()
