#!/usr/bin/env python3
"""
Generate favicon.ico and common PNG icon sizes from src/static/favicon.png.

Outputs:
- src/static/favicon.ico (multi-size: 16, 32, 48, 64)
- src/static/favicon-<size>x<size>.png (sizes: 16, 32, 48, 64, 128, 180, 192, 512)
- src/static/apple-touch-icon.png (180x180)
"""
from pathlib import Path
from PIL import Image

SRC = Path("src/static/favicon.png")
OUTDIR = SRC.parent

def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(f"Source image not found: {SRC}")

    im = Image.open(SRC).convert("RGBA")

    # Generate .ico with multiple sizes
    ico_path = OUTDIR / "favicon.ico"
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    # Pillow will downscale from the source image to the provided sizes
    im.save(ico_path, format="ICO", sizes=ico_sizes)

    # Generate PNG sizes
    sizes_png = [16, 32, 48, 64, 128, 180, 192, 512]
    for s in sizes_png:
        out_path = OUTDIR / f"favicon-{s}x{s}.png"
        im_resized = im.resize((s, s), Image.LANCZOS)
        im_resized.save(out_path, format="PNG")

    # Apple Touch Icon
    ati_path = OUTDIR / "apple-touch-icon.png"
    im.resize((180, 180), Image.LANCZOS).save(ati_path, format="PNG")

    print(f"Generated: {ico_path}")
    print("Generated PNG icons:", ", ".join([f"favicon-{s}x{s}.png" for s in sizes_png]))
    print(f"Generated: {ati_path}")

if __name__ == "__main__":
    main()