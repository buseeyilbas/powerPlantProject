# Filename: 4_save_current_view_png_svg.py
# Purpose : Save current map canvas as ultra-HQ PNG + SVG using a user-provided base filename,
#           with a timestamp suffix (YYYYMMDD_HHMMSS). No layer-name logic.

from pathlib import Path
from datetime import datetime
import re

from PyQt5.QtCore import QSize, QRectF, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtSvg import QSvgGenerator

from qgis.core import QgsProject, QgsMapRendererCustomPainterJob

# ---- SETTINGS ----
OUT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\exports\1_state_pie_yearly\thuringen_statePie_masked_yearly")  # change if needed
BASE_FILENAME = "maStr_pieChart_Thueringen_statePies"  # <-- put your desired base filename here (no extension)
DPI = 1000
SCALE = 10
PNG_TRANSPARENT_BG = False
# ------------------

def safe_filename(name: str) -> str:
    """Return a filesystem-safe, lowercased filename stem."""
    name = (name or "mapcanvas").strip().lower()
    tr_map = str.maketrans({
        "ş":"s","ı":"i","İ":"i","ğ":"g","ö":"o","ü":"u","ç":"c",
        "ä":"a","ö":"o","ü":"u","ß":"ss"
    })
    name = name.translate(tr_map)
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name or "mapcanvas"

def export_canvas(base_stem: str):
    """Export current canvas as PNG+SVG using ultra-high quality settings."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Local timestamp (no ':' to keep Windows-safe file names)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Final stem: <base>__YYYYMMDD_HHMMSS
    final_stem = f"{base_stem}__{ts}"

    png_path = OUT_DIR / f"{final_stem}.png"
    svg_path = OUT_DIR / f"{final_stem}.svg"

    canvas = iface.mapCanvas()
    ms = canvas.mapSettings()

    # Boost resolution
    w, h = canvas.size().width(), canvas.size().height()
    out_size = QSize(int(w * SCALE), int(h * SCALE))
    ms.setOutputSize(out_size)
    ms.setOutputDpi(DPI)
    ms.setFlag(ms.Antialiasing, True)
    ms.setFlag(ms.UseAdvancedEffects, True)
    ms.setFlag(ms.DrawLabeling, True)
    ms.setBackgroundColor(Qt.transparent if PNG_TRANSPARENT_BG else Qt.white)

    # --- PNG ---
    img = QImage(out_size, QImage.Format_ARGB32)
    img.fill(Qt.transparent if PNG_TRANSPARENT_BG else Qt.white)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.HighQualityAntialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start(); job.waitForFinished()
    p.end()
    img.save(str(png_path), "PNG")

    # --- SVG ---
    svg = QSvgGenerator()
    svg.setFileName(str(svg_path))
    svg.setSize(out_size)
    svg.setViewBox(QRectF(0, 0, out_size.width(), out_size.height()))
    svg.setTitle(final_stem)
    svg.setDescription("Exported from QGIS map canvas (ULTRA HQ)")
    p2 = QPainter(svg)
    p2.setRenderHint(QPainter.Antialiasing, True)
    p2.setRenderHint(QPainter.HighQualityAntialiasing, True)
    job2 = QgsMapRendererCustomPainterJob(ms, p2)
    job2.start(); job2.waitForFinished()
    p2.end()

    print(f"[OK] PNG -> {png_path}")
    print(f"[OK] SVG -> {svg_path}")
    print(f"Finished.")

# --- MAIN ---
safe_stem = safe_filename(BASE_FILENAME)
print(f"[INFO] Using base filename: {BASE_FILENAME} -> safe stem: {safe_stem}")
export_canvas(safe_stem)
