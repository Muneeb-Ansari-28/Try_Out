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

import json
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parent.parent
cat_path = ROOT / "backend" / "garments.json"

if not cat_path.exists():
    print(f"❌ Error: Catalog not found at {cat_path}")
    exit(1)

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
    # Compose preview over neutral background
    if img.shape[2] == 4:
        bg = cv2.cvtColor(img[:, :, 3], cv2.COLOR_GRAY2BGR)
        bg = (0.4 * bg + 0.6 * img[:, :, :3]).astype("uint8")
    else:
        bg = img.copy()

    pts = []

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 8:
            pts.append((x / w, y / h))
            cv2.circle(bg, (x, y), 5, (0, 0, 255), -1)
            cv2.putText(
                bg,
                labels[len(pts) - 1],
                (x + 8, y + 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 255),
                1,
            )
            print(f"    [{len(pts)}/8] {labels[len(pts) - 1]}: ({x/w:.3f}, {y/h:.3f})")

    win_title = f"Annotate: {g['id']} — click {len(labels)} points (ESC to skip)"
    cv2.namedWindow(win_title)
    cv2.setMouseCallback(win_title, on_click)

    while len(pts) < 8:
        cv2.imshow(win_title, bg)
        key = cv2.waitKey(20) & 0xFF
        if key == 27:  # ESC
            break

    cv2.destroyAllWindows()

    if len(pts) == 8:
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
        print(f"  ⏭️ {g['id']} skipped (only {len(pts)}/8 points clicked)")

cat_path.write_text(json.dumps(cat, indent=2), encoding="utf-8")
print(f"✅ Catalog updated with anchors at {cat_path}")
