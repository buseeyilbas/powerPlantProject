# Filename: 2_style_landkreisPieChart_yearly.py
# Purpose : Auto-load & style yearly Landkreis pies from:
#           <ROOT>/<bin>/<state>/de_<state>_landkreis_pie_<bin>.geojson
#           and create nested groups: "landkreis_pies (yearly)" -> <Year> -> <State>
# QGIS     : 3.10-safe

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol
)
from qgis.PyQt.QtGui import QColor
from pathlib import Path
import os, re

ROOT_DIR   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly")
GROUP_NAME = "landkreis_pies (yearly)"

PALETTE = {
    "pv_kw": QColor(255,255,0,255),
    "battery_kw": QColor(148,87,235,255),
    "wind_kw": QColor(173,216,230,255),
    "hydro_kw": QColor(0,0,255,255),
    "biogas_kw": QColor(0,190,0,255),
    "others_kw": QColor(158,158,158,255),
}

BIN_ORDER = ["pre_1990","1991_1999","2000_2003","2004_2011","2012_2016","2017_2020","2021_2025"]
BIN_LABEL = {
    "pre_1990":  "≤1990 — Pre-EEG",
    "1991_1999": "1991–1999 — Post-reunification",
    "2000_2003": "2000–2003 — EEG launch",
    "2004_2011": "2004–2011 — EEG expansion",
    "2012_2016": "2012–2016 — EEG 2012 reform",
    "2017_2020": "2017–2020 — Auction transition",
    "2021_2025": "2021–2025 — Recent years",
}

proj = QgsProject.instance()
root = proj.layerTreeRoot()

def ensure_group(parent, name: str):
    grp = parent.findGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.findGroup(name)
    if grp is None:
        grp = (parent.addGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.addGroup(name))
    return grp

def style_layer(lyr: QgsVectorLayer):
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
    lyr.triggerRepaint()

def main():
    if not ROOT_DIR.exists():
        raise Exception(f"[ERROR] ROOT_DIR not found: {ROOT_DIR}")

    main_group = ensure_group(root, GROUP_NAME)
    # clear previous
    for ch in list(main_group.children()):
        main_group.removeChildNode(ch)

    # Scan nested structure: <bin>/<state>/de_<state>_landkreis_pie_<bin>.geojson
    targets = {}
    for bin_dir in [p for p in ROOT_DIR.iterdir() if p.is_dir()]:
        bin_slug = bin_dir.name
        for st_dir in [d for d in bin_dir.iterdir() if d.is_dir()]:
            for fn in st_dir.glob(f"de_{st_dir.name}_landkreis_pie_{bin_slug}.geojson"):
                targets.setdefault(bin_slug, {}).setdefault(st_dir.name, []).append(fn)

    if not targets:
        raise Exception(f"[ERROR] No yearly state pie files found under: {ROOT_DIR}")

    ordered_bins = [b for b in BIN_ORDER if b in targets] + [b for b in targets.keys() if b not in BIN_ORDER]
    for bin_slug in ordered_bins:
        g_bin = ensure_group(main_group, BIN_LABEL.get(bin_slug, bin_slug))
        for state_slug in sorted(targets[bin_slug].keys()):
            g_state = ensure_group(g_bin, state_slug)
            for p in sorted(targets[bin_slug][state_slug]):
                vl = QgsVectorLayer(str(p), p.stem, "ogr")
                if not vl.isValid():
                    print(f"[WARN] invalid: {p}")
                    continue
                proj.addMapLayer(vl, False)
                g_state.addLayer(vl)
                style_layer(vl)
                print(f"[OK] {bin_slug}/{state_slug} -> {p.name}")

    print("[DONE] Loaded yearly Landkreis pies by Year → State.")

main()
