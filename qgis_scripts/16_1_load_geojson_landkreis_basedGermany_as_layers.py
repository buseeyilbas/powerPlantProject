import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant

# 📂 Root folder containing subfolders for each state
GEOJSON_ROOT = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"

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

# -------- Pass 1: compute totals --------
landkreis_totals = {}
for root, dirs, files in os.walk(GEOJSON_ROOT):
    for fname in files:
        if not fname.endswith(".geojson"):
            continue
        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")
        state = os.path.basename(root)  # 👈 state = klasör adı
        key = f"{state}_{landkreis}"
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = sum(
            parse_kw(feat["properties"].get("Bruttoleistung", 0))
            for feat in data["features"]
            if str(feat["properties"].get("Energietraeger", "")).strip() in ENERGY_TYPES
        )
        landkreis_totals[key] = total

# global min / max
max_total, min_total = max(landkreis_totals.values()), min(landkreis_totals.values())
print(f"🌍 Landkreis Max total={max_total:.0f}, Min total={min_total:.0f}")

# -------- Pass 2: build layers --------
MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0

def scale_size(v, vmin, vmax, smin, smax):
    return (smin+smax)/2 if vmax==vmin else smin + ((v-vmin)/(vmax-vmin))*(smax-smin)

for root, dirs, files in os.walk(GEOJSON_ROOT):
    for fname in files:
        if not fname.endswith(".geojson"):
            continue
        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")
        state = os.path.basename(root)
        key = f"{state}_{landkreis}"
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        power_by_type, coords = {label: 0.0 for label in ENERGY_TYPES.values()}, []
        for feat in data["features"]:
            props, coord = feat["properties"], feat["geometry"]["coordinates"]
            coords.append(coord)
            label = ENERGY_TYPES.get(str(props.get("Energietraeger", "")).strip())
            if label:
                power_by_type[label] += parse_kw(props.get("Bruttoleistung", 0))
        if not coords:
            print(f"❌ No coords in {key}")
            continue

        avg_x, avg_y = sum(c[0] for c in coords)/len(coords), sum(c[1] for c in coords)/len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        total_power = landkreis_totals[key]
        size_mm = scale_size(total_power, min_total, max_total, MIN_SIZE_MM, MAX_SIZE_MM)

        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"landkreis_pie_{key}", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type])
        pr.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("DE_MaxTotalPower", QVariant.Double),
            QgsField("DE_MinTotalPower", QVariant.Double),
            QgsField("DiagramSizeMM", QVariant.Double),
            QgsField("State", QVariant.String),
            QgsField("Landkreis", QVariant.String)
        ])
        layer.updateFields()

        feat = QgsFeature()
        feat.setGeometry(centroid)
        feat.setAttributes(
            [power_by_type[n] for n in power_by_type]
            + [total_power, max_total, min_total, size_mm, state, landkreis]
        )
        pr.addFeature(feat); layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        print(f"🎨 {state}/{landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm")
