import os
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling
)
from qgis.PyQt.QtGui import QColor, QFont

# 📂 Folder where the GADM files are located
base_path = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data/gadm41_DEU"
file_names = [
    "gadm41_DEU_1.json",  # State boundaries
    "gadm41_DEU_2.json",
    "gadm41_DEU_3.json",
    "gadm41_DEU_4.json"
]

# 📌 Load layers and store references
loaded_layers = {}
for file_name in file_names:
    file_path = os.path.join(base_path, file_name)
    layer_name = file_name.replace(".json", "")
    layer = QgsVectorLayer(file_path, layer_name, "ogr")
    if layer.isValid():
        QgsProject.instance().addMapLayer(layer)
        loaded_layers[layer_name] = layer
        print(f"✅ {layer_name} loaded successfully.")
    else:
        print(f"❌ Failed to load {layer_name}")

# 🔍 Set opacity for all loaded layers
for lyr in loaded_layers.values():
    lyr.setOpacity(0.5)  # QGIS 3.10 compatible
    lyr.triggerRepaint()
    print(f"☑️ Opacity set for {lyr.name()}")

# 👁️ Only keep gadm41_DEU_1 visible
root = QgsProject.instance().layerTreeRoot()
for lyr_name, lyr in loaded_layers.items():
    node = root.findLayer(lyr.id())
    if node:
        node.setItemVisibilityChecked(lyr_name == "gadm41_DEU_1")

# 🏷️ Add state name labels to gadm41_DEU_1
layer_1 = loaded_layers.get("gadm41_DEU_1")
if layer_1:
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = "NAME_1"   # State name field
    label_settings.enabled = True

    # ✏️ Text formatting
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 10))
    text_format.setSize(10)
    text_format.setColor(QColor("black"))
    label_settings.setFormat(text_format)

    # Apply labeling
    layer_1.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer_1.setLabelsEnabled(True)
    layer_1.triggerRepaint()
    print("🏷️ State labels enabled on gadm41_DEU_1")
