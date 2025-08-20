import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField, QgsLayerTreeGroup
)
from PyQt5.QtCore import QVariant


BASE_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_landkreis_yearly"


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

root = QgsProject.instance().layerTreeRoot()


for state in os.listdir(BASE_FOLDER):
    state_path = os.path.join(BASE_FOLDER, state)
    if not os.path.isdir(state_path):
        continue


    state_group = root.addGroup(state)


    for landkreis in os.listdir(state_path):
        landkreis_path = os.path.join(state_path, landkreis)
        if not os.path.isdir(landkreis_path):
            continue


        landkreis_group = state_group.addGroup(landkreis)


        for fname in sorted(os.listdir(landkreis_path)):
            if not fname.endswith(".geojson"):
                continue

            year = fname.replace(".geojson", "")
            fpath = os.path.join(landkreis_path, fname)

            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            power_by_type = {label: 0.0 for label in ENERGY_TYPES.values()}
            coords = []

            for feat in data.get("features", []):
                props = feat["properties"]
                coord = feat["geometry"]["coordinates"]
                coords.append(coord)

                code = str(props.get("Energietraeger", "")).strip()
                label = ENERGY_TYPES.get(code, None)
                if label:
                    power = parse_kw(props.get("Bruttoleistung", 0))
                    power_by_type[label] += power

            if not coords:
                print(f"❌ No coordinates in {state}/{landkreis} {year}")
                continue

            # Geometric centroid
            avg_x = sum(c[0] for c in coords) / len(coords)
            avg_y = sum(c[1] for c in coords) / len(coords)
            centroid = QgsGeometry.fromPointXY(QgsPointXY(avg_x, avg_y))

            # Create layer
            layer_name = f"{state}_{landkreis}_{year}"
            layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
            provider = layer.dataProvider()

            # Add fields
            provider.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type])
            provider.addAttributes([QgsField("Year", QVariant.String)])
            layer.updateFields()

            # Add feature
            feat = QgsFeature()
            feat.setGeometry(centroid)
            feat.setAttributes([power_by_type[name] for name in power_by_type] + [year])
            provider.addFeature(feat)
            layer.updateExtents()

            # Add to QGIS under correct group
            QgsProject.instance().addMapLayer(layer, False)
            landkreis_group.addLayer(layer)
            print(f"✅ Loaded: {state}/{landkreis} ({year})")
