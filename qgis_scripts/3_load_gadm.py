
import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsFillSymbol, QgsSingleSymbolRenderer, QgsInvertedPolygonRenderer
)
from qgis.PyQt.QtGui import QColor, QFont

# --- CONFIG -------------------------------------------------------------------
BASE_PATH = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data/gadm41_DEU"
GADM_FILES = [
    ("gadm41_DEU_1.json", "gadm41_DEU_1"),  # States (Bundesländer)
    ("gadm41_DEU_2.json", "gadm41_DEU_2"),  # Districts (Landkreise)
    ("gadm41_DEU_3.json", "gadm41_DEU_3"),
    ("gadm41_DEU_4.json", "gadm41_DEU_4"),
]
VISIBLE = {"gadm41_DEU_1", "gadm41_DEU_2"}
OSM_NAME = "OpenStreetMap"  # change if your basemap layer name differs

proj = QgsProject.instance()
root = proj.layerTreeRoot()

# --- 1) Remove existing OSM + GADM + DEU_mask (by id) -------------------------
to_remove = []
for lyr in list(proj.mapLayers().values()):
    if not lyr:
        continue
    if lyr.name() in {OSM_NAME, "DEU_mask"}:
        to_remove.append(lyr.id())
    if lyr.name() in [n for _, n in GADM_FILES]:
        to_remove.append(lyr.id())
for lid in set(to_remove):
    proj.removeMapLayer(lid)

# Use panel order (turn off any stale custom order)
root.setHasCustomLayerOrder(False)

# --- 2) Add OSM FIRST (bottom) ------------------------------------------------
# If OSM already exists in project, you can pull its source like before; here we just add fallback XYZ:
xyz = 'type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png'
osm_layer = QgsRasterLayer(xyz, OSM_NAME, 'wms')
if osm_layer.isValid():
    proj.addMapLayer(osm_layer)
    print("🗺️ OpenStreetMap added first (bottom).")
else:
    print("⚠️ Could not add OpenStreetMap.")

# --- 3) Add DEU_mask as 'Inverted Polygons' (outside = solid white) -----------
states_path = os.path.join(BASE_PATH, "gadm41_DEU_0.json")
mask_layer = QgsVectorLayer(states_path, "DEU_mask", "ogr")   # file-backed, NOT scratch
if not mask_layer.isValid():
    raise RuntimeError("Could not load gadm41_DEU_1.json for DEU_mask.")

# Style: outside = white, inside = transparent
fill_symbol   = QgsFillSymbol.createSimple({"color": "white", "outline_style": "no"})
base_renderer = QgsSingleSymbolRenderer(fill_symbol)
inv_renderer  = QgsInvertedPolygonRenderer(base_renderer)
mask_layer.setRenderer(inv_renderer)
mask_layer.setOpacity(1.0)

proj.addMapLayer(mask_layer)
print("🧱 DEU_mask (inverted polygons) added directly from gadm41_DEU_1 source.")

# --- 4) Add GADM layers (above the mask) --------------------------------------
loaded = {}
for fname, name in GADM_FILES:
    fpath = os.path.join(BASE_PATH, fname)
    lyr = QgsVectorLayer(fpath, name, "ogr")
    if lyr.isValid():
        proj.addMapLayer(lyr)
        loaded[name] = lyr
        print(f"✅ Added: {name}")
    else:
        print(f"❌ Failed to add: {name}")

# Optional: make polygons transparent so OSM peeks through inside Germany
for lyr in loaded.values():
    lyr.setOpacity(0.35)
    lyr.triggerRepaint()

# Only 1–2 visible
for name, lyr in loaded.items():
    node = root.findLayer(lyr.id())
    if node:
        node.setItemVisibilityChecked(name in VISIBLE)

## Labels on 1–2
#def enable_labeling(layer, field_name: str, family="Arial", size=10, color="black"):
#    if not layer:
#        return
#    s = QgsPalLayerSettings()
#    s.fieldName = field_name
#    s.enabled = True
#    fmt = QgsTextFormat()
#    fmt.setFont(QFont(family, size))
#    fmt.setSize(size)
#    fmt.setColor(QColor(color))
#    s.setFormat(fmt)
#    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
#    layer.setLabelsEnabled(True)
#    layer.triggerRepaint()
#
#enable_labeling(loaded.get("gadm41_DEU_1"), "NAME_1")
#enable_labeling(loaded.get("gadm41_DEU_2"), "NAME_2")
#print("🏷️ Labels enabled on 1–2.")

print("✅ Final stack (bottom → top): OpenStreetMap → DEU_mask (inverted) → GADM_1..4 (1–2 visible)")
