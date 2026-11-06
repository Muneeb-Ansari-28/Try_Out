"""
scripts/annotate_garments.py

Interactive 8-point garment anchor annotation tool [FIX C5, PATCH P3].
Allows clicking 8 keypoints per garment:
  1. Left Shoulder
  2. Right Shoulder
  3. Neck Centre
  4. Waist Left
  5. Waist Right
  6. Left Hem
  7. Right Hem
  8. Hem Centre

Clicks 1, 2, 6, 7 map to 4-point perspective warp anchors (ls, rs, lh, rh).
All 8 clicks map to Day 6 non-rigid TPS anchors (anchors8).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
cat_path = ROOT / "backend" / "garments.json"

if not cat_path.exists():
    print(f"❌ Error: Catalog not found at {cat_path}")
    sys.exit(1)

cat = json.loads(cat_path.read_text(encoding="utf-8"))

labels = [
    "Left Shoulder",
    "Right Shoulder",
    "Neck Centre",
    "Waist Left",
    "Waist Right",
    "Left Hem",
    "Right Hem",
    "Hem Centre",
]


class GarmentAnnotator:
    def __init__(self, bg: np.ndarray, w: int, h: int) -> None:
        self.bg = bg
        self.w = w
        self.h = h
        self.pts: list[tuple[float, float]] = []

    def on_click(self, event: int, x: int, y: int, flags: int, param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN and len(self.pts) < 8:
            norm_x, norm_y = x / self.w, y / self.h
            self.pts.append((norm_x, norm_y))
            cv2.circle(self.bg, (x, y), 5, (0, 0, 255), -1)
            label = labels[len(self.pts) - 1]
            cv2.putText(
                self.bg,
                label,
                (x + 8, y + 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 255),
                1,
            )
            print(f"    [{len(self.pts)}/8] {label}: ({norm_x:.3f}, {norm_y:.3f})")


def annotate():
    for g in cat:
        if "anchors" in g and "anchors8" in g:
            print(f"  ℹ️ {g['id']}: already annotated, skipping")
            continue

        img_file = ROOT / "garments" / "processed" / g["file"]
        img = cv2.imread(str(img_file), cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"  ⚠️ {g['id']}: image not found ({img_file}), skipping")
            continue

        h, w = img.shape[:2]
        if img.shape[2] == 4:
            bg = cv2.cvtColor(img[:, :, 3], cv2.COLOR_GRAY2BGR)
            bg = (0.4 * bg + 0.6 * img[:, :, :3]).astype("uint8")
        else:
            bg = img.copy()

        annotator = GarmentAnnotator(bg, w, h)
        win_title = f"Annotate: {g['id']} — click {len(labels)} points (ESC to skip)"
        cv2.namedWindow(win_title)
        cv2.setMouseCallback(win_title, annotator.on_click)

        while len(annotator.pts) < 8:
            cv2.imshow(win_title, annotator.bg)
            key = cv2.waitKey(20) & 0xFF
            if key == 27:  # ESC
                break

        cv2.destroyAllWindows()

        if len(annotator.pts) == 8:
            pts = annotator.pts
            # Clicks 0, 1, 5, 6 are 4-point anchors (ls, rs, lh, rh)
            g["anchors"] = dict(
                zip(
                    ["ls", "rs", "lh", "rh"],
                    [list(pts[0]), list(pts[1]), list(pts[5]), list(pts[6])],
                )
            )
            # All 8 points are TPS anchors
            g["anchors8"] = dict(
                zip(
                    ["ls", "rs", "neck", "waist_l", "waist_r", "lh", "rh", "hem_mid"],
                    [list(p) for p in pts],
                )
            )
            print(f"  ✅ {g['id']} annotated (4-point + 8-point saved)")
        else:
            print(f"  ⏭️ {g['id']} skipped (only {len(annotator.pts)}/8 points clicked)")

    cat_path.write_text(json.dumps(cat, indent=2), encoding="utf-8")
    print(f"✅ Catalog updated with anchors at {cat_path}")


if __name__ == "__main__":
    annotate()
