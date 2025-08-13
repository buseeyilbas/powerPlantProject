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
