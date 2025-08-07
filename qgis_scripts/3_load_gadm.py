import os
from qgis.core import QgsVectorLayer, QgsProject

# Folder where the GADM files are located
base_path = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data"
file_names = [
    "gadm41_DEU_1.json",  # Germany outer border
    "gadm41_DEU_2.json",  # Bundesländer (states)
    "gadm41_DEU_3.json",
    "gadm41_DEU_4.json"
]

for file_name in file_names:
    file_path = os.path.join(base_path, file_name)
    layer_name = file_name.replace(".json", "")
    layer = QgsVectorLayer(file_path, layer_name, "ogr")
    if layer.isValid():
        QgsProject.instance().addMapLayer(layer)
        print(f"✅ {layer_name} loaded successfully.")
    else:
        print(f"❌ Failed to load {layer_name}")

for layer in QgsProject.instance().mapLayers().values():
    if "gadm41_DEU_" in layer.name():
        layer.renderer().setOpacity(0.5)
        layer.triggerRepaint()
        print(f"☑️ Opacity set for {layer.name()}")


# GADM_2 is assumed to include state boundaries and names
layer = QgsProject.instance().mapLayersByName("gadm41_DEU_2")[0]
label_settings = layer.labeling().clone()
layer_settings = layer.labeling().settings()
layer_settings.fieldName = 'NAME_1'  # eyalet adı bu kolon ismiyle geliyor
layer_settings.enabled = True
layer.setLabeling(QgsVectorLayer.SimpleLabeling(layer_settings))
layer.setLabelsEnabled(True)
layer.triggerRepaint()
print("🏷️ State labels enabled on gadm41_DEU_2")
