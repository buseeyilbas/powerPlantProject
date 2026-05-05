# tools_extract_png_from_embedded_svg.py
# Extracts embedded base64 PNG images from SVG files and saves them as PNG.
# This fixes QGIS showing "?" for SVG markers.

from pathlib import Path
import base64
import re

SRC_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\icons")
OUT_DIR = SRC_DIR / "_png"
OUT_DIR.mkdir(parents=True, exist_ok=True)

pattern = re.compile(r'href="data:image/png;base64,([^"]+)"')

count = 0
for svg_path in SRC_DIR.glob("*.svg"):
    txt = svg_path.read_text(encoding="utf-8", errors="ignore")
    m = pattern.search(txt)
    if not m:
        print(f"[WARN] No embedded PNG found in: {svg_path.name}")
        continue

    b64 = m.group(1)
    png_bytes = base64.b64decode(b64)

    out_png = OUT_DIR / (svg_path.stem + ".png")
    out_png.write_bytes(png_bytes)
    print(f"[OK] {svg_path.name} -> {out_png.name}")
    count += 1

print(f"[DONE] Extracted {count} PNG files into: {OUT_DIR}")
