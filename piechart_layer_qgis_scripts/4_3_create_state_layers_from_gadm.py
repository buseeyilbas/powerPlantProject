# 4_create_state_layers_from_gadm.py
# Build one toggleable item per German state (from GADM Level-1),
# and give each item a "Germany-style" mask so ONLY that state remains visible.
# Comments and filename are intentionally in English.

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFillSymbol, QgsSingleSymbolRenderer,
    QgsInvertedPolygonRenderer, QgsLayerTreeLayer
)
from qgis.PyQt.QtGui import QColor

# --- CONFIG -------------------------------------------------------------------
# If you already set these in 3_load_gadm.py, you can keep them consistent here.
BASE_PATH = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data/gadm41_DEU"
GADM1_FILE = "gadm41_DEU_1.json"   # Bundesländer polygons (GeoJSON/JSON via OGR)
STATE_FIELD = "NAME_1"             # GADM Level-1 state name
GROUP_NAME  = "DE States (masked)"
DEFAULT_VISIBLE_STATE = "Thüringen"  # set which state starts visible

# --- LOAD THE SOURCE LAYER ----------------------------------------------------
src_path = os.path.join(BASE_PATH, GADM1_FILE)
src_path = src_path.replace("\\", "/")  # OGR prefers forward slashes on Windows
src = QgsVectorLayer(src_path, "gadm_1_src", "ogr")
if not src.isValid():
    raise RuntimeError(f"Could not open '{src_path}'")

idx = src.fields().indexOf(STATE_FIELD)
if idx < 0:
    raise RuntimeError(f"Field '{STATE_FIELD}' not found in {GADM1_FILE}")

state_names = sorted([str(v) for v in src.uniqueValues(idx)])

# --- PREPARE THE GROUP --------------------------------------------------------
project = QgsProject.instance()
root = project.layerTreeRoot()

# Create or reuse parent group
parent_group = root.findGroup(GROUP_NAME)
if not parent_group:
    parent_group = root.insertGroup(0, GROUP_NAME)
else:
    # clear previous run
    for child in list(parent_group.children()):
        parent_group.removeChildNode(child)

# --- HELPER: add a filtered layer into the legend under a given group ---------
def add_layer_under(group, layer):
    # Add the layer (not at the root) and put it into the group
    project.addMapLayer(layer, False)
    group.insertChildNode(0, QgsLayerTreeLayer(layer))

# --- STYLE DEFINITIONS --------------------------------------------------------
def make_white_mask_renderer():
    """Return an inverted-polygon renderer that paints OUTSIDE the state in white."""
    white_fill = QgsFillSymbol.createSimple({
        "color": "255,255,255,255",        # opaque white
        "outline_color": "255,255,255,0",  # no outline
        "outline_width": "0"
    })
    return QgsInvertedPolygonRenderer(QgsSingleSymbolRenderer(white_fill))

def make_outline_renderer():
    """Return a simple renderer that draws only the state outline."""
    outline = QgsFillSymbol.createSimple({
        "color": "255,255,255,0",    # transparent fill
        "outline_color": "0,0,0,255",
        "outline_width": "0.8"
    })
    return QgsSingleSymbolRenderer(outline)

# --- BUILD ONE "ITEM" PER STATE ----------------------------------------------
created = 0
for name in state_names:
    # Defensive quoting for single quotes in names (OGR SQL)
    safe = name.replace("'", "''")
    subset = f""""{STATE_FIELD}" = '{safe}'"""

    # We create two sibling layers inside a per-state group:
    #  1) <State> – Outline (normal renderer)
    #  2) <State> – Mask outside (inverted polygon to white)
    state_group = parent_group.addGroup(name)

    # Outline
    outline_layer = QgsVectorLayer(src.source(), f"{name} – Outline", "ogr")
    outline_layer.setSubsetString(subset)
    outline_layer.setRenderer(make_outline_renderer())
    add_layer_under(state_group, outline_layer)

    # Mask (outside the state)
    mask_layer = QgsVectorLayer(src.source(), f"{name} – Mask outside", "ogr")
    mask_layer.setSubsetString(subset)
    mask_layer.setRenderer(make_white_mask_renderer())
    add_layer_under(state_group, mask_layer)

    # Visibility: only the chosen default state's group is on
    state_group.setItemVisibilityChecked(name == DEFAULT_VISIBLE_STATE)

    created += 1

print(f"✅ Created {created} state groups under: '{GROUP_NAME}'.")
print("ℹ️ Each group contains:")
print("   • an outline layer to delineate the state, and")
print("   • a white 'inverted polygon' mask that hides everything outside the state.")
print(f"👁️ Only '{DEFAULT_VISIBLE_STATE}' is visible initially. Toggle groups to switch focus.")


