# -*- coding: utf-8 -*-
import os
import json
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsFeature,
    QgsGeometry, QgsPointXY, QgsField, QgsLayerTreeGroup
)
from PyQt5.QtCore import QVariant

# 📁 Base folder: state subfolders -> landkreis geojsons inside
BASE_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_landkreis"

# 🔖 Group name in QGIS
TOP_GROUP_NAME = "pieCharts_landkreise_by_state"

# ⚡ Energy codes and labels (columns will use these labels)
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
    except Exception:
        return 0.0

# 🌳 Prepare top group (remove if exists)
project = QgsProject.instance()
root = project.layerTreeRoot()
existing = root.findGroup(TOP_GROUP_NAME)
if existing:
    root.removeChildNode(existing)
top_group = root.addGroup(TOP_GROUP_NAME)

# ♻️ Walk state subfolders
for state_folder in sorted(os.listdir(BASE_FOLDER)):
    state_path = os.path.join(BASE_FOLDER, state_folder)
    if not os.path.isdir(state_path):
        continue

    # Create subgroup per state
    state_group = top_group.addGroup(state_folder)

    for fname in sorted(os.listdir(state_path)):
        if not fname.lower().endswith(".geojson"):
            continue

        fpath = os.path.join(state_path, fname)
        landkreis_name = os.path.splitext(fname)[0]

        # Load raw geojson to aggregate
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed to read {fpath}: {e}")
            continue

        # Aggregate power per energy type + collect coords
        power_by_type = {label: 0.0 for label in ENERGY_TYPES.values()}
        xs, ys, n = 0.0, 0.0, 0

        feats = data.get("features", [])
        if not feats:
            print(f"❌ No features in {landkreis_name}")
            continue

        for feat in feats:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates")
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                try:
                    xs += float(coords[0])
                    ys += float(coords[1])
                    n += 1
                except Exception:
                    pass

            props = feat.get("properties", {})
            code = str(props.get("Energietraeger", "")).strip()
            label = ENERGY_TYPES.get(code, None)
            if label:
                power_by_type[label] += parse_kw(props.get("Bruttoleistung", 0))

        if n == 0:
            print(f"❌ No valid point coordinates in {landkreis_name}")
            continue

        cx, cy = xs / n, ys / n
        centroid = QgsGeometry.fromPointXY(QgsPointXY(cx, cy))

        # Create memory point layer with one feature (columns = energy labels)
        layer_name = f"lk_pie_{state_folder}__{landkreis_name}"
        layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        prov = layer.dataProvider()

        prov.addAttributes([QgsField(name, QVariant.Double) for name in power_by_type.keys()])
        layer.updateFields()

        feat = QgsFeature()
        feat.setGeometry(centroid)
        feat.setAttributes([power_by_type[name] for name in power_by_type.keys()])
        prov.addFeature(feat)
        layer.updateExtents()

        # Add to project under the state subgroup
        QgsProject.instance().addMapLayer(layer, False)
        state_group.addLayer(layer)

        print(f"✅ Loaded: {layer_name}")

print("🎉 All Landkreis layers (grouped by state) are loaded. Add pie charts manually via Layer Properties > Diagrams.")
