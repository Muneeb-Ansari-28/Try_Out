"""
backend/tryon_engine.py

Real-time virtual try-on engine using MediaPipe pose detection and perspective homography warping.
Tuned for high-framerate real-time performance on consumer hardware (NVIDIA T550 / CPU).
Supports both full-body and desk/torso-only webcam viewpoints with aspect-ratio preserving scaling.
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading
from typing import Dict, Optional

import cv2
import mediapipe as mp
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TryOnEngine")


class TryOnEngine:
    """
    Live virtual try-on engine.
    Extracts pose landmarks with MediaPipe and warps clothing garments onto the user's torso.
    """

    def __init__(
        self,
        garment_dir: str | Path = "garments/processed",
        smoothing_alpha: float = 0.65,
    ) -> None:
        self.garment_dir = Path(garment_dir)
        self.garments: Dict[str, np.ndarray] = {}
        self.current_garment_id: Optional[str] = None
        self._lock = threading.Lock()

        # Smoothing parameter: 0.0 = no smoothing, 1.0 = heavy smoothing
        self.smoothing_alpha = smoothing_alpha
        self._prev_pts: Optional[Dict[str, np.ndarray]] = None

        # MediaPipe Pose setup (model_complexity=0 is Lite = fastest for live video)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.load_garments()
        logger.info(f"TryOnEngine initialized with {len(self.garments)} garments.")

    def load_garments(self) -> int:
        """Scan garment_dir and load all transparent PNGs into memory."""
        count = 0
        if not self.garment_dir.exists():
            self.garment_dir.mkdir(parents=True, exist_ok=True)
            return 0

        for path in self.garment_dir.glob("*.png"):
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is not None:
                # Ensure 4 channels (BGRA)
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                elif img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

                self.garments[path.stem] = img
                count += 1
                logger.debug(f"Loaded garment: {path.stem} {img.shape}")

        if count > 0 and self.current_garment_id is None:
            self.current_garment_id = next(iter(self.garments.keys()))

        return count

    def set_garment(self, garment_id: str) -> bool:
        """Thread-safe active garment switch."""
        with self._lock:
            if garment_id in self.garments:
                self.current_garment_id = garment_id
                self._prev_pts = None  # Reset temporal smoother on garment change
                logger.info(f"Active garment switched to: {garment_id}")
                return True
            logger.warning(f"Garment not found: {garment_id}")
            return False

    def clear_garment(self) -> None:
        """Remove active garment overlay."""
        with self._lock:
            self.current_garment_id = None
            self._prev_pts = None

    def _get_body_points(self, landmarks, frame_w: int, frame_h: int) -> Optional[Dict[str, np.ndarray]]:
        """
        Extract key torso landmarks with visibility validation.
        Gracefully extrapolates hips if the user is sitting at a desk or framed upper-body only.
        """
        lm = landmarks.landmark

        def extract_pt(idx: int) -> Optional[np.ndarray]:
            p = lm[idx]
            if p.visibility < 0.35:
                return None
            return np.array([p.x * frame_w, p.y * frame_h], dtype=np.float32)

        ls = extract_pt(11)  # Left shoulder (viewer right)
        rs = extract_pt(12)  # Right shoulder (viewer left)
        lh = extract_pt(23)  # Left hip
        rh = extract_pt(24)  # Right hip

        # Shoulders are strictly required
        if ls is None or rs is None:
            return None

        shoulder_width = float(np.linalg.norm(rs - ls))
        if shoulder_width < 25.0:
            return None

        # Torso downward vector (perpendicular to shoulder span)
        dx = rs[0] - ls[0]
        dy = rs[1] - ls[1]
        perp_down = np.array([-dy, dx], dtype=np.float32)
        norm = np.linalg.norm(perp_down)
        if norm > 1e-4:
            perp_down /= norm
        else:
            perp_down = np.array([0.0, 1.0], dtype=np.float32)

        # Smart extrapolation if hips are below frame boundary (sitting/portrait mode)
        torso_height_est = shoulder_width * 1.35
        if lh is None:
            lh = ls + perp_down * torso_height_est
        if rh is None:
            rh = rs + perp_down * torso_height_est

        current_pts = {"ls": ls, "rs": rs, "lh": lh, "rh": rh}

        # Apply exponential moving average (EMA) smoothing across frames
        if self._prev_pts is not None:
            smoothed = {}
            for k, cur in current_pts.items():
                prev = self._prev_pts[k]
                smoothed[k] = self.smoothing_alpha * cur + (1.0 - self.smoothing_alpha) * prev
            self._prev_pts = smoothed
            return smoothed
        else:
            self._prev_pts = current_pts
            return current_pts

    def _warp_garment(
        self,
        garment: np.ndarray,
        pts: Dict[str, np.ndarray],
        frame_h: int,
        frame_w: int,
    ) -> Optional[np.ndarray]:
        """
        Warp garment image to fit the detected torso geometry using homography.
        Adds ergonomic margin around shoulders and hips for natural drape.
        """
        gh, gw = garment.shape[:2]

        shoulder_width = float(np.linalg.norm(pts["rs"] - pts["ls"]))
        torso_height = float(np.linalg.norm(pts["lh"] - pts["ls"]))

        if shoulder_width < 20 or torso_height < 30:
            return None

        # Margins to account for garment collar, sleeves, and hemline
        pad_x = shoulder_width * 0.18
        pad_y_top = torso_height * 0.14
        pad_y_bot = torso_height * 0.08

        # Target destinations on camera frame
        ls = pts["ls"] + np.array([-pad_x, -pad_y_top], dtype=np.float32)
        rs = pts["rs"] + np.array([pad_x, -pad_y_top], dtype=np.float32)
        lh = pts["lh"] + np.array([-pad_x * 0.7, pad_y_bot], dtype=np.float32)
        rh = pts["rh"] + np.array([pad_x * 0.7, pad_y_bot], dtype=np.float32)

        # Source coordinates on garment PNG (assuming centered top)
        src = np.float32([
            [gw * 0.15, gh * 0.03],  # Left shoulder anchor
            [gw * 0.85, gh * 0.03],  # Right shoulder anchor
            [gw * 0.10, gh * 0.97],  # Left hip/hem anchor
            [gw * 0.90, gh * 0.97],  # Right hip/hem anchor
        ])
        dst = np.float32([ls, rs, lh, rh])

        homography, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if homography is None:
            return None

        warped = cv2.warpPerspective(
            garment,
            homography,
            (frame_w, frame_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        return warped

    def _blend(self, frame: np.ndarray, warped: np.ndarray) -> np.ndarray:
        """Fast vectorized alpha-blending of warped BGRA garment onto BGR camera frame."""
        if warped is None or warped.shape[2] < 4:
            return frame

        alpha = (warped[:, :, 3:4].astype(np.float32)) / 255.0
        # If no alpha pixels, return original frame quickly
        if not np.any(alpha > 0.01):
            return frame

        warped_rgb = warped[:, :, :3].astype(np.float32)
        bg = frame.astype(np.float32)

        blended = bg * (1.0 - alpha) + warped_rgb * alpha
        return np.clip(blended, 0, 255).astype(np.uint8)

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single video frame:
        1. Aspect-ratio preserving downscale for fast pose detection.
        2. Extract body landmarks.
        3. Warp active garment onto full-resolution frame.
        4. Blend seamlessly.
        """
        with self._lock:
            garment_id = self.current_garment_id

        if garment_id is None:
            return frame

        garment = self.garments.get(garment_id)
        if garment is None:
            return frame

        frame_h, frame_w = frame.shape[:2]

        # Optimization: Aspect-ratio preserving downscale if image is large
        max_dim = max(frame_h, frame_w)
        if max_dim > 480:
            scale = 480.0 / max_dim
            detect_w = int(frame_w * scale)
            detect_h = int(frame_h * scale)
            small_frame = cv2.resize(frame, (detect_w, detect_h))
        else:
            small_frame = frame

        rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_small)

        output = frame.copy()

        if results.pose_landmarks:
            pts = self._get_body_points(results.pose_landmarks, frame_w, frame_h)
            if pts is not None:
                warped = self._warp_garment(garment, pts, frame_h, frame_w)
                output = self._blend(output, warped)
            else:
                self._draw_hint(output, "Adjust position — shoulders needed")
        else:
            self._draw_hint(output, "Stand in frame")

        return output

    def _draw_hint(self, img: np.ndarray, text: str) -> None:
        """Draw a semi-transparent status pill overlay."""
        cv2.putText(
            img,
            text,
            (24, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 165, 255),
            2,
            cv2.LINE_AA,
        )
