"""
backend/tryon_engine.py

Live virtual try-on engine using MediaPipe Pose + perspective warp.
[FIX H3] Perspective transform (exact 4-point solver).
[FIX H1] X-coordinate sorted shoulder & hip landmarks.
[FIX H2] Smart hip estimation when hips are below frame / low visibility.
[FIX H5] One-Euro temporal filtering with automatic timeout reset.
[FIX C2, M2] Real profiler stats and state logging.
[FIX C5, PATCH P3] Per-garment 4-point and 8-point anchors support.
[PATCH P2, P15] Segmentation occlusion & relighting hooks with graceful fallback.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

# Day 3 & Day 6 modules — lazy imports
try:
    from realism import relight_and_soften  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    from segmentation import BodySegmenter  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except ImportError:
    try:
        from backend.realism import relight_and_soften  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
        from backend.segmentation import BodySegmenter  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    except ImportError:
        relight_and_soften = None
        BodySegmenter = None

try:
    from tps_warper import compute_tps_anchors, tps_warp  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
except ImportError:
    try:
        from backend.tps_warper import compute_tps_anchors, tps_warp  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]
    except ImportError:
        compute_tps_anchors = None
        tps_warp = None


def widen_for_real_clothes(pts: dict, cat_mask: np.ndarray | None) -> dict:
    """[PATCH P4] Expand shoulders/hips symmetrically so the virtual garment
    covers the user's real clothes. No-op when no mask or clothes are narrower."""
    if cat_mask is None:
        return pts
    y0 = int(min(pts["ls"][1], pts["rs"][1]))
    y1 = int(max(pts["lh"][1], pts["rh"][1]))
    if y0 < 0 or y1 <= y0 or y1 > cat_mask.shape[0]:
        return pts
    band = (cat_mask[y0:y1] == 4)
    if not band.any():
        return pts
    xs = np.where(band.any(axis=0))[0]
    real_w = float(xs.max() - xs.min())
    shoulder_w = float(np.linalg.norm(pts["rs"] - pts["ls"]))
    target_w = min(real_w, 1.35 * shoulder_w)
    if target_w <= shoulder_w * 1.02:
        return pts
    extra = (target_w - shoulder_w) / 2
    direction = (pts["rs"] - pts["ls"]) / (shoulder_w + 1e-6)
    pts = dict(pts)
    pts["ls"] = pts["ls"] - direction * extra
    pts["rs"] = pts["rs"] + direction * extra
    pts["lh"] = pts["lh"] - direction * extra * 0.5
    pts["rh"] = pts["rh"] + direction * extra * 0.5
    return pts

log = logging.getLogger("TryOnEngine")


class OneEuro:
    """
    [FIX H5] One-Euro filter for smooth landmark tracking.
    Smooth when stationary, highly responsive during quick movements.
    """

    def __init__(self, min_cutoff: float = 1.5, beta: float = 0.02, d_cutoff: float = 1.0) -> None:
        self.mc = min_cutoff
        self.b = beta
        self.dc = d_cutoff
        self.x: np.ndarray | None = None
        self.dx: np.ndarray | None = None
        self.t: float | None = None

    @staticmethod
    def _a(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        """Reset filter state when tracking is lost."""
        self.x = None
        self.dx = None
        self.t = None

    def __call__(self, x: np.ndarray, t: float) -> np.ndarray:
        """
        x: (N, 2) array of points
        t: monotonic timestamp in seconds
        """
        x_arr = np.asarray(x, dtype=np.float32)
        if self.x is None:
            self.x = x_arr.copy()
            self.dx = np.zeros_like(x_arr)
            self.t = t
            return x_arr.copy()

        dt = max(t - self.t, 1e-3)
        dx = (x_arr - self.x) / dt
        self.dx += self._a(self.dc, dt) * (dx - self.dx)
        cutoff = self.mc + self.b * np.linalg.norm(self.dx, axis=-1, keepdims=True)
        self.x += self._a(cutoff, dt) * (x_arr - self.x)
        self.t = t
        return self.x.copy()


class TryOnEngine:
    """
    Live virtual try-on engine using MediaPipe Pose + perspective warp.
    [FIX H3] Uses exact 4-point perspective transform.
    """

    def __init__(
        self,
        garment_dir: str | Path = "garments/processed",
        catalog_path: str | Path | None = None,
    ) -> None:
        self.garment_dir = Path(garment_dir)
        self.catalog_path = Path(catalog_path) if catalog_path else self.garment_dir.parent.parent / "backend" / "garments.json"

        self.garments: dict[str, np.ndarray] = {}
        self.garment_anchors: dict[str, dict] = {}  # [FIX C5] per-garment 4-point anchors
        self.garment_anchors8: dict[str, dict] = {}  # [PATCH P3] per-garment 8-point anchors
        self.current_garment_id: str | None = None
        self._lock = threading.Lock()

        # [FIX C2] Backend state and deduplicated warning logging
        self.backend_used: str = "warp"
        self._warned: set[str] = set()
        self.stats: dict = {}  # [FIX M2] Profiler metrics exposed to /api/status

        # [FIX H5] Temporal smoother
        self._smoother = OneEuro()
        self._no_person_since: float | None = None

        # [PATCH P2] Segmenter for occlusion & relighting (if available)
        self.segmenter = BodySegmenter() if BodySegmenter is not None else None
        self._last_cat_mask: np.ndarray | None = None
        self._frame_count: int = 0

        # MediaPipe Pose (model_complexity=0 is Lite model for maximum real-time speed)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Load garments and metadata
        self._load_garments()
        log.info(f"✅ TryOnEngine ready — {len(self.garments)} garments loaded")

    def _warn_once(self, key: str, msg: str) -> None:
        """[FIX C2] Log warning once without repeating per frame."""
        if key not in self._warned:
            self._warned.add(key)
            log.warning(msg)

    def _load_garments(self) -> None:
        """Load all processed transparent PNG garments and their anchors."""
        if not self.garment_dir.exists():
            self.garment_dir.mkdir(parents=True, exist_ok=True)
            return

        for path in sorted(self.garment_dir.glob("*.png")):
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is not None:
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                elif img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                self.garments[path.stem] = img
                log.debug(f"Loaded garment: {path.stem}")

        # Set initial garment
        if self.garments and self.current_garment_id is None:
            self.current_garment_id = next(iter(self.garments.keys()))

        # [FIX C5, PATCH P3] Load per-garment anchors from catalog
        if self.catalog_path.exists():
            try:
                catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
                for g in catalog:
                    gid = g.get("id")
                    if gid in self.garments:
                        if "anchors" in g:
                            self.garment_anchors[gid] = g["anchors"]
                        if "anchors8" in g:
                            self.garment_anchors8[gid] = g["anchors8"]
            except (json.JSONDecodeError, OSError, KeyError) as e:
                self._warn_once("catalog", f"Failed to load catalog anchors: {e!r}")

    def set_garment(self, garment_id: str) -> bool:
        """Thread-safe garment switch."""
        with self._lock:
            if garment_id in self.garments:
                self.current_garment_id = garment_id
                self._smoother.reset()
                return True
            return False

    def clear_garment(self) -> None:
        """Remove active garment overlay."""
        with self._lock:
            self.current_garment_id = None
            self._smoother.reset()

    @staticmethod
    def _pair(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """[FIX H1] Sort points by x-coordinate so left/right never swap after horizontal mirror flips."""
        return (a, b) if a[0] <= b[0] else (b, a)

    @staticmethod
    def estimate_hips(ls: np.ndarray, rs: np.ndarray, torso_ratio: float = 1.3, hip_ratio: float = 0.85) -> tuple[np.ndarray, np.ndarray]:
        """[FIX H2] Extrapolate hip positions from shoulder geometry when hips are occluded."""
        mid = (ls + rs) / 2.0
        sh_vec = rs - ls
        width = float(np.linalg.norm(sh_vec))
        down = np.array([-sh_vec[1], sh_vec[0]], dtype=np.float32) / (width + 1e-6)
        if down[1] < 0:
            down = -down
        hip_mid = mid + down * width * torso_ratio
        half = (sh_vec / (width + 1e-6)) * width * hip_ratio / 2.0
        return hip_mid - half, hip_mid + half

    def _get_body_points(self, landmarks, frame_w: int, frame_h: int) -> dict | None:
        """
        Extract key upper-body landmarks.
        [FIX H1] Sorts L/R shoulders and hips by x-coordinate.
        [FIX H2] Requires only shoulders; estimates hips if low visibility.
        [PATCH P2] Collects elbows and wrists for arm occlusion capsules.
        """
        lm = landmarks.landmark

        def pt(idx: int) -> tuple[np.ndarray, float]:
            l = lm[idx]
            return np.array([l.x * frame_w, l.y * frame_h], dtype=np.float32), float(l.visibility)

        p11, v11 = pt(11)  # Left shoulder
        p12, v12 = pt(12)  # Right shoulder
        p23, v23 = pt(23)  # Left hip
        p24, v24 = pt(24)  # Right hip

        # [FIX H2] Only require shoulders
        if v11 < 0.4 or v12 < 0.4:
            return None

        # [FIX H1] Sort shoulders by x so left/right are image-left/image-right
        ls, rs = self._pair(p11, p12)

        # [FIX H2] Use real hips when both visible >= 0.5, otherwise extrapolate
        if v23 >= 0.5 and v24 >= 0.5:
            lh, rh = self._pair(p23, p24)
        else:
            lh, rh = self.estimate_hips(ls, rs)

        pts = {"ls": ls, "rs": rs, "lh": lh, "rh": rh}

        # [PATCH P2] Elbow and wrist landmarks for forearm occlusion capsules
        p13, v13 = pt(13)  # Left elbow
        p14, v14 = pt(14)  # Right elbow
        p15, v15 = pt(15)  # Left wrist
        p16, v16 = pt(16)  # Right wrist

        if v13 >= 0.4 and v15 >= 0.4:
            pts["el_l"], pts["wr_l"] = p13, p15
        if v14 >= 0.4 and v16 >= 0.4:
            pts["el_r"], pts["wr_r"] = p14, p16

        return pts

    def _get_garment_src_points(self, garment_id: str, w: int, h: int) -> np.ndarray:
        """[FIX C5] Source anchor points from catalog calibration or fallback defaults."""
        if garment_id in self.garment_anchors:
            a = self.garment_anchors[garment_id]
            return np.float32([
                [a["ls"][0] * w, a["ls"][1] * h],
                [a["rs"][0] * w, a["rs"][1] * h],
                [a["lh"][0] * w, a["lh"][1] * h],
                [a["rh"][0] * w, a["rh"][1] * h],
            ])
        # Default fallback for tightly cropped alpha bounding boxes
        return np.float32([
            [w * 0.15, h * 0.02],
            [w * 0.85, h * 0.02],
            [w * 0.10, h * 0.98],
            [w * 0.90, h * 0.98],
        ])

    def _warp_garment(
        self,
        garment: np.ndarray,
        garment_id: str,
        pts: dict,
        frame_h: int,
        frame_w: int,
    ) -> np.ndarray | None:
        """
        Warp garment image onto detected body region.
        [FIX H3] Uses cv2.getPerspectiveTransform (exact 4-point solver).
        """
        h, w = garment.shape[:2]

        # Padding based on shoulder width and torso height
        sh_width = float(np.linalg.norm(pts["rs"] - pts["ls"]))
        pad_x = sh_width * 0.12
        torso_height = float(np.linalg.norm(pts["lh"] - pts["ls"]))
        pad_y_top = torso_height * 0.08
        pad_y_bot = torso_height * 0.05

        ls = pts["ls"] + np.array([-pad_x, -pad_y_top], dtype=np.float32)
        rs = pts["rs"] + np.array([pad_x, -pad_y_top], dtype=np.float32)
        lh = pts["lh"] + np.array([-pad_x * 0.5, pad_y_bot], dtype=np.float32)
        rh = pts["rh"] + np.array([pad_x * 0.5, pad_y_bot], dtype=np.float32)

        src = self._get_garment_src_points(garment_id, w, h)
        dst = np.float32([ls, rs, lh, rh])

        try:
            # [FIX H3] Exact 4-point perspective transform
            M = cv2.getPerspectiveTransform(src, dst)
        except cv2.error as e:
            self._warn_once("warp_matrix", f"Perspective transform computation failed: {e}")
            return None

        warped = cv2.warpPerspective(
            garment,
            M,
            (frame_w, frame_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        return warped

    def _blend(self, frame: np.ndarray, warped: np.ndarray) -> np.ndarray:
        """Standard alpha blend fallback when segmenter is unavailable."""
        if warped is None or warped.shape[2] < 4:
            return frame

        alpha = warped[:, :, 3:4].astype(np.float32) / 255.0
        rgb = warped[:, :, :3].astype(np.float32)
        bg = frame.astype(np.float32)

        result = bg * (1.0 - alpha) + rgb * alpha
        return result.astype(np.uint8)

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        [PATCH P2] Per-frame pipeline:
        1. MediaPipe Pose detection
        2. One-Euro landmark temporal filtering with timeout reset
        3. Multiclass segmentation on alternate frames (for occlusion & relighting)
        4. Perspective / TPS warping
        5. Composite with occlusion mask or fallback blend
        """
        t0 = time.perf_counter()
        self._frame_count += 1

        with self._lock:
            garment_id = self.current_garment_id

        if garment_id is None:
            overlay = frame.copy()
            cv2.putText(
                overlay,
                "Select a garment from the left panel",
                (20, frame.shape[0] // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            return overlay

        garment = self.garments.get(garment_id)
        if garment is None:
            return frame

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        t_pose = time.perf_counter()

        # [PATCH P2] Segmentation every 2nd frame; reuse last mask between runs
        t_seg = t_pose
        cat_mask = self._last_cat_mask
        if (
            self.segmenter is not None
            and getattr(self.segmenter, "available", False)
            and self._frame_count % 2 == 0
        ):
            ts_ms = int(time.monotonic() * 1000)
            fresh = self.segmenter.segment(rgb, ts_ms)
            if fresh is not None:
                cat_mask = fresh
                self._last_cat_mask = fresh
            t_seg = time.perf_counter()

        output = frame.copy()
        t_warp = t_seg
        t_blend = t_seg

        if results.pose_landmarks:
            pts = self._get_body_points(results.pose_landmarks, w, h)
            if pts:
                self._no_person_since = None

                # [FIX H5] Smooth 4 core keypoints using One-Euro filter
                raw = np.array([pts["ls"], pts["rs"], pts["lh"], pts["rh"]], dtype=np.float32)
                smoothed = self._smoother(raw, time.monotonic())
                pts["ls"], pts["rs"] = smoothed[0], smoothed[1]
                pts["lh"], pts["rh"] = smoothed[2], smoothed[3]

                # [PATCH P4] Adaptive fit: widen slightly to hide underlying real clothing
                pts = widen_for_real_clothes(pts, cat_mask)

                t_warp = time.perf_counter()
                gh, gw = garment.shape[:2]
                tps = (
                    compute_tps_anchors(pts, self.garment_anchors8.get(garment_id), gw, gh)
                    if compute_tps_anchors is not None
                    else None
                )
                if tps is not None and tps_warp is not None:
                    src_pts, dst_pts = tps
                    warped = tps_warp(garment, src_pts, dst_pts, w, h)
                else:
                    warped = self._warp_garment(garment, garment_id, pts, h, w)
                t_blend = time.perf_counter()

                if warped is not None and cat_mask is not None and relight_and_soften is not None:
                    # [PATCH P2] Cut occluder (arms, face, hair) out of garment alpha
                    occ = BodySegmenter.build_occluder_mask(cat_mask, pts, (h, w))
                    warped = warped.copy()
                    warped[..., 3] = (
                        warped[..., 3].astype(np.float32) * (1.0 - occ.astype(np.float32) / 255.0)
                    ).astype(np.uint8)

                    # Torso mask = clothes class (4) dilated by 7px
                    torso_mask = cv2.dilate(
                        ((cat_mask == 4).astype(np.uint8) * 255),
                        np.ones((7, 7), np.uint8),
                    )
                    output = relight_and_soften(frame, warped, torso_mask)
                elif warped is not None:
                    # Segmenter unavailable: fallback to clean alpha blend
                    output = self._blend(output, warped)
            else:
                # [PATCH P15] Shoulders missing: reset smoother after 0.5s
                now = time.monotonic()
                if self._no_person_since is None:
                    self._no_person_since = now
                elif now - self._no_person_since > 0.5:
                    self._smoother.reset()

                cv2.putText(
                    output,
                    "Show your shoulders",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 165, 255),
                    2,
                )
        else:
            now = time.monotonic()
            if self._no_person_since is None:
                self._no_person_since = now
            elif now - self._no_person_since > 0.5:
                self._smoother.reset()

            cv2.putText(
                output,
                "Stand in frame",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2,
            )

        t_end = time.perf_counter()
        total_ms = (t_end - t0) * 1e3
        self.stats = {
            "pose_ms": round((t_pose - t0) * 1e3, 2),
            "segmentation_ms": round((t_seg - t_pose) * 1e3, 2),
            "warp_ms": round((t_blend - t_warp) * 1e3, 2),
            "blend_ms": round((t_end - t_blend) * 1e3, 2),
            "total_ms": round(total_ms, 2),
            "fps": round(1000.0 / max(total_ms, 1.0), 1),
        }
        return output
