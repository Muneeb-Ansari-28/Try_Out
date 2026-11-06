"""
scripts/prepare_garments.py

Batch-processes raw garment photos:
1. Removes background using rembg (isnet-general-use [PATCH P7]).
2. Crops tightly to the visible alpha bounding box [FIX C5].
3. Constrains thumbnail dimensions to 1024x1024.
4. Generates/updates backend/garments.json preserving custom anchors and metadata [FIX C3, C5].
"""

import json
from pathlib import Path
import re
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
raw_dir = ROOT / "garments" / "raw"
out_dir = ROOT / "garments" / "processed"
catalog_path = ROOT / "backend" / "garments.json"

out_dir.mkdir(parents=True, exist_ok=True)
catalog_path.parent.mkdir(parents=True, exist_ok=True)

# Preserve existing entries so custom pricing and manual anchors aren't overwritten [FIX C3, C5]
existing = {}
if catalog_path.exists():
    try:
        existing = {g["id"]: g for g in json.loads(catalog_path.read_text(encoding="utf-8"))}
    except Exception as e:
        print(f"⚠️ Warning loading existing catalog: {e}")

# [PATCH P7] Prefer isnet-general-use for crisp lace/strap edges; fallback to u2netp if needed
session = None
try:
    from rembg import new_session, remove
    session = new_session("isnet-general-use")
    print("✅ rembg session initialized with 'isnet-general-use'")
except Exception as e:
    print(f"⚠️ Could not load isnet-general-use ({e}), falling back to u2netp...")
    try:
        from rembg import new_session, remove
        session = new_session("u2netp")
    except Exception:
        session = None


def slug(s: str) -> str:
    """Generate stable ID from filename stem."""
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_")


def prepare_all():
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    raw_files = [f for f in sorted(raw_dir.iterdir()) if f.suffix.lower() in valid_exts]

    if not raw_files:
        print(f"ℹ️ No raw images found in {raw_dir}")
        return

    for img_path in raw_files:
        gid = slug(img_path.stem)
        print(f"Processing {img_path.name} → {gid}")

        try:
            im = Image.open(img_path).convert("RGB")
            if session:
                cut = remove(im, session=session)
            else:
                cut = im.convert("RGBA")

            # [FIX C5] Crop to visible garment alpha bounding box
            alpha = cut.getchannel("A")
            bbox = alpha.point(lambda a: 255 if a > 10 else 0).getbbox()
            if bbox is None:
                print("  ! background removal found nothing, skipping")
                continue

            cut = cut.crop(bbox)
            cut.thumbnail((1024, 1024))
            cut.save(out_dir / f"{gid}.png")

            existing.setdefault(gid, {
                "id": gid,
                "name": gid.replace("_", " ").title(),
                "price": 49.99,
                "file": f"{gid}.png",
                "category": "upper",
                "collection": "default",
            })
        except Exception as e:
            print(f"  ❌ Error processing {img_path.name}: {e}")

    catalog_path.write_text(json.dumps(list(existing.values()), indent=2), encoding="utf-8")
    print(f"\nDone: {len(existing)} garments registered in {catalog_path}")


if __name__ == "__main__":
    prepare_all()
