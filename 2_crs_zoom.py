from qgis.core import (
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject
)

# Step 1: Define Germany extent in EPSG:4326 (lat/lon)
extent_wgs84 = QgsRectangle(5.5, 47.0, 15.5, 55.5)
crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
crs_target = QgsProject.instance().crs()  # Use current project CRS (should be EPSG:3857)

# Step 2: Transform extent to project CRS
transform = QgsCoordinateTransform(crs_wgs84, crs_target, QgsProject.instance())
extent_project = transform.transformBoundingBox(extent_wgs84)

# Step 3: Apply zoom
iface.mapCanvas().setExtent(extent_project)
iface.mapCanvas().refresh()
print("🔍 Zoomed to Germany.")
