from qgis.core import QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup
import os

geojson_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon"
group_name = "Powerplants by State (Polygons)"

# Get QGIS root
root = QgsProject.instance().layerTreeRoot()

# Remove group if it already exists
existing_group = root.findGroup(group_name)
if existing_group:
    root.removeChildNode(existing_group)

# Create new group
layer_group = root.addGroup(group_name)

# Loop over all .geojson files
for file_name in os.listdir(geojson_folder):
    if file_name.endswith(".geojson"):
        file_path = os.path.join(geojson_folder, file_name)
        layer_name = os.path.splitext(file_name)[0].replace("_", " ").title().replace(" ", "_")

        layer = QgsVectorLayer(file_path, layer_name, "ogr")

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer, False)  # Add but not to root
            tree_layer = QgsLayerTreeLayer(layer)
            layer_group.insertChildNode(0, tree_layer)
            print(f"✅ Loaded: {layer_name}")
        else:
            print(f"❌ Failed to load: {file_name}")
