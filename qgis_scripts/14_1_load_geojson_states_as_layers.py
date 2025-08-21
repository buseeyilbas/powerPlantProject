import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant

GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

# Energy types mapping
ENERGY_TYPES = {
    "2403": "Deep Geothermal",
    "2405": "Sewage Gas",
    "2406": "Pressure Relief",
    "2493": "Biogas",
    "2495": "Photovoltaics",
    "2496": "Battery",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2957": "Pressure Relief CHP",
    "2958": "Pressure Relief Small"
}

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except:
        return 0.0

# -------- Pass 1: compute all state totals --------
state_totals = {}

for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state = fname.replace(".geojson", "")
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0.0
    for feat in data["features"]:
        props = feat["properties"]
        code = str(props.get("Energietraeger", "")).strip()
        if code in ENERGY_TYPES:
            total += parse_kw(props.get("Bruttoleistung", 0))

    state_totals[state] = total

# global min / max
max_total = max(state_totals.values())
min_total = min(state_totals.values())
print(f"🌍 Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build layers with extra fields --------
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

    power_by_type = {label: 0.0 for label in ENERGY_TYPES.values()}
    coords = []

    for feat in data["features"]:
        props = feat["properties"]
        coord = feat["geometry"]["coordinates"]
        coords.append(coord)

        code = str(props.get("Energietraeger", "")).strip()
        label = ENERGY_TYPES.get(code, None)
        if label:
            power = parse_kw(props.get("Bruttoleistung", 0))
            power_by_type[label] += power

    if not coords:
        print(f"❌ No coordinates in {state}")
        continue

    avg_x = sum(c[0] for c in coords) / len(coords)
    avg_y = sum(c[1] for c in coords) / len(coords)
    centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

    total_power = state_totals[state]

    # --- compute scaled size once (constant per state) ---
    size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

    # ✅ Add fields
    layer = QgsVectorLayer("Point?crs=EPSG:4326", f"state_pie_{state}", "memory")
    provider = layer.dataProvider()

    provider.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type])
    provider.addAttributes([
        QgsField("StateTotalPower", QVariant.Double),
        QgsField("DE_MaxTotalPower", QVariant.Double),
        QgsField("DE_MinTotalPower", QVariant.Double),
        QgsField("DiagramSizeMM", QVariant.Double)
    ])
    layer.updateFields()

    feat = QgsFeature()
    feat.setGeometry(centroid)
    feat.setAttributes(
        [power_by_type[name] for name in power_by_type] +
        [total_power, max_total, min_total, size_mm]
    )
    provider.addFeature(feat)
    layer.updateExtents()

    QgsProject.instance().addMapLayer(layer)
    print(f"🎨 {state}: Total={total_power:.0f}, Size={size_mm:.1f} mm (constant)")
