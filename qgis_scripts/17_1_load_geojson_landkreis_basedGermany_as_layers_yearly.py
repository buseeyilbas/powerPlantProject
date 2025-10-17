# Filename: 17_1_load_geojson_landkreis_basedGermany_as_layers_yearly.py
# Purpose: Build one memory point layer per Landkreis (per state), with one feature per DATE.
#          Each feature stores power sums for 5 main energy groups + "Others".
#          Colors follow the supervisor-approved palette.

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant, QDate

# 📂 Root folder: each subfolder is a state; inside are Landkreis .geojson files
GEOJSON_ROOT = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"

# --- Supervisor-approved grouping & colors ------------------------------------
PRIMARY_TYPES = {  # keep these five as distinct groups
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# Fixed color palette for QGIS Pie Chart renderer (reference)
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    """Map raw 'Energietraeger' code to the 5 main groups; everything else -> 'Others'."""
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
        state = os.path.basename(root)
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
            total += parse_kw(props.get("Bruttoleistung", 0))  # include all codes (Others too)
        landkreis_totals[key] = total

if landkreis_totals:
    max_total = max(landkreis_totals.values())
    min_total = min(landkreis_totals.values())
else:
    max_total = 0.0
    min_total = 0.0

print(f"🌍 Landkreis Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build yearly layers (actually per DATE feature) -------------
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

        yearly_power, coords = {}, []

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {}) or {}
            coord = geom.get("coordinates")
            if coord:
                coords.append(coord)

            # Parse commissioning date (expects YYYY-MM-DD or ISO with T)
            date_str = str(props.get("Inbetriebnahmedatum", ""))
            if len(date_str) < 4 or not date_str[:4].isdigit():
                continue
            try:
                ymd = date_str.split("T")[0].split("-")
                year = int(ymd[0])
                month = int(ymd[1]) if len(ymd) > 1 and ymd[1].isdigit() else 1
                day = int(ymd[2]) if len(ymd) > 2 and ymd[2].isdigit() else 1
            except Exception:
                continue

            code = str(props.get("Energietraeger", "")).strip()
            group = map_code_to_group(code)
            power = parse_kw(props.get("Bruttoleistung", 0))

            # Initialize this date bucket lazily with GROUP_ORDER keys
            date_key = (year, month, day)
            if date_key not in yearly_power:
                yearly_power[date_key] = {g: 0.0 for g in GROUP_ORDER}
            yearly_power[date_key][group] += power

        if not coords:
            print(f"❌ No coords in {key}")
            continue

        avg_x = sum(c[0] for c in coords) / len(coords)
        avg_y = sum(c[1] for c in coords) / len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        total_power = landkreis_totals.get(key, 0.0)
        size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

        # ✅ Create memory layer: one feature per DATE; fields follow GROUP_ORDER
        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"landkreis_pie_{key}_yearly", "memory")
        provider = layer.dataProvider()

        provider.addAttributes([QgsField(name, QVariant.Double) for name in GROUP_ORDER])
        provider.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("DE_MaxTotalPower", QVariant.Double),
            QgsField("DE_MinTotalPower", QVariant.Double),
            QgsField("DiagramSizeMM", QVariant.Double),
            QgsField("YearTotal", QVariant.Double),
            QgsField("Date", QVariant.Date),
            QgsField("State", QVariant.String),
            QgsField("Landkreis", QVariant.String),
        ])
        layer.updateFields()

        for (year, month, day), power_dict in sorted(yearly_power.items()):
            year_total = sum(power_dict.values())
            feat = QgsFeature()
            feat.setGeometry(centroid)
            feat.setAttributes(
                [power_dict[g] for g in GROUP_ORDER] +
                [total_power, max_total, min_total, size_mm, year_total, QDate(year, month, day), state, landkreis]
            )
            provider.addFeature(feat)

        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

        print(f"🎨 {state}/{landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm (5+Others grouped)")
