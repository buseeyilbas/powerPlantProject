# Filename: 15_1_load_geojson_states_as_layers_yearly.py
# Purpose: Build one memory point layer per state, with one feature per YEAR.
#          Each feature stores power sums for 5 main energy groups + "Others",
#          and fixed colors are provided for consistent pie-chart styling.

import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant, QDate

GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

PRIMARY_TYPES = {  # keep these five as distinct groups
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# Fixed color palette (use these in QGIS Pie Chart renderer)
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    """
    Map raw 'Energietraeger' code to one of the 5 main groups; everything else -> 'Others'.
    """
    if code in PRIMARY_TYPES:
        return PRIMARY_TYPES[code]
    return "Others"

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

# -------- Pass 1: compute per-state TOTALS (for size scaling) -----------------
state_totals = {}

for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state = fname.replace(".geojson", "")

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0.0
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        total += parse_kw(props.get("Bruttoleistung", 0))

    state_totals[state] = total

if state_totals:
    max_total = max(state_totals.values())
    min_total = min(state_totals.values())
else:
    max_total = 0.0
    min_total = 0.0

print(f"🌍 Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build YEARLY layers with grouped fields ---------------------
MIN_SIZE_MM = 10.0
MAX_SIZE_MM = 20.0

def scale_size(value, vmin, vmax, smin, smax):
    if vmax == vmin:
        return (smin + smax) / 2
    return smin + ((value - vmin) / (vmax - vmin)) * (smax - smin)

for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state = fname.replace(".geojson", "")

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    yearly_power = {}  # year -> dict(group -> kW)
    coords = []

    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coord = geom.get("coordinates")
        if coord:
            coords.append(coord)

        # Parse commissioning year (first 4 chars of 'Inbetriebnahmedatum')
        year_str = str(props.get("Inbetriebnahmedatum", ""))[:4]
        if not year_str.isdigit():
            continue
        year = int(year_str)

        # Group by 5+Others
        code = str(props.get("Energietraeger", "")).strip()
        group = map_code_to_group(code)

        # Sum installed power
        power_kw = parse_kw(props.get("Bruttoleistung", 0))

        # Initialize year dict lazily with GROUP_ORDER keys
        if year not in yearly_power:
            yearly_power[year] = {g: 0.0 for g in GROUP_ORDER}
        yearly_power[year][group] += power_kw

    if not coords:
        print(f"❌ No coordinates in {state}")
        continue

    # Simple centroid = average of input coordinates (same as your non-yearly script)
    avg_x = sum(c[0] for c in coords) / len(coords)
    avg_y = sum(c[1] for c in coords) / len(coords)
    centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

    total_power = state_totals.get(state, 0.0)

    # Create memory layer (one feature per YEAR)
    layer = QgsVectorLayer("Point?crs=EPSG:4326", f"state_pie_{state}_yearly", "memory")
    provider = layer.dataProvider()

    # Add one numeric field for each group, plus meta fields
    provider.addAttributes([QgsField(g, QVariant.Double) for g in GROUP_ORDER])
    provider.addAttributes([
        QgsField("StateTotalPower", QVariant.Double),
        QgsField("DE_MaxTotalPower", QVariant.Double),
        QgsField("DE_MinTotalPower", QVariant.Double),
        QgsField("DiagramSizeMM", QVariant.Double),
        QgsField("YearTotal", QVariant.Double),
        QgsField("Year", QVariant.Date)   # stored as QDate (1 Jan of the year)
    ])
    layer.updateFields()

    # Compute constant diagram size per state (same size across years)
    size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

    # Add one feature per year
    for year, power_dict in sorted(yearly_power.items()):
        year_total = sum(power_dict.values())

        feat = QgsFeature()
        feat.setGeometry(centroid)

        # Convert to QDate (first day of the year)
        year_date = QDate(year, 1, 1)

        feat.setAttributes(
            [power_dict[g] for g in GROUP_ORDER] +
            [total_power, max_total, min_total, size_mm, year_total, year_date]
        )
        provider.addFeature(feat)

        print(f"📅 {state} {year}: YearTotal={year_total:.0f}, StateTotal={total_power:.0f}, Size={size_mm:.1f} mm")

    layer.updateExtents()
    QgsProject.instance().addMapLayer(layer)

# Tip (QGIS side):
# - Use 'Pie Chart' renderer on each 'state_pie_*_yearly' layer.
# - Set the slices to fields in GROUP_ORDER (same order) and assign GROUP_COLORS.
# - Set size = data-defined using 'DiagramSizeMM' (map units: millimeters).
# - Filter by 'Year' to animate/step through time, or use Atlas with a date-driven filter.
