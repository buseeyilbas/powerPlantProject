from qgis.core import (
    QgsVectorLayer, QgsProject, QgsLayerTreeLayer, QgsLayerTreeGroup,
    QgsRuleBasedRenderer, QgsMarkerSymbol, QgsSymbolLayer, QgsProperty
)
import os

# 📁 Folder path for GeoJSONs
geojson_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_gemeindeschluessel"
group_name = "Powerplants by State (Gemeindeschluessel)"

# 🔄 Replace existing group if already loaded
root = QgsProject.instance().layerTreeRoot()
existing_group = root.findGroup(group_name)
if existing_group:
    root.removeChildNode(existing_group)
layer_group = root.addGroup(group_name)

# 🎨 Energy code → color mapping
ENERGY_COLOR_MAP = {
    "2403": "red",     # Deep Geothermal
    "2405": "purple",  # Sewage Gas
    "2406": "pink",    # Pressure Relief
    "2493": "lightgreen",   # Biogas
    "2495": "gold",    # Photovoltaics
    "2496": "gray",    # Battery
    "2497": "white",   # Onshore Wind
    "2498": "skyblue", # Hydropower
    "2957": "orange",  # Pressure Relief (CHP)
    "2958": "orange"   # Pressure Relief (Small)
}

# 🏷 Energy label map
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

# 🚀 Loop through all GeoJSON files
for file_name in os.listdir(geojson_folder):
    if not file_name.endswith(".geojson"):
        continue

    file_path = os.path.join(geojson_folder, file_name)
    layer_name = os.path.splitext(file_name)[0].replace("_", " ").title().replace(" ", "_")
    layer = QgsVectorLayer(file_path, layer_name, "ogr")

    if not layer.isValid():
        print(f"❌ Failed to load: {file_name}")
        continue

    # 🌟 Root rule
    root_rule = QgsRuleBasedRenderer.Rule(None)

    for code, color in ENERGY_COLOR_MAP.items():
        # 🟢 Base symbol
        symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': color,
            'outline_color': 'black',
            'size': '4'
        })

        # 📏 Log-scale size
        symbol.symbolLayer(0).setDataDefinedProperty(
            QgsSymbolLayer.PropertySize,
            QgsProperty.fromExpression(
                'CASE WHEN "Bruttoleistung" IS NOT NULL AND "Bruttoleistung" > 0 '
                'THEN 1 + log10("Bruttoleistung") ELSE 0.1 END'
            )
        )

        # ⚫ Outline color: remote controllable
        symbol.symbolLayer(0).setDataDefinedProperty(
            QgsSymbolLayer.PropertyStrokeColor,
            QgsProperty.fromExpression(
                'CASE WHEN "FernsteuerbarkeitNb" = \'1\' OR "FernsteuerbarkeitDv" = \'1\' '
                'THEN \'green\' ELSE \'black\' END'
            )
        )

        # 🏷 Rule definition
        rule = QgsRuleBasedRenderer.Rule(symbol)
        rule.setFilterExpression(f'"Energietraeger" = \'{code}\'')
        label = f"{code} - {energy_labels.get(code, 'Unknown')}"
        rule.setLabel(label)
        root_rule.appendChild(rule)

    # 🎨 Apply renderer
    renderer = QgsRuleBasedRenderer(root_rule)
    layer.setRenderer(renderer)

    # ➕ Add to QGIS project
    QgsProject.instance().addMapLayer(layer, False)
    tree_layer = QgsLayerTreeLayer(layer)
    layer_group.insertChildNode(0, tree_layer)
    print(f"✅ Loaded and styled: {layer_name}")
