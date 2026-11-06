"""
tests/test_tryon_engine.py

Unit tests for TryOnEngine conforming to VTON_IMPLEMENTATION_PLAN-2-FIXED.md:
- Garment loading and thread-safe selection
- X-coordinate landmark pair sorting [FIX H1]
- Hip extrapolation from shoulders [FIX H2]
- One-Euro temporal filtering and reset [FIX H5, PATCH P15]
- Perspective warping with per-garment anchors [FIX C5, H3]
- Alpha blending fallback
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from backend.tryon_engine import OneEuro, TryOnEngine
except ImportError:
    from tryon_engine import OneEuro, TryOnEngine  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]


class MockLandmark:
    def __init__(self, x: float, y: float, visibility: float = 0.9):
        self.x = x
        self.y = y
        self.visibility = visibility


class MockPoseLandmarks:
    def __init__(self, ls_x: float = 0.4, rs_x: float = 0.6, hips_visible: bool = True):
        self.landmark = [MockLandmark(0.5, 0.5, 0.9) for _ in range(33)]
        # Left shoulder (11), Right shoulder (12)
        self.landmark[11] = MockLandmark(ls_x, 0.3, 0.95)
        self.landmark[12] = MockLandmark(rs_x, 0.3, 0.95)
        # Left hip (23), Right hip (24)
        hip_vis = 0.95 if hips_visible else 0.1
        self.landmark[23] = MockLandmark(0.42, 0.7, hip_vis)
        self.landmark[24] = MockLandmark(0.58, 0.7, hip_vis)
        # Elbows (13, 14) and Wrists (15, 16)
        self.landmark[13] = MockLandmark(0.35, 0.45, 0.9)
        self.landmark[14] = MockLandmark(0.65, 0.45, 0.9)
        self.landmark[15] = MockLandmark(0.32, 0.6, 0.9)
        self.landmark[16] = MockLandmark(0.68, 0.6, 0.9)


def test_garment_loading_and_anchors(tmp_path: Path):
    garment_dir = tmp_path / "garments"
    garment_dir.mkdir()
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()

    # Create dummy garment
    dummy_img = np.zeros((100, 100, 4), dtype=np.uint8)
    dummy_img[:, :, :3] = 200
    dummy_img[:, :, 3] = 255
    cv2.imwrite(str(garment_dir / "hoodie.png"), dummy_img)

    # Create dummy catalog with anchors
    catalog_path = backend_dir / "garments.json"
    catalog_data = [
        {
            "id": "hoodie",
            "name": "Hoodie",
            "file": "hoodie.png",
            "anchors": {
                "ls": [0.2, 0.05],
                "rs": [0.8, 0.05],
                "lh": [0.18, 0.95],
                "rh": [0.82, 0.95],
            },
        }
    ]
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")

    engine = TryOnEngine(garment_dir=garment_dir, catalog_path=catalog_path)
    assert "hoodie" in engine.garments
    assert engine.current_garment_id == "hoodie"
    assert "hoodie" in engine.garment_anchors
    assert engine.garment_anchors["hoodie"]["ls"] == [0.2, 0.05]

    # Test thread-safe garment selection
    assert engine.set_garment("hoodie") is True
    assert engine.set_garment("invalid") is False
    engine.clear_garment()
    assert engine.current_garment_id is None


def test_x_coordinate_sorting_and_hip_extrapolation():
    engine = TryOnEngine(garment_dir=Path("garments/processed"))

    # Case 1: Normal orientation (ls_x < rs_x)
    lm_normal = MockPoseLandmarks(ls_x=0.4, rs_x=0.6, hips_visible=True)
    pts1 = engine._get_body_points(lm_normal, frame_w=640, frame_h=480)
    assert pts1 is not None
    assert pts1["ls"][0] < pts1["rs"][0]

    # Case 2: Swapped / mirrored orientation (ls_x > rs_x) [FIX H1]
    lm_swapped = MockPoseLandmarks(ls_x=0.6, rs_x=0.4, hips_visible=True)
    pts2 = engine._get_body_points(lm_swapped, frame_w=640, frame_h=480)
    assert pts2 is not None
    # Must still be sorted left-to-right on screen
    assert pts2["ls"][0] < pts2["rs"][0]

    # Case 3: Hips occluded / below frame [FIX H2]
    lm_no_hips = MockPoseLandmarks(ls_x=0.4, rs_x=0.6, hips_visible=False)
    pts3 = engine._get_body_points(lm_no_hips, frame_w=640, frame_h=480)
    assert pts3 is not None
    assert "lh" in pts3 and "rh" in pts3
    # Extrapolated hips should be below shoulders
    assert pts3["lh"][1] > pts3["ls"][1]
    assert pts3["rh"][1] > pts3["rs"][1]


def test_one_euro_filter():
    euro = OneEuro(min_cutoff=1.5, beta=0.02)
    p0 = np.array([[100.0, 100.0]], dtype=np.float32)
    t0 = 1.0

    # Initial call
    out0 = euro(p0, t0)
    assert np.allclose(out0, p0)

    # Next call with small movement (should be smoothed)
    p1 = np.array([[102.0, 101.0]], dtype=np.float32)
    t1 = t0 + 0.033
    out1 = euro(p1, t1)
    # Output should be between p0 and p1
    assert p0[0, 0] <= out1[0, 0] <= p1[0, 0]

    # Test reset
    euro.reset()
    assert euro.x is None
    assert euro.t is None


def test_warp_and_blend(tmp_path: Path):
    engine = TryOnEngine(garment_dir=tmp_path)

    # Create dummy garment with alpha
    garment = np.zeros((100, 100, 4), dtype=np.uint8)
    garment[:, :, :3] = 120
    garment[:, :, 3] = 255

    pts = {
        "ls": np.array([200.0, 150.0], dtype=np.float32),
        "rs": np.array([440.0, 150.0], dtype=np.float32),
        "lh": np.array([220.0, 380.0], dtype=np.float32),
        "rh": np.array([420.0, 380.0], dtype=np.float32),
    }

    warped = engine._warp_garment(garment, "test_item", pts, frame_h=480, frame_w=640)
    assert warped is not None
    assert warped.shape == (480, 640, 4)

    # Alpha blending onto background frame
    bg_frame = np.ones((480, 640, 3), dtype=np.uint8) * 200
    blended = engine._blend(bg_frame, warped)

    assert blended.shape == (480, 640, 3)
    assert blended.dtype == np.uint8
    center_val = blended[250, 320]
    assert not np.array_equal(center_val, [200, 200, 200])
