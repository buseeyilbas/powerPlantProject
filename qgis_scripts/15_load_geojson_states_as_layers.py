import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField
)
from PyQt5.QtCore import QVariant


GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

# Energy types
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

   
    layer = QgsVectorLayer("Point?crs=EPSG:4326", f"state_pie_{state}", "memory")
    provider = layer.dataProvider()

    provider.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type])
    layer.updateFields()


    feat = QgsFeature()
    feat.setGeometry(centroid)
    feat.setAttributes([power_by_type[name] for name in power_by_type])
    provider.addFeature(feat)
    layer.updateExtents()


    QgsProject.instance().addMapLayer(layer)
    print(f"✅ Layer loaded for {state}")
