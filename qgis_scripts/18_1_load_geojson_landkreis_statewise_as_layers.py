# Filename: 18_1_load_geojson_landkreis_statewise_as_layers.py
# Purpose: Build one memory point layer per Landkreis, sized within EACH STATE (statewise scaling).
#          Attribute schema = 5 main energy groups + "Others" for QGIS Pie Chart renderer.

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant

# 📂 Root folder containing subfolders for each state (each subfolder holds Landkreis .geojson files)
GEOJSON_ROOT = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"

# --- Supervisor-approved grouping & colors ------------------------------------
# Keep these five groups separate; everything else (and unknown codes) -> "Others"
PRIMARY_TYPES = {
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# Fixed color palette (apply in QGIS Pie Chart renderer)
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    """Map raw 'Energietraeger' code to one of the 5 main groups; everything else -> 'Others'."""
    return PRIMARY_TYPES.get(code, "Others")

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

# -------- Pass 1: compute totals per state/landkreis (for statewise scaling) ---
state_totals = {}   # {state: {landkreis: total_power}}

for root, _dirs, files in os.walk(GEOJSON_ROOT):
    state = os.path.basename(root)
    if not state:  # safety
        continue

    # Gather all Landkreis files under this state folder
    landkreis_files = [f for f in files if f.endswith(".geojson")]
    if not landkreis_files:
        continue

    state_totals[state] = {}
    for fname in landkreis_files:
        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read {fpath}: {e}")
            continue

        total = 0.0
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            total += parse_kw(props.get("Bruttoleistung", 0))  # include Others too
        state_totals[state][landkreis] = total

# -------- Pass 2: build layers with STATE-BASED scaling -----------------------
MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0

def scale_size(v, vmin, vmax, smin, smax):
    if vmax == vmin:
        return (smin + smax) / 2
    return smin + ((v - vmin) / (vmax - vmin)) * (smax - smin)

for state, landkreis_dict in state_totals.items():
    if not landkreis_dict:
        continue

    vmax = max(landkreis_dict.values()) if landkreis_dict else 0.0
    vmin = min(landkreis_dict.values()) if landkreis_dict else 0.0
    print(f"\n📊 {state} → Max={vmax:.0f}, Min={vmin:.0f}")

    for landkreis, total_power in landkreis_dict.items():
        fpath = os.path.join(GEOJSON_ROOT, state, f"{landkreis}.geojson")
        if not os.path.exists(fpath):
            continue

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read {fpath}: {e}")
            continue

        # Grouped power sums (5 main + Others) and centroid coords
        power_by_group = {g: 0.0 for g in GROUP_ORDER}
        coords = []

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {}) or {}
            coord = geom.get("coordinates")
            if coord:
                coords.append(coord)

            code = str(props.get("Energietraeger", "")).strip()
            group = map_code_to_group(code)
            power_by_group[group] += parse_kw(props.get("Bruttoleistung", 0))

        if not coords:
            print(f"   ❌ No coords in {landkreis}")
            continue

        avg_x = sum(c[0] for c in coords) / len(coords)
        avg_y = sum(c[1] for c in coords) / len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        # Statewise symbol size (relative within this state's min–max)
        size_mm = scale_size(total_power, vmin, vmax, MIN_SIZE_MM, MAX_SIZE_MM)

        # One point feature per Landkreis; fields follow GROUP_ORDER (fixed order)
        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"landkreis_pie_{state}_{landkreis}_statewise", "memory")
        pr = layer.dataProvider()

        pr.addAttributes([QgsField(name, QVariant.Double) for name in GROUP_ORDER])
        pr.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("StateMax", QVariant.Double),
            QgsField("StateMin", QVariant.Double),
            QgsField("DiagramSizeMM", QVariant.Double),
            QgsField("State", QVariant.String),
            QgsField("Landkreis", QVariant.String),
        ])
        layer.updateFields()

        feat = QgsFeature()
        feat.setGeometry(centroid)
        feat.setAttributes(
            [power_by_group[g] for g in GROUP_ORDER] +
            [total_power, vmax, vmin, size_mm, state, landkreis]
        )
        pr.addFeature(feat)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

        print(f"   🎨 {landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm (5+Others grouped)")

# QGIS styling tips:
# - Use 'Pie Chart' renderer on each 'landkreis_pie_*_statewise' layer.
# - Set slices = fields in GROUP_ORDER (same order) and apply GROUP_COLORS.
# - Set symbol size = data-defined from 'DiagramSizeMM' (map units: millimeters).
