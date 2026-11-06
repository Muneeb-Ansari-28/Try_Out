"""
backend/segmentation.py

CPU-friendly multiclass segmentation for occlusion and background handling [UPGRADE 2].
Uses MediaPipe Tasks ImageSegmenter with selfie_multiclass_256x256.tflite.
Categories:
  0: Background
  1: Hair
  2: Body-skin
  3: Face-skin
  4: Clothes
  5: Others
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

logger = logging.getLogger("Segmentation")

MODEL_PATH = Path(__file__).resolve().parent / "models" / "selfie_multiclass_256x256.tflite"


class BodySegmenter:
    """CPU-friendly multiclass segmentation for occlusion and background masks."""

    def __init__(self) -> None:
        self.available = False
        if not MODEL_PATH.exists():
            logger.warning(f"Segmenter model not found at {MODEL_PATH} — occlusion disabled")
            return
        try:
            opts = vision.ImageSegmenterOptions(
                base_options=mp_tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                output_category_mask=True,
            )
            self.segmenter = vision.ImageSegmenter.create_from_options(opts)
            self.available = True
            logger.info("✅ Multiclass Selfie Segmenter initialized")
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Segmenter init error: {e!r}")

    def segment(self, rgb_frame: np.ndarray, timestamp_ms: int) -> np.ndarray | None:
        """Returns (H, W) uint8 category mask."""
        if not self.available:
            return None
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        res = self.segmenter.segment_for_video(mp_img, timestamp_ms)
        return res.category_mask.numpy_view()

    @staticmethod
    def build_occluder_mask(cat_mask: np.ndarray | None, pts: dict, shape: tuple[int, int]) -> np.ndarray:
        """
        Creates binary mask of elements that MUST render IN FRONT of the garment:
        - Face (3) and Hair (1)
        - Forearms/hands (thick capsules between elbows and wrists where person exists)
        """
        h, w = shape
        if cat_mask is None:
            return np.zeros((h, w), dtype=np.uint8)

        # Hair (1) + Face skin (3) always stay in front (chin, neck, hair over collar)
        occ = np.isin(cat_mask, (1, 3)).astype(np.uint8) * 255

        # Forearms and hands: thick capsules between elbow and wrist
        arms = np.zeros((h, w), dtype=np.uint8)
        sh_width = float(np.linalg.norm(pts["rs"] - pts["ls"]))
        thick = max(int(0.18 * sh_width), 8)

        for el_key, wr_key in [("el_l", "wr_l"), ("el_r", "wr_r")]:
            if el_key in pts and wr_key in pts and pts[el_key] is not None and pts[wr_key] is not None:
                p_el = (int(pts[el_key][0]), int(pts[el_key][1]))
                p_wr = (int(pts[wr_key][0]), int(pts[wr_key][1]))
                cv2.line(arms, p_el, p_wr, 255, thick)

        # Only retain arm capsule where BARE SKIN (class 2) exists (hands/wrists crossing torso).
        # Do NOT intersect with clothes (class 4), which would punch holes revealing old shirts.
        arms &= ((cat_mask == 2).astype(np.uint8) * 255)

        return cv2.max(occ, arms)
