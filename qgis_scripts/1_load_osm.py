from qgis.core import QgsProject, QgsVectorLayer
from qgis.utils import iface

# Load OpenStreetMap basemap (XYZ layer)
urlWithParams = 'type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png'
osm_layer = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms')

if osm_layer.isValid():
    QgsProject.instance().addMapLayer(osm_layer)
    print("🗺️ OpenStreetMap layer added.")
else:
    print("❌ Failed to load OpenStreetMap layer.")

# Load Germany GeoJSON layer
geojson_path = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany.geojson"
germany_layer = QgsVectorLayer(geojson_path, "All Germany Power Plants", "ogr")

if germany_layer.isValid():
    QgsProject.instance().addMapLayer(germany_layer)
    print("✅ Germany GeoJSON layer loaded.")
else:
    print("❌ Failed to load Germany GeoJSON layer.")
