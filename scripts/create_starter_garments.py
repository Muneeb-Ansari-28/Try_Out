"""
scripts/create_starter_garments.py

Generates initial transparent PNG garments matching the exact styles
from the Anywear cottagecore catalog in the reference screenshot:
1. blue_buttondown - Light blue short-sleeve resort collar shirt
2. charcoal_hoodie - Dark charcoal oversized hoodie
3. wavy_blue_sweater - Royal blue knit sweater with iconic white wave lines
4. white_turtleneck - Cream / ivory ribbed knit turtleneck sweater
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


def create_starter_garments(out_dir: str | Path = "garments/processed") -> None:
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    width, height = 600, 700

    catalog = []

    # ----------------------------------------------------
    # 1. Wavy Blue Sweater (The iconic blue & white swirl sweater)
    # ----------------------------------------------------
    img1 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw1 = ImageDraw.Draw(img1)

    # Torso + sleeves polygon
    sweater_poly = [
        (190, 70),   # Left neck
        (130, 95),   # Left shoulder
        (40, 240),   # Left sleeve outer
        (85, 450),   # Left cuff outer
        (140, 435),  # Left cuff inner
        (135, 290),  # Left armpit
        (150, 620),  # Left hem
        (450, 620),  # Right hem
        (465, 290),  # Right armpit
        (460, 435),  # Right cuff inner
        (515, 450),  # Right cuff outer
        (560, 240),  # Right sleeve outer
        (470, 95),   # Right shoulder
        (410, 70),   # Right neck
        (300, 110),  # Collar dip
    ]
    # Base blue color #1e4fd8
    base_blue = (30, 80, 220, 255)
    draw1.polygon(sweater_poly, fill=base_blue)

    # Collar ribbed band
    draw1.arc([200, 50, 400, 115], start=0, end=180, fill=(20, 60, 180, 255), width=18)

    # White abstract organic wavy lines
    wave_lines = [
        # Left chest swirl
        [(170, 220), (220, 260), (250, 360), (210, 430), (160, 390), (170, 300), (220, 320)],
        # Center big loop
        [(260, 160), (330, 200), (380, 280), (340, 370), (290, 420), (340, 500), (410, 480)],
        # Right arm curve
        [(460, 180), (490, 240), (520, 350), (480, 420)],
        # Left arm curve
        [(130, 180), (90, 250), (105, 360)],
        # Bottom curve
        [(200, 540), (280, 580), (380, 560), (430, 590)],
    ]
    for pts in wave_lines:
        for i in range(len(pts) - 1):
            draw1.line([pts[i], pts[i + 1]], fill=(245, 250, 255, 255), width=16)
        # Smooth joints
        for pt in pts:
            draw1.ellipse([pt[0] - 8, pt[1] - 8, pt[0] + 8, pt[1] + 8], fill=(245, 250, 255, 255))

    # Ribbed hemline
    draw1.rectangle([150, 605, 450, 620], fill=(20, 60, 180, 255))
    # Ribbed cuffs
    draw1.polygon([(85, 435), (140, 420), (140, 435), (85, 450)], fill=(20, 60, 180, 255))
    draw1.polygon([(460, 420), (515, 435), (515, 450), (460, 435)], fill=(20, 60, 180, 255))

    p1 = dest / "wavy_blue_sweater.png"
    img1.save(p1, "PNG")
    catalog.append({
        "id": "wavy_blue_sweater",
        "name": "Cobalt Swirl Knit Sweater",
        "price": 68.00,
        "file": "wavy_blue_sweater.png",
        "category": "upper",
        "collection": "cottagecore",
        "tags": ["knit", "sweater", "blue", "wavy"],
    })

    # ----------------------------------------------------
    # 2. Charcoal Hoodie (Oversized minimalist grey hoodie)
    # ----------------------------------------------------
    img2 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(img2)

    hoodie_poly = [
        (210, 85),   # Left collar
        (130, 110),  # Left shoulder drop
        (35, 260),   # Left arm outer
        (75, 460),   # Left cuff outer
        (135, 445),  # Left cuff inner
        (140, 310),  # Left armpit
        (145, 630),  # Left hem
        (455, 630),  # Right hem
        (460, 310),  # Right armpit
        (465, 445),  # Right cuff inner
        (525, 460),  # Right cuff outer
        (565, 260),  # Right arm outer
        (470, 110),  # Right shoulder drop
        (390, 85),   # Right collar
    ]
    charcoal = (52, 55, 62, 255)
    charcoal_shadow = (42, 45, 50, 255)
    draw2.polygon(hoodie_poly, fill=charcoal)

    # Hood collar wrap
    draw2.polygon([(200, 85), (300, 150), (400, 85), (360, 45), (300, 55), (240, 45)], fill=charcoal_shadow)
    # Drawstrings
    draw2.line([(275, 130), (270, 240)], fill=(200, 200, 205, 255), width=5)
    draw2.line([(325, 130), (330, 235)], fill=(200, 200, 205, 255), width=5)

    # Kangaroo pocket
    pocket = [(200, 450), (400, 450), (420, 570), (180, 570)]
    draw2.polygon(pocket, fill=(46, 48, 55, 255))
    draw2.line([(200, 450), (180, 570)], fill=(38, 40, 45, 255), width=3)
    draw2.line([(400, 450), (420, 570)], fill=(38, 40, 45, 255), width=3)

    p2 = dest / "charcoal_hoodie.png"
    img2.save(p2, "PNG")
    catalog.append({
        "id": "charcoal_hoodie",
        "name": "Oversized Charcoal Hoodie",
        "price": 54.00,
        "file": "charcoal_hoodie.png",
        "category": "upper",
        "collection": "cottagecore",
        "tags": ["hoodie", "charcoal", "minimal", "streetwear"],
    })

    # ----------------------------------------------------
    # 3. White Turtleneck (Cream / off-white cozy knit)
    # ----------------------------------------------------
    img3 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw3 = ImageDraw.Draw(img3)

    white_poly = [
        (220, 75),   # Left collar base
        (130, 95),   # Left shoulder
        (45, 250),   # Left sleeve outer
        (85, 450),   # Left cuff outer
        (140, 435),  # Left cuff inner
        (140, 290),  # Left armpit
        (155, 620),  # Left hem
        (445, 620),  # Right hem
        (460, 290),  # Right armpit
        (460, 435),  # Right cuff inner
        (515, 450),  # Right cuff outer
        (555, 250),  # Right sleeve outer
        (470, 95),   # Right shoulder
        (380, 75),   # Right collar base
    ]
    cream_white = (244, 243, 238, 255)
    cream_shadow = (225, 223, 215, 255)
    draw3.polygon(white_poly, fill=cream_white)

    # Turtleneck high collar
    draw3.rectangle([220, 30, 380, 85], fill=cream_white)
    # Collar ribbing lines
    for x in range(225, 380, 8):
        draw3.line([(x, 30), (x, 85)], fill=cream_shadow, width=2)
    # Subtle knit texture lines down chest
    for y in range(120, 600, 30):
        draw3.line([(180, y), (420, y)], fill=(238, 236, 228, 255), width=2)

    p3 = dest / "white_turtleneck.png"
    img3.save(p3, "PNG")
    catalog.append({
        "id": "white_turtleneck",
        "name": "Ribbed Ivory Turtleneck",
        "price": 49.00,
        "file": "white_turtleneck.png",
        "category": "upper",
        "collection": "cottagecore",
        "tags": ["knit", "turtleneck", "cream", "white"],
    })

    # ----------------------------------------------------
    # 4. Light Blue Button-Down (Short sleeve summer shirt)
    # ----------------------------------------------------
    img4 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw4 = ImageDraw.Draw(img4)

    shirt_poly = [
        (220, 80),   # Left collar
        (135, 95),   # Left shoulder
        (50, 240),   # Left sleeve outer
        (90, 320),   # Left sleeve hem
        (140, 310),  # Left sleeve inner
        (145, 270),  # Left armpit
        (160, 600),  # Left hem
        (440, 600),  # Right hem
        (455, 270),  # Right armpit
        (460, 310),  # Right sleeve inner
        (510, 320),  # Right sleeve hem
        (550, 240),  # Right sleeve outer
        (465, 95),   # Right shoulder
        (380, 80),   # Right collar
    ]
    sky_blue = (195, 215, 238, 255)
    shadow_blue = (175, 195, 220, 255)
    draw4.polygon(shirt_poly, fill=sky_blue)

    # Camp collar triangles
    draw4.polygon([(220, 80), (280, 160), (240, 180), (190, 100)], fill=(210, 225, 245, 255))
    draw4.polygon([(380, 80), (320, 160), (360, 180), (410, 100)], fill=(210, 225, 245, 255))

    # Center button placket
    draw4.rectangle([290, 150, 310, 600], fill=shadow_blue)
    # Buttons
    for by in [190, 260, 330, 400, 470, 540]:
        draw4.ellipse([296, by - 4, 304, by + 4], fill=(245, 245, 250, 255))

    # Chest pocket
    draw4.polygon([(200, 230), (250, 230), (250, 290), (225, 310), (200, 290)], fill=shadow_blue)

    p4 = dest / "blue_buttondown.png"
    img4.save(p4, "PNG")
    catalog.append({
        "id": "blue_buttondown",
        "name": "Classic Sky Camp Shirt",
        "price": 42.00,
        "file": "blue_buttondown.png",
        "category": "upper",
        "collection": "cottagecore",
        "tags": ["shirt", "buttondown", "blue", "summer"],
    })

    # Save catalog JSON
    cat_file = Path("backend/garments.json")
    cat_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cat_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"Generated {len(catalog)} starter garments in {dest} and catalog at {cat_file}")


if __name__ == "__main__":
    create_starter_garments()

