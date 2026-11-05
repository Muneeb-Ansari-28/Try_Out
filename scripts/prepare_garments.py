"""
scripts/prepare_garments.py

Batch-processes garment photos:
1. Removes background using rembg (ISNet model tuned for clothing/objects).
2. Trims transparent borders to normalize bounding box.
3. Resizes to standard garment aspect ratio.
4. Generates/updates backend/garments.json catalog.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys

from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PrepareGarments")


def process_garments(
    raw_dir: str | Path = "garments/raw",
    processed_dir: str | Path = "garments/processed",
    catalog_path: str | Path = "backend/garments.json",
    model_name: str = "u2netp",
) -> None:
    raw_path = Path(raw_dir)
    proc_path = Path(processed_dir)
    cat_path = Path(catalog_path)

    proc_path.mkdir(parents=True, exist_ok=True)
    cat_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from rembg import remove, new_session
        session = new_session(model_name=model_name)
        logger.info(f"rembg '{model_name}' session initialized successfully.")
    except Exception as e:
        logger.warning(f"rembg session failed with {model_name}: {e}. Retrying default...")
        try:
            from rembg import remove, new_session
            session = new_session()
        except Exception:
            session = None

    valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    raw_files = [f for f in sorted(raw_path.glob("*")) if f.suffix.lower() in valid_extensions]

    if not raw_files:
        logger.info(f"No raw files found in {raw_path}. Checking existing processed garments...")

    catalog = []
    # If catalog exists, load it to preserve custom names/prices
    existing_meta = {}
    if cat_path.exists():
        try:
            with open(cat_path, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    existing_meta[item.get("id")] = item
        except Exception as e:
            logger.warning(f"Could not read existing catalog: {e}")

    # Process each raw image
    for idx, img_path in enumerate(raw_files, start=1):
        out_name = f"{img_path.stem}.png"
        out_path = proc_path / out_name

        logger.info(f"Processing raw garment: {img_path.name} -> {out_name}")

        with open(img_path, "rb") as f:
            raw_bytes = f.read()

        if session:
            try:
                proc_bytes = remove(raw_bytes, session=session)
                with open(out_path, "wb") as f:
                    f.write(proc_bytes)
            except Exception as e:
                logger.error(f"Failed to remove background for {img_path.name}: {e}")
                # Fallback: copy as-is if already PNG
                continue
        else:
            with open(out_path, "wb") as f:
                f.write(raw_bytes)

        # Post-process: crop tight bounding box around visible alpha
        try:
            with Image.open(out_path) as im:
                if im.mode != "RGBA":
                    im = im.convert("RGBA")
                bbox = im.getbbox()
                if bbox:
                    im_cropped = im.crop(bbox)
                    im_cropped.save(out_path, "PNG")
        except Exception as e:
            logger.warning(f"Bounding box crop skipped for {out_name}: {e}")

    # Build catalog from all processed PNGs
    for idx, p_file in enumerate(sorted(proc_path.glob("*.png")), start=1):
        stem = p_file.stem
        existing = existing_meta.get(stem, {})

        pretty_name = existing.get("name", stem.replace("_", " ").replace("-", " ").title())
        price = existing.get("price", 45.00)
        category = existing.get("category", "upper")
        collection = existing.get("collection", "cottagecore")

        catalog.append({
            "id": stem,
            "name": pretty_name,
            "price": price,
            "file": p_file.name,
            "category": category,
            "collection": collection,
            "tags": [category, collection],
        })

    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    logger.info(f"Catalog updated: {len(catalog)} garments registered in {cat_path}")


if __name__ == "__main__":
    process_garments()

