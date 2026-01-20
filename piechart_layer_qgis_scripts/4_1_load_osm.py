from qgis.core import QgsProject, QgsRasterLayer
from qgis.utils import iface

# Load OpenStreetMap basemap (XYZ layer)
url = 'type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png'
osm_layer = QgsRasterLayer(url, 'OpenStreetMap', 'wms')

if osm_layer.isValid():
    QgsProject.instance().addMapLayer(osm_layer)
    print("🗺️ OpenStreetMap layer added.")
else:
    print("❌ Failed to load OpenStreetMap layer.")
