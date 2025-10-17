# Filename: 19_1_load_geojson_landkreis_statewise_as_layers_yearly.py
# Purpose: Build one memory point layer per Landkreis (per state), with one feature per DATE.
#          Attribute schema = 5 main energy groups + "Others" for QGIS Pie Chart renderer.
#          Symbol size scales WITHIN each state (state-wise min–max).

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant, QDate

# 📂 Root folder containing subfolders for each state
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

# -------- Pass 1: compute totals per state/landkreis (for state-wise scaling) --
state_totals = {}   # {state: {landkreis: total_power}}

for root, dirs, files in os.walk(GEOJSON_ROOT):
    state = os.path.basename(root)
    if not state:
        continue

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

# -------- Pass 2: build YEARLY layers with STATE-BASED scaling -----------------
MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0

def scale_size(v, vmin, vmax, smin, smax):
    if vmax == vmin:
        return (smin + smax) / 2
    return smin + ((v - vmin) / (vmax - vmin)) * (smax - smin)

for state, landkreis_dict in state_totals.items():
    if not landkreis_dict:
        continue

    vmax = max(landkreis_dict.values())
    vmin = min(landkreis_dict.values())
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

        yearly_power, coords = {}, []

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {}) or {}
            coord = geom.get("coordinates")
            if coord:
                coords.append(coord)

            # Parse commissioning date (robust: YYYY or YYYY-MM or YYYY-MM-DD or ISO)
            date_str = str(props.get("Inbetriebnahmedatum", "")).strip()
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

            date_key = (year, month, day)
            if date_key not in yearly_power:
                yearly_power[date_key] = {g: 0.0 for g in GROUP_ORDER}
            yearly_power[date_key][group] += power

        if not coords:
            print(f"   ❌ No coords in {state}/{landkreis}")
            continue

        avg_x = sum(c[0] for c in coords) / len(coords)
        avg_y = sum(c[1] for c in coords) / len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        # State-wise symbol size (relative within this state's min–max)
        size_mm = scale_size(total_power, vmin, vmax, MIN_SIZE_MM, MAX_SIZE_MM)

        # ✅ Memory layer: one feature per DATE; fields follow GROUP_ORDER
        layer_name = f"landkreis_pie_{state}_{landkreis}_yearly_statewise"
        layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        pr = layer.dataProvider()

        pr.addAttributes([QgsField(name, QVariant.Double) for name in GROUP_ORDER])
        pr.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("StateMax", QVariant.Double),
            QgsField("StateMin", QVariant.Double),
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
                [total_power, vmax, vmin, size_mm, year_total, QDate(year, month, day), state, landkreis]
            )
            pr.addFeature(feat)

        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        print(f"   🎨 {state}/{landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm (5+Others grouped)")
