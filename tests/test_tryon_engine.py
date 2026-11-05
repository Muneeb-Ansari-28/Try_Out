"""
tests/test_tryon_engine.py

Unit tests for TryOnEngine homography warping, alpha blending,
landmark smoothing, and garment management.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tryon_engine import TryOnEngine


class MockLandmark:
    def __init__(self, x: float, y: float, visibility: float = 0.9):
        self.x = x
        self.y = y
        self.visibility = visibility


class MockPoseLandmarks:
    def __init__(self):
        # 33 landmarks default in MediaPipe
        self.landmark = [MockLandmark(0.5, 0.5, 0.9) for _ in range(33)]
        # Left shoulder (11), Right shoulder (12)
        self.landmark[11] = MockLandmark(0.4, 0.3, 0.95)
        self.landmark[12] = MockLandmark(0.6, 0.3, 0.95)
        # Left hip (23), Right hip (24)
        self.landmark[23] = MockLandmark(0.42, 0.7, 0.95)
        self.landmark[24] = MockLandmark(0.58, 0.7, 0.95)


def test_garment_loading_and_selection(tmp_path: Path):
    garment_dir = tmp_path / "garments"
    garment_dir.mkdir()

    # Create dummy 4-channel BGRA garment PNG
    import cv2
    dummy_img = np.zeros((100, 100, 4), dtype=np.uint8)
    dummy_img[:, :, 2] = 255  # Red channel
    dummy_img[:, :, 3] = 255  # Alpha channel
    cv2.imwrite(str(garment_dir / "test_shirt.png"), dummy_img)

    engine = TryOnEngine(garment_dir=garment_dir)
    assert "test_shirt" in engine.garments
    assert engine.current_garment_id == "test_shirt"

    # Test thread-safe garment selection
    assert engine.set_garment("test_shirt") is True
    assert engine.set_garment("non_existent") is False
    assert engine.current_garment_id == "test_shirt"

    engine.clear_garment()
    assert engine.current_garment_id is None


def test_landmark_extraction_and_smoothing(tmp_path: Path):
    engine = TryOnEngine(garment_dir=tmp_path)
    mock_lm = MockPoseLandmarks()

    pts = engine._get_body_points(mock_lm, frame_w=640, frame_h=480)
    assert pts is not None
    assert "ls" in pts and "rs" in pts and "lh" in pts and "rh" in pts
    assert np.isclose(pts["ls"][0], 0.4 * 640)
    assert np.isclose(pts["ls"][1], 0.3 * 480)

    # Test smoothing on subsequent frame
    mock_lm.landmark[11] = MockLandmark(0.42, 0.32, 0.95)
    pts_smoothed = engine._get_body_points(mock_lm, frame_w=640, frame_h=480)
    assert pts_smoothed is not None
    # Value should be blended between previous (0.4) and current (0.42)
    expected_x = engine.smoothing_alpha * (0.42 * 640) + (1.0 - engine.smoothing_alpha) * (0.4 * 640)
    assert np.isclose(pts_smoothed["ls"][0], expected_x, atol=1e-3)


def test_warp_and_blend(tmp_path: Path):
    engine = TryOnEngine(garment_dir=tmp_path)

    # Create dummy garment with alpha
    garment = np.zeros((200, 200, 4), dtype=np.uint8)
    garment[:, :, :3] = 120
    garment[:, :, 3] = 255  # fully opaque

    pts = {
        "ls": np.array([200.0, 150.0], dtype=np.float32),
        "rs": np.array([440.0, 150.0], dtype=np.float32),
        "lh": np.array([220.0, 380.0], dtype=np.float32),
        "rh": np.array([420.0, 380.0], dtype=np.float32),
    }

    warped = engine._warp_garment(garment, pts, frame_h=480, frame_w=640)
    assert warped is not None
    assert warped.shape == (480, 640, 4)

    # Test alpha blending onto background frame
    bg_frame = np.ones((480, 640, 3), dtype=np.uint8) * 200
    blended = engine._blend(bg_frame, warped)

    assert blended.shape == (480, 640, 3)
    assert blended.dtype == np.uint8
    # Center pixel where garment was placed should no longer be 200
    center_val = blended[250, 320]
    assert not np.array_equal(center_val, [200, 200, 200])

