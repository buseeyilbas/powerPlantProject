# Filename: 4_load_allGermany.py
# Purpose: Load all-Germany plants and style with supervisor-approved colors:
#          Photovoltaics=yellow, Battery=purple, Onshore Wind=light blue,
#          Hydropower=dark blue, Biogas=dark green, Others=gray.
#          QGIS 3.10 compatible (no setElse; uses a filter expression for "Others").

from qgis.core import (
    QgsVectorLayer, QgsProject, QgsRuleBasedRenderer, QgsMarkerSymbol,
    QgsSymbolLayer, QgsProperty
)
import os

# --- Primary 5 codes -> group names -------------------------------------------
PRIMARY_TYPES = {
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# --- Fixed color palette ------------------------------------------------------
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

# --- Data path ----------------------------------------------------------------
geojson_path = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany_three_checks.geojson"
layer_name = "all_germany"
layer = QgsVectorLayer(geojson_path, layer_name, "ogr")

if not layer.isValid():
    print("❌ Failed to load all_germany_three_checks.geojson.")
else:
    # Root for rule-based renderer
    root_rule = QgsRuleBasedRenderer.Rule(None)

    # Helper to build a symbol with our data-defined properties
    def build_symbol(fill_color: str) -> QgsMarkerSymbol:
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": fill_color,
            "outline_color": "black",
            "size": "4"  # base size; overridden by data-defined property below
        })
        # Size ~ log(Bruttoleistung)
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

    # --- Rules for the 5 primary groups (one code each; stable legend order) ---
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

    # --- Catch-all rule for "Others" (QGIS 3.10: use a filter expression) ------
    others_symbol = build_symbol(GROUP_COLORS["Others"])
    others_rule = QgsRuleBasedRenderer.Rule(others_symbol)

    primary_codes_list = ",".join([f"'{c}'" for c in PRIMARY_TYPES.keys()])
    others_expr = (
        f"\"Energietraeger\" IS NULL OR trim(\"Energietraeger\") = '' "
        f"OR NOT (\"Energietraeger\" IN ({primary_codes_list}))"
    )
    others_rule.setFilterExpression(others_expr)
    others_rule.setLabel("Others")
    root_rule.appendChild(others_rule)

    # Apply renderer
    renderer = QgsRuleBasedRenderer(root_rule)
    layer.setRenderer(renderer)

    QgsProject.instance().addMapLayer(layer)
    print("✅ all_germany styled with 5+Others color coding (QGIS 3.10 compatible).")
