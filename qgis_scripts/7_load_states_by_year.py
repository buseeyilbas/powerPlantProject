
from qgis.core import (
    QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsRuleBasedRenderer,
    QgsMarkerSymbol, QgsSymbolLayer, QgsProperty
)
import os

# --- Input folder and group in Layers panel ---
base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_three_checks"
group_name = "Powerplants by State(3checks)-Year"

root = QgsProject.instance().layerTreeRoot()
existing_group = root.findGroup(group_name)
if existing_group:
    root.removeChildNode(existing_group)
main_group = root.addGroup(group_name)

# --- Primary 5 codes -> group names (others collapse into "Others") -----------
PRIMARY_TYPES = {
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}

# Legend/renderer order
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

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
    """Marker with data-defined size (log power) and green outline if remotely controllable."""
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": fill_color,
        "outline_color": "black",
        "size": "4",  # base; overridden below
    })
    # Size ~ log10(Bruttoleistung)
    sym.symbolLayer(0).setDataDefinedProperty(
        QgsSymbolLayer.PropertySize,
        QgsProperty.fromExpression(
            'CASE WHEN "Bruttoleistung" IS NOT NULL AND "Bruttoleistung" > 0 '
            'THEN 1 + log10("Bruttoleistung") ELSE 0.1 END'
        )
    )
    # Outline: green if remotely controllable, else black
    sym.symbolLayer(0).setDataDefinedProperty(
        QgsSymbolLayer.PropertyStrokeColor,
        QgsProperty.fromExpression(
            "CASE WHEN \"FernsteuerbarkeitNb\" = '1' OR \"FernsteuerbarkeitDv\" = '1' "
            "THEN 'green' ELSE 'black' END"
        )
    )
    return sym

# --- Iterate states and years --------------------------------------------------
for state_name in sorted(os.listdir(base_folder)):
    state_path = os.path.join(base_folder, state_name)
    if not os.path.isdir(state_path):
        continue

    state_group = main_group.addGroup(state_name)

    for file_name in sorted(os.listdir(state_path)):
        if not file_name.endswith(".geojson"):
            continue

        file_path = os.path.join(state_path, file_name)
        year = os.path.splitext(file_name)[0]
        layer_name = f"{state_name}_{year}"
        layer = QgsVectorLayer(file_path, layer_name, "ogr")

        if not layer.isValid():
            print(f"❌ Failed to load {file_path}")
            continue

        # Build rule-based renderer
        root_rule = QgsRuleBasedRenderer.Rule(None)

        # 1) Rules for the 5 primary groups (stable legend order)
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

        # 2) Catch-all "Others" rule (3.10-friendly filter expression)
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

        # Add to project under the state's group; start hidden to avoid clutter
        QgsProject.instance().addMapLayer(layer, False)
        tree_layer = QgsLayerTreeLayer(layer)
        tree_layer.setItemVisibilityChecked(False)
        state_group.insertChildNode(0, tree_layer)

        print(f"✅ Loaded & styled (5+Others): {layer_name}")
