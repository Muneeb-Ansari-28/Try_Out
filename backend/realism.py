"""
backend/realism.py

Lighting matching, soft-edge feathering, and contact shadows [UPGRADE 4].
Transforms flat pasted garment overlays into realistic AR-blended clothing:
1. Erodes alpha borders and feathers with Gaussian blur to kill jagged edges.
2. Extracts low-frequency ambient lighting from the user's torso region in LAB space.
3. Computes contact shadows under garment borders.
"""

from __future__ import annotations

import cv2
import numpy as np


def relight_and_soften(
    frame: np.ndarray,
    warped_garment: np.ndarray,
    torso_region_mask: np.ndarray,
) -> np.ndarray:
    """
    [UPGRADE 4] Blends warped garment with:
    1. Gaussian-eroded soft borders (kills the cardboard cut-out edge).
    2. Torso LAB lighting estimation (garment brightness matches room).
    3. Soft contact shadow under garment hem and edges.
    """
    rgb = warped_garment[..., :3].astype(np.float32)
    alpha = warped_garment[..., 3].astype(np.float32) / 255.0

    if float(alpha.max()) == 0.0:
        return frame

    # 1. Soft, slightly eroded edge
    kernel = np.ones((3, 3), np.uint8)
    eroded_alpha = cv2.erode(alpha, kernel, iterations=1)
    soft_alpha = cv2.GaussianBlur(eroded_alpha, (0, 0), 1.5)

    # 2. Scene lighting estimation in LAB color space
    lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel = lab_frame[..., 0].astype(np.float32)

    torso_pixels = torso_region_mask > 0
    mean_lighting = float(l_channel[torso_pixels].mean()) if torso_pixels.any() else 128.0

    # Low-frequency lighting variations across torso (large blur removes shirt patterns)
    lighting_shade = cv2.GaussianBlur(l_channel, (0, 0), 25) / max(mean_lighting, 1.0)
    lighting_shade = np.clip(lighting_shade, 0.75, 1.25)
    global_gain = np.clip(mean_lighting / 128.0, 0.8, 1.2)

    # Apply lighting to garment
    lit_rgb = np.clip(rgb * lighting_shade[..., None] * global_gain, 0.0, 255.0)

    # 3. Soft contact shadow behind garment edge
    shadow = cv2.GaussianBlur(soft_alpha, (0, 0), 12) * 0.22
    base_frame = frame.astype(np.float32) * (1.0 - shadow[..., None])

    # Final composite
    composed = base_frame * (1.0 - soft_alpha[..., None]) + lit_rgb * soft_alpha[..., None]
    return np.clip(composed, 0.0, 255.0).astype(np.uint8)

