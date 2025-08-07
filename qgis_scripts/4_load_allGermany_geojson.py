from qgis.core import QgsVectorLayer, QgsProject

# GeoJSON dosyasının yolu
geojson_path = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany.geojson"

# Layer oluştur
layer_name = "all_germany"
geojson_layer = QgsVectorLayer(geojson_path, layer_name, "ogr")

# Layer geçerli mi kontrol et ve projeye ekle
if geojson_layer.isValid():
    QgsProject.instance().addMapLayer(geojson_layer)
    print("✅ all_germany.geojson successfully loaded.")
else:
    print("❌ Failed to load all_germany.geojson.")
