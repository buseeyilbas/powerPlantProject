

# Filename: zoom_to_thuringia.py
# Purpose : Zoom the map canvas to the state of Thüringen using existing admin layers if possible,
#           otherwise fall back to a WGS84 bounding box. All comments and the filename are in English.

from qgis.core import (
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject
)

# Thueringen extent in WGS84
#extent_wgs84 = QgsRectangle(8.9, 50.2, 12.5, 51.8)      # for state map 1_style
extent_wgs84 = QgsRectangle(9.4, 50.0, 13.55, 52.05)   # for landkreis map 2_style
crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
crs_target = QgsProject.instance().crs()

# Transform and zoom
transform = QgsCoordinateTransform(crs_wgs84, crs_target, QgsProject.instance())
extent_project = transform.transformBoundingBox(extent_wgs84)
iface.mapCanvas().setExtent(extent_project)
iface.mapCanvas().refresh()
print("🔍 Zoomed to Thüringen.")


