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
    "gadm41_DEU_2.json",  # District (Landkreis) boundaries
    "gadm41_DEU_3.json",
    "gadm41_DEU_4.json"
]

# Desired visible layers
VISIBLE_LAYERS = {"gadm41_DEU_1", "gadm41_DEU_2"}

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

# 🔍 Set opacity for all loaded layers (QGIS 3.10 compatible)
for lyr in loaded_layers.values():
    lyr.setOpacity(0.5)
    lyr.triggerRepaint()
    print(f"☑️ Opacity set for {lyr.name()}")

# 👁️ Keep only gadm41_DEU_1 and gadm41_DEU_2 visible
root = QgsProject.instance().layerTreeRoot()
for lyr_name, lyr in loaded_layers.items():
    node = root.findLayer(lyr.id())
    if node:
        node.setItemVisibilityChecked(lyr_name in VISIBLE_LAYERS)

# 🏷️ Helper to apply labeling to a given layer by field name
def enable_labeling(layer, field_name: str, font_family="Arial", font_size=10, color="black"):
    if not layer:
        return
    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = field_name
    label_settings.enabled = True

    text_format = QgsTextFormat()
    text_format.setFont(QFont(font_family, font_size))
    text_format.setSize(font_size)
    text_format.setColor(QColor(color))
    label_settings.setFormat(text_format)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

# 🏷️ Add labels
layer_1 = loaded_layers.get("gadm41_DEU_1")
enable_labeling(layer_1, "NAME_1")
print("🏷️ State labels enabled on gadm41_DEU_1")

layer_2 = loaded_layers.get("gadm41_DEU_2")
enable_labeling(layer_2, "NAME_2")
print("🏷️ District labels enabled on gadm41_DEU_2")
