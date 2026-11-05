"""
scripts/test_local.py

Interactive & automated test harness for Day 1:
1. Validates MediaPipe Pose detection.
2. Validates TPS homography garment warping.
3. Supports live webcam feed (press 'n' to cycle garments, 'q' to quit).
4. Supports headless/image mode to verify without an interactive GUI.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
import time

import cv2
import numpy as np

# Ensure backend is on python search path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tryon_engine import TryOnEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestLocal")


def create_synthetic_person_image() -> np.ndarray:
    """Generate a synthetic person frame for headless/automated testing."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 230  # Light studio background

    # Head / Face
    cv2.circle(frame, (320, 100), 45, (190, 175, 160), -1)
    # Neck
    cv2.rectangle(frame, (310, 140), (330, 170), (180, 165, 150), -1)
    # Torso
    pts_body = np.array([
        [240, 170],  # Left shoulder (MediaPipe right shoulder from viewer)
        [400, 170],  # Right shoulder
        [370, 360],  # Right hip
        [270, 360],  # Left hip
    ], dtype=np.int32)
    cv2.fillPoly(frame, [pts_body], (210, 200, 195))

    # Arms
    cv2.line(frame, (240, 170), (210, 300), (190, 175, 160), 22)
    cv2.line(frame, (400, 170), (430, 300), (190, 175, 160), 22)

    # Legs
    cv2.line(frame, (285, 360), (280, 480), (60, 60, 70), 24)
    cv2.line(frame, (355, 360), (360, 480), (60, 60, 70), 24)

    return frame


def run_headless_verification(engine: TryOnEngine, out_path: str = "test_output.jpg") -> bool:
    """Run non-interactive verification test to ensure pipeline succeeds."""
    logger.info("Running headless automated pipeline test...")

    garment_ids = list(engine.garments.keys())
    if not garment_ids:
        logger.error("No garments loaded in TryOnEngine!")
        return False

    active_id = garment_ids[0]
    engine.set_garment(active_id)
    logger.info(f"Set active garment for headless test: {active_id}")

    test_frame = create_synthetic_person_image()
    start_t = time.perf_counter()
    result_frame = engine.process_frame(test_frame)
    duration_ms = (time.perf_counter() - start_t) * 1000

    logger.info(f"Processed test frame in {duration_ms:.2f}ms")
    cv2.imwrite(out_path, result_frame)
    logger.info(f"Headless test frame saved to {out_path}")
    return True


def run_interactive_webcam(engine: TryOnEngine, camera_id: int = 0) -> None:
    """Run interactive webcam window."""
    garment_ids = list(engine.garments.keys())
    if not garment_ids:
        logger.error("No garments found in garments/processed!")
        return

    logger.info(f"Loaded garments ({len(garment_ids)}): {garment_ids}")
    cur_idx = 0
    engine.set_garment(garment_ids[cur_idx])

    logger.info(f"Opening webcam device {camera_id}...")
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        logger.warning("Default DirectShow capture failed, trying standard backend...")
        cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        logger.error(f"Could not open webcam index {camera_id}. Running headless verification instead.")
        run_headless_verification(engine)
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    logger.info("=" * 50)
    logger.info("Webcam started! Controls:")
    logger.info("  [N]   - Cycle to next garment")
    logger.info("  [1-9] - Directly pick garment index")
    logger.info("  [C]   - Clear active garment")
    logger.info("  [Q]   - Quit")
    logger.info("=" * 50)

    fps_history = []
    t_prev = time.perf_counter()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to grab camera frame")
                time.sleep(0.03)
                continue

            # Mirror frame for natural webcam selfie experience
            frame = cv2.flip(frame, 1)

            # Process try-on
            processed = engine.process_frame(frame)

            # Calculate FPS
            t_now = time.perf_counter()
            fps = 1.0 / max(1e-5, t_now - t_prev)
            t_prev = t_now
            fps_history.append(fps)
            if len(fps_history) > 30:
                fps_history.pop(0)
            avg_fps = sum(fps_history) / len(fps_history)

            # Draw HUD
            hud_text = f"Garment: {garment_ids[cur_idx] if engine.current_garment_id else 'None'} | {avg_fps:.1f} FPS"
            cv2.putText(processed, hud_text, (20, processed.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(processed, "[N] Next | [Q] Quit", (20, processed.shape[0] - 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow("VTON Live Try-On (Day 1)", processed)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # ESC or Q
                break
            elif key == ord("n"):
                cur_idx = (cur_idx + 1) % len(garment_ids)
                engine.set_garment(garment_ids[cur_idx])
            elif key == ord("c"):
                engine.clear_garment()
            elif ord("1") <= key <= ord("9"):
                target = key - ord("1")
                if target < len(garment_ids):
                    cur_idx = target
                    engine.set_garment(garment_ids[cur_idx])
    finally:
        cap.release()
        cv2.destroyAllWindows()
        logger.info("Webcam test ended cleanly.")


def run_static_image_test(engine: TryOnEngine, img_path: str, out_path: str = "test_image_tryon.jpg") -> bool:
    """Test try-on on a static photo of a person."""
    img = cv2.imread(img_path)
    if img is None:
        logger.error(f"Could not load image: {img_path}")
        return False

    garment_ids = list(engine.garments.keys())
    if not garment_ids:
        logger.error("No garments loaded!")
        return False

    active_id = engine.current_garment_id or garment_ids[0]
    engine.set_garment(active_id)
    logger.info(f"Applying active garment '{active_id}' to {img_path}...")

    t0 = time.perf_counter()
    out = engine.process_frame(img)
    duration_ms = (time.perf_counter() - t0) * 1000

    cv2.imwrite(out_path, out)
    logger.info(f"Processed image in {duration_ms:.2f}ms. Output saved to: {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test local VTON engine")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default 0)")
    parser.add_argument("--image", type=str, default=None, help="Path to static person photo to test")
    parser.add_argument("--garment", type=str, default=None, help="Garment ID to apply")
    parser.add_argument("--headless", action="store_true", help="Run in headless verification mode")
    parser.add_argument("--garments-dir", type=str, default="garments/processed")
    args = parser.parse_args()

    engine = TryOnEngine(args.garments_dir)
    if args.garment:
        engine.set_garment(args.garment)

    if args.image:
        success = run_static_image_test(engine, args.image)
        sys.exit(0 if success else 1)
    elif args.headless:
        success = run_headless_verification(engine)
        sys.exit(0 if success else 1)
    else:
        run_interactive_webcam(engine, camera_id=args.camera)


if __name__ == "__main__":
    main()

