# Filename: 16_1_load_geojson_landkreis_basedGermany_as_layers.py
# Purpose: Build one memory point layer per Landkreis (per state) for QGIS pie charts.
#          Fields = 5 main energy groups + "Others", with supervisor-approved colors.

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant

# 📂 Root folder containing subfolders for each state (each subfolder holds Landkreis .geojson files)
GEOJSON_ROOT = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"

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
    if code in PRIMARY_TYPES:
        return PRIMARY_TYPES[code]
    return "Others"

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

# -------- Pass 1: compute totals per (state, landkreis) for size scaling ------
landkreis_totals = {}

for root, _dirs, files in os.walk(GEOJSON_ROOT):
    for fname in files:
        if not fname.endswith(".geojson"):
            continue

        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")
        state = os.path.basename(root)  # state = folder name
        key = f"{state}_{landkreis}"

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read {fpath}: {e}")
            continue

        total = 0.0
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            total += parse_kw(props.get("Bruttoleistung", 0))
        landkreis_totals[key] = total

if landkreis_totals:
    max_total = max(landkreis_totals.values())
    min_total = min(landkreis_totals.values())
else:
    max_total = 0.0
    min_total = 0.0

print(f"🌍 Landkreis Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build memory layers with grouped fields ---------------------
MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0

def scale_size(v, vmin, vmax, smin, smax):
    if vmax == vmin:
        return (smin + smax) / 2
    return smin + ((v - vmin) / (vmax - vmin)) * (smax - smin)

for root, _dirs, files in os.walk(GEOJSON_ROOT):
    for fname in files:
        if not fname.endswith(".geojson"):
            continue

        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")
        state = os.path.basename(root)
        key = f"{state}_{landkreis}"

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read {fpath}: {e}")
            continue

        power_by_group = {g: 0.0 for g in GROUP_ORDER}
        coords = []

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coord = geom.get("coordinates")
            if coord:
                coords.append(coord)

            code = str(props.get("Energietraeger", "")).strip()
            group = map_code_to_group(code)
            power_by_group[group] += parse_kw(props.get("Bruttoleistung", 0))

        if not coords:
            print(f"❌ No coordinates in {key}")
            continue

        avg_x = sum(c[0] for c in coords) / len(coords)
        avg_y = sum(c[1] for c in coords) / len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        total_power = landkreis_totals.get(key, 0.0)
        size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

        # One point feature per Landkreis; fields in GROUP_ORDER (fixed order)
        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"landkreis_pie_{key}", "memory")
        pr = layer.dataProvider()

        pr.addAttributes([QgsField(name, QVariant.Double) for name in GROUP_ORDER])
        pr.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("DE_MaxTotalPower", QVariant.Double),
            QgsField("DE_MinTotalPower", QVariant.Double),
            QgsField("DiagramSizeMM", QVariant.Double),
            QgsField("State", QVariant.String),
            QgsField("Landkreis", QVariant.String),
        ])
        layer.updateFields()

        feat = QgsFeature()
        feat.setGeometry(centroid)
        feat.setAttributes(
            [power_by_group[g] for g in GROUP_ORDER] +
            [total_power, max_total, min_total, size_mm, state, landkreis]
        )
        pr.addFeature(feat)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

        print(f"🎨 {state}/{landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm (5+Others grouped)")

# QGIS tips:
# - Use 'Pie Chart' renderer on each 'landkreis_pie_*' layer.
# - Set the slices to fields in GROUP_ORDER (same order) and assign GROUP_COLORS.
# - Set size = data-defined using 'DiagramSizeMM' (map units: millimeters).
