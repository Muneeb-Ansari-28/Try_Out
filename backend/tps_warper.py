"""
backend/tps_warper.py

Non-rigid thin-plate spline warping engine [UPGRADE 3, PATCH P3].
Uses scipy RBFInterpolator on a coarse 24x24 grid, upsampled to full resolution
for real-time CPU performance (30+ FPS) while permitting organic cloth deformation.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.interpolate import RBFInterpolator

TPS_KEYS = ["ls", "rs", "neck", "waist_l", "waist_r", "lh", "rh", "hem_mid"]


def tps_warp(
    garment_bgra: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
    out_w: int,
    out_h: int,
    grid_size: int = 24,
) -> np.ndarray:
    """
    [UPGRADE 3] Non-rigid thin-plate spline warping using RBFInterpolator.
    src_pts: (N, 2) control points in garment coordinates
    dst_pts: (N, 2) matching target coordinates on the body frame
    """
    if len(src_pts) < 4 or len(dst_pts) < 4:
        return np.zeros((out_h, out_w, 4), dtype=np.uint8)

    # Backward mapping: frame (dst) -> garment (src)
    interp = RBFInterpolator(
        np.asarray(dst_pts, np.float64),
        np.asarray(src_pts, np.float64),
        kernel="thin_plate_spline",
        smoothing=1e-3,  # Slight smoothing prevents extreme fold singularities
    )

    # Evaluate on coarse grid for real-time speed
    gx, gy = np.meshgrid(
        np.linspace(0, out_w - 1, grid_size),
        np.linspace(0, out_h - 1, grid_size),
    )
    grid_coords = np.stack([gx.ravel(), gy.ravel()], axis=1)

    coarse_map = interp(grid_coords).reshape(grid_size, grid_size, 2).astype(np.float32)

    # Upsample map to full frame resolution
    full_map = cv2.resize(coarse_map, (out_w, out_h), interpolation=cv2.INTER_LINEAR)

    # Remap garment pixels
    warped = cv2.remap(
        garment_bgra,
        full_map[..., 0],
        full_map[..., 1],
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return warped


def compute_tps_anchors(
    pts: dict,
    anchors8: dict | None,
    gw: int,
    gh: int,
) -> tuple[np.ndarray, np.ndarray] | None:
    """
    [PATCH P3] Computes matched 8-point (src, dst) control sets.
    Returns (src, dst) or None if anchors8 is missing.
    """
    if not anchors8 or any(k not in anchors8 for k in TPS_KEYS):
        return None

    src = np.float32([[anchors8[k][0] * gw, anchors8[k][1] * gh] for k in TPS_KEYS])

    ls, rs = pts["ls"], pts["rs"]
    lh, rh = pts["lh"], pts["rh"]
    sh_dist = float(np.linalg.norm(rs - ls))
    neck = (ls + rs) / 2.0 - np.array([0.0, sh_dist * 0.08], dtype=np.float32)
    hem_mid = (lh + rh) / 2.0
    waist_l = (ls + lh) / 2.0
    waist_r = (rs + rh) / 2.0

    dst = np.float32([ls, rs, neck, waist_l, waist_r, lh, rh, hem_mid])
    return src, dst

