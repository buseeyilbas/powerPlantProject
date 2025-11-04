# Filename: 3_style_statewise_landkreisPieChart_yearly.py
# Purpose : Auto-load and style per-bin statewise pies into nested groups:
#           statewise_landkreis_pies (yearly) -> <Year bin> -> <State>
# Notes   : Expects files like: de_<state_slug>_landkreis_pie_<bin>.geojson

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsFillSymbol, QgsVectorLayerSimpleLabeling,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsProperty
)
from qgis.PyQt.QtGui import QColor, QFont
from pathlib import Path
import os, re

SHOW_LABELS = False
ROOT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly")
GROUP_NAME = "statewise_landkreis_pies_yearly"

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

def style_one(lyr):
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
        pal = QgsPalLayerSettings(); pal.enabled = True; pal.isExpression = True
        pal.fieldName = 'CASE WHEN "label_anchor"=1 THEN "name" ELSE NULL END'
        fmt = QgsTextFormat(); fmt.setFont(QFont("Arial", 8)); fmt.setSize(8); fmt.setColor(QColor(25,25,25))
        buf = QgsTextBufferSettings(); buf.setEnabled(True); buf.setSize(0.8); buf.setColor(QColor(255,255,255))
        fmt.setBuffer(buf); pal.setFormat(fmt)
        size_expr = ('CASE WHEN @map_scale <= 750000 THEN 9 WHEN @map_scale <= 1500000 THEN 8 '
                     'WHEN @map_scale <= 3000000 THEN 7 ELSE 6 END')
        ddp = pal.dataDefinedProperties()
        ddp.setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression(size_expr))
        pal.setDataDefinedProperties(ddp)
        try:
            pal.placement = QgsPalLayerSettings.OverPolygon
        except Exception:
            pass
        lyr.setLabelsEnabled(True); lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    else:
        lyr.setLabelsEnabled(False)

    lyr.triggerRepaint()

def main():
    if not ROOT_DIR.exists():
        raise Exception(f"[ERROR] ROOT_DIR not found: {ROOT_DIR}")

    main_group = ensure_group(root, GROUP_NAME)
    # Clear previous runs
    for ch in list(main_group.children()):
        main_group.removeChildNode(ch)

    # Scan files: de_<state_slug>_landkreis_pie_<bin>.geojson
    targets = []
    for base, _, files in os.walk(ROOT_DIR):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                m = re.match(r"de_(.+)_landkreis_pie_(.+)\.geojson", fn)
                if m:
                    state_slug, bin_slug = m.group(1), m.group(2)
                    targets.append((Path(base)/fn, state_slug, bin_slug))

    if not targets:
        print(f"[WARN] No '*_landkreis_pie_<bin>.geojson' found under: {ROOT_DIR}")
        return

    # Re-group: YEAR BIN → STATE → layer(s)
    by_bin = {}
    for path, state_slug, bin_slug in targets:
        by_bin.setdefault(bin_slug, {}).setdefault(state_slug, []).append(path)

    ordered_bins = [b for b in BIN_ORDER if b in by_bin] + [b for b in by_bin.keys() if b not in BIN_ORDER]
    for bin_slug in ordered_bins:
        g_bin = ensure_group(main_group, BIN_LABEL.get(bin_slug, bin_slug))
        for state_slug in sorted(by_bin[bin_slug].keys()):
            g_state = ensure_group(g_bin, f"de_{state_slug}_landkreis_pie")
            for p in sorted(by_bin[bin_slug][state_slug]):
                vl = QgsVectorLayer(str(p), p.stem, "ogr")
                if not vl.isValid():
                    print(f"[WARN] Invalid: {p.name}")
                    continue
                proj.addMapLayer(vl, False)
                g_state.addLayer(vl)
                style_one(vl)
                print(f"[OK] Loaded + styled: {p.name} → {bin_slug}/{state_slug}")

    print("[DONE] Year → State groups created.]")

main()
