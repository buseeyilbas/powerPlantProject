from qgis.core import (
    QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup,
    QgsRuleBasedRenderer, QgsMarkerSymbol, QgsSymbolLayer, QgsProperty
)
import os
import json

# 📁 Path to yearly-structured GeoJSONs
base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"
group_name = "Powerplants by State-Year"

# 🧹 Remove previous group if exists
root = QgsProject.instance().layerTreeRoot()
existing_group = root.findGroup(group_name)
if existing_group:
    root.removeChildNode(existing_group)
main_group = root.addGroup(group_name)

# Energy type to color
ENERGY_COLOR_MAP = {
    "2403": "red",
    "2405": "purple",
    "2406": "pink",
    "2493": "lightgreen",
    "2495": "gold",
    "2496": "gray",
    "2497": "white",
    "2498": "skyblue",
    "2957": "orange",
    "2958": "orange"
}

# Energy type to label
energy_labels = {
    "2403": "Deep Geothermal Energy (Tiefe Geothermie)",
    "2405": "Sewage Gas (Klärgas)",
    "2406": "Pressure Relief Energy (Druckentspannung)",
    "2493": "Biogas (Biogas)",
    "2495": "Photovoltaics (Photovoltaik)",
    "2496": "Battery Storage (Stromspeicher)",
    "2497": "Onshore Wind Energy (Windenergie an Land)",
    "2498": "Hydropower (Wasserkraft)",
    "2957": "Pressure Relief (CHP Mix) (Druckentspannung - BHKW, Mischform)",
    "2958": "Pressure Relief (Small-scale Plants) (Druckentspannung - kleine Anlagen)"
}


# 🚀 Loop over states
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

        # 🎨 Styling by rules
        root_rule = QgsRuleBasedRenderer.Rule(None)

        for code, color in ENERGY_COLOR_MAP.items():
            symbol = QgsMarkerSymbol.createSimple({
                'name': 'circle',
                'color': color,
                'outline_color': 'black',
                'size': '4'
            })

            # 📏 Size by log10(power)
            symbol.symbolLayer(0).setDataDefinedProperty(
                QgsSymbolLayer.PropertySize,
                QgsProperty.fromExpression(
                    'CASE WHEN "Bruttoleistung" IS NOT NULL AND "Bruttoleistung" > 0 '
                    'THEN 1 + log10("Bruttoleistung") ELSE 0.1 END'
                )
            )

            # ⚫ Outline color: remotely controllable
            symbol.symbolLayer(0).setDataDefinedProperty(
                QgsSymbolLayer.PropertyStrokeColor,
                QgsProperty.fromExpression(
                    'CASE WHEN "FernsteuerbarkeitNb" = \'1\' OR "FernsteuerbarkeitDv" = \'1\' '
                    'THEN \'green\' ELSE \'black\' END'
                )
            )
            

            rule = QgsRuleBasedRenderer.Rule(symbol)
            rule.setFilterExpression(f'"Energietraeger" = \'{code}\'')
            rule.setLabel(f"{code} - {energy_labels.get(code, 'Unknown')}")
            root_rule.appendChild(rule)

        renderer = QgsRuleBasedRenderer(root_rule)
        layer.setRenderer(renderer)

        # ➕ Add to QGIS project
        QgsProject.instance().addMapLayer(layer, False)
        tree_layer = QgsLayerTreeLayer(layer)
        tree_layer.setItemVisibilityChecked(False)
        state_group.insertChildNode(0, tree_layer)

        print(f"✅ Loaded: {layer_name}")