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

# -------- Pass 1: compute totals per state --------
state_totals = {}   # {state: {landkreis: total_power}}
for root, dirs, files in os.walk(GEOJSON_ROOT):
    state = os.path.basename(root)
    if not state:
        continue
    state_totals[state] = {}
    for fname in files:
        if not fname.endswith(".geojson"):
            continue
        fpath = os.path.join(root, fname)
        landkreis = fname.replace(".geojson", "")
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = sum(
            parse_kw(feat["properties"].get("Bruttoleistung", 0))
            for feat in data["features"]
            if str(feat["properties"].get("Energietraeger", "")).strip() in ENERGY_TYPES
        )
        state_totals[state][landkreis] = total

# -------- Pass 2: build layers with STATE-BASED scaling --------
MIN_SIZE_MM, MAX_SIZE_MM = 10.0, 20.0

def scale_size(v, vmin, vmax, smin, smax):
    return (smin+smax)/2 if vmax==vmin else smin + ((v-vmin)/(vmax-vmin))*(smax-smin)

for state, landkreis_dict in state_totals.items():
    
    if not landkreis_dict:
        continue
    vmax, vmin = max(landkreis_dict.values()), min(landkreis_dict.values())

    
    print(f"\n📊 {state} → Max={vmax:.0f}, Min={vmin:.0f}")
    for landkreis, total_power in landkreis_dict.items():
        fpath = os.path.join(GEOJSON_ROOT, state, f"{landkreis}.geojson")
        if not os.path.exists(fpath):
            continue
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
            print(f"   ❌ No coords in {landkreis}")
            continue

        avg_x, avg_y = sum(c[0] for c in coords)/len(coords), sum(c[1] for c in coords)/len(coords)
        centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

        # ✅ scale sadece kendi state içindeki min–max ile
        size_mm = scale_size(total_power, vmin, vmax, MIN_SIZE_MM, MAX_SIZE_MM)

        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"landkreis_pie_{state}_{landkreis}_statewise", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type])
        pr.addAttributes([
            QgsField("LandkreisTotalPower", QVariant.Double),
            QgsField("StateMax", QVariant.Double),
            QgsField("StateMin", QVariant.Double),
            QgsField("DiagramSizeMM", QVariant.Double),
            QgsField("State", QVariant.String),
            QgsField("Landkreis", QVariant.String)
        ])
        layer.updateFields()

        feat = QgsFeature()
        feat.setGeometry(centroid)
        feat.setAttributes(
            [power_by_type[n] for n in power_by_type]
            + [total_power, vmax, vmin, size_mm, state, landkreis]
        )
        pr.addFeature(feat); layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        print(f"   🎨 {landkreis}: Total={total_power:.0f}, Size={size_mm:.1f} mm")
