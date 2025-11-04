# Auto-load and style all "*_pie.geojson" under pieCharts/statewise_landkreis_pies
# Groups them under "statewise_landkreis_pies (auto)"
# Works in QGIS 3.10 and shows debug output in console.

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsFillSymbol, QgsVectorLayerSimpleLabeling,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsProperty
)
from qgis.PyQt.QtGui import QColor, QFont
from pathlib import Path
import os

# --- SETTINGS ---
SHOW_LABELS = False  # 👈 change to True to show names
ROOT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies")
GROUP_NAME = "statewise_landkreis_pies"
# ----------------

PALETTE = {
    "pv_kw": QColor(255,255,0,255),
    "battery_kw": QColor(148,87,235,255),
    "wind_kw": QColor(173,216,230,255),
    "hydro_kw": QColor(0,0,255,255),
    "biogas_kw": QColor(0,190,0,255),
    "others_kw": QColor(158,158,158,255),
}

proj = QgsProject.instance()
root = proj.layerTreeRoot()

def ensure_group(name: str):
    grp = root.findGroup(name)
    if grp is None:
        grp = root.addGroup(name)
        print(f"[INFO] Created group: {name}")
    return grp

def already_loaded(path_str: str):
    for lyr in proj.mapLayers().values():
        try:
            if Path(lyr.source()).resolve() == Path(path_str).resolve():
                return True
        except Exception:
            pass
    return False

def style_one(lyr):
    """Apply color palette and label toggle"""
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0"
        })
        cats.append(QgsRendererCategory(key, sym, key))
    lyr.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    if SHOW_LABELS:
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = True
        pal.fieldName = 'CASE WHEN "label_anchor"=1 THEN "name" ELSE NULL END'
        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 8))
        fmt.setSize(8)
        fmt.setColor(QColor(25,25,25))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.8)
        buf.setColor(QColor(255,255,255))
        fmt.setBuffer(buf)
        pal.setFormat(fmt)
        size_expr = (
            'CASE '
            ' WHEN @map_scale <= 750000 THEN 9 '
            ' WHEN @map_scale <= 1500000 THEN 8 '
            ' WHEN @map_scale <= 3000000 THEN 7 '
            ' ELSE 6 END'
        )
        ddp = pal.dataDefinedProperties()
        ddp.setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression(size_expr))
        pal.setDataDefinedProperties(ddp)
        try:
            pal.placement = QgsPalLayerSettings.OverPolygon
        except Exception:
            pass
        lyr.setLabelsEnabled(True)
        lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    else:
        lyr.setLabelsEnabled(False)
    lyr.triggerRepaint()

def main():
    if not ROOT_DIR.exists():
        raise Exception(f"[ERROR] ROOT_DIR not found: {ROOT_DIR}")

    group = ensure_group(GROUP_NAME)
    loaded, styled = 0, 0
    targets = []

    # Find all *_pie.geojson files
    for base, _, files in os.walk(ROOT_DIR):
        for fn in files:
            if fn.lower().endswith("_pie.geojson"):  # skip *_pies.geojson
                path = Path(base) / fn
                targets.append(path)

    if not targets:
        print(f"[WARN] No '*_pie.geojson' found under: {ROOT_DIR}")
        return

    print(f"[INFO] Found {len(targets)} pie files to load.")

    for p in sorted(targets):
        src = str(p)
        if already_loaded(src):
            print(f"[SKIP] Already loaded: {p.name}")
            continue
        vl = QgsVectorLayer(src, p.stem, "ogr")
        if not vl.isValid():
            print(f"[WARN] Invalid layer: {p.name}")
            continue
        proj.addMapLayer(vl, False)
        group.addLayer(vl)
        style_one(vl)
        loaded += 1
        styled += 1
        print(f"[OK] Loaded + styled: {p.name}")

    print(f"[DONE] Loaded {loaded} layers, styled {styled}. Labels {'ON' if SHOW_LABELS else 'OFF'}.")

main()
