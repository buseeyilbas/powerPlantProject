# Filename: 5_load_by_state_3checks.py
# Purpose: Load each state GeoJSON and style points with supervisor-approved colors:
#          Photovoltaics=yellow, Battery=purple, Onshore Wind=lightskyblue,
#          Hydropower=darkblue, Biogas=darkgreen, Others=gray (catch-all).
#          QGIS 3.10 compatible (no setElse; uses a filter expression for "Others").

from qgis.core import (
    QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup,
    QgsRuleBasedRenderer, QgsMarkerSymbol, QgsSymbolLayer, QgsProperty
)
from qgis.core import (
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling
)
import os

geojson_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_three_checks"
group_name = "Powerplants by State (three checks)"

root = QgsProject.instance().layerTreeRoot()
existing_group = root.findGroup(group_name)
if existing_group:
    root.removeChildNode(existing_group)
layer_group = root.addGroup(group_name)

# --- Primary groups (code -> name) --------------------------------------------
PRIMARY_TYPES = {
    "2495": "Photovoltaics",
    "2496": "Battery",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
}
# Legend order (supervisor-approved)
GROUP_ORDER = ["Photovoltaics", "Battery", "Onshore Wind", "Hydropower", "Biogas", "Others"]

# --- Fixed color palette -------------------------------------------------------
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def build_symbol(fill_color: str) -> QgsMarkerSymbol:
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": fill_color,
        "outline_color": "black",
        "size": "4"  # base size; overridden below
    })
    # Log-scale symbol size by installed power
    sym.symbolLayer(0).setDataDefinedProperty(
        QgsSymbolLayer.PropertySize,
        QgsProperty.fromExpression(
            'CASE WHEN "Bruttoleistung" IS NOT NULL AND "Bruttoleistung" > 0 '
            'THEN 1 + log10("Bruttoleistung") ELSE 0.1 END'
        )
    )
    # Outline green if remotely controllable, else black
    sym.symbolLayer(0).setDataDefinedProperty(
        QgsSymbolLayer.PropertyStrokeColor,
        QgsProperty.fromExpression(
            "CASE WHEN \"FernsteuerbarkeitNb\" = '1' OR \"FernsteuerbarkeitDv\" = '1' "
            "THEN 'green' ELSE 'black' END"
        )
    )
    return sym

# Loop through all GeoJSON files
for file_name in os.listdir(geojson_folder):
    if not file_name.endswith(".geojson"):
        continue

    file_path = os.path.join(geojson_folder, file_name)
    layer_name = os.path.splitext(file_name)[0].replace("_", " ").title().replace(" ", "_")
    layer = QgsVectorLayer(file_path, layer_name, "ogr")

    if not layer.isValid():
        print(f"❌ Failed to load: {file_name}")
        continue

    # Root rule
    root_rule = QgsRuleBasedRenderer.Rule(None)

    # 1) Primary five rules (stable legend order)
    code_by_group = {v: k for k, v in PRIMARY_TYPES.items()}
    for group in GROUP_ORDER:
        if group == "Others":
            continue
        code = code_by_group[group]
        symbol = build_symbol(GROUP_COLORS[group])
        rule = QgsRuleBasedRenderer.Rule(symbol)
        rule.setFilterExpression(f"\"Energietraeger\" = '{code}'")
        rule.setLabel(group)
        root_rule.appendChild(rule)

    # 2) Catch-all "Others" rule (QGIS 3.10: filter expression instead of setElse)
    primary_code_list = ",".join([f"'{c}'" for c in PRIMARY_TYPES.keys()])
    others_expr = (
        f"\"Energietraeger\" IS NULL OR trim(\"Energietraeger\") = '' "
        f"OR NOT (\"Energietraeger\" IN ({primary_code_list}))"
    )
    others_symbol = build_symbol(GROUP_COLORS["Others"])
    others_rule = QgsRuleBasedRenderer.Rule(others_symbol)
    others_rule.setFilterExpression(others_expr)
    others_rule.setLabel("Others")
    root_rule.appendChild(others_rule)

    # Apply renderer
    renderer = QgsRuleBasedRenderer(root_rule)
    layer.setRenderer(renderer)

    # Optional: enable labeling (state/district fields may not exist here; keep off by default)
    # lbl = QgsPalLayerSettings(); ...  # left intentionally minimal

    # Add to group
    QgsProject.instance().addMapLayer(layer, False)
    tree_layer = QgsLayerTreeLayer(layer)
    layer_group.insertChildNode(0, tree_layer)
    print(f"✅ Loaded and styled (5+Others): {layer_name}")
