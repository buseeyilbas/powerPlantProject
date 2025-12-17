from qgis.core import (
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject
)

# Germany extent in WGS84
extent_wgs84 = QgsRectangle(4.2, 47.0, 15.5, 55.5)
crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
crs_target = QgsProject.instance().crs()

# Transform and zoom
transform = QgsCoordinateTransform(crs_wgs84, crs_target, QgsProject.instance())
extent_project = transform.transformBoundingBox(extent_wgs84)
iface.mapCanvas().setExtent(extent_project)
iface.mapCanvas().refresh()
print("🔍 Zoomed to Germany.")
