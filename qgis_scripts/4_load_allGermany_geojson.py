from qgis.core import (
    QgsVectorLayer, QgsProject, QgsRuleBasedRenderer, QgsMarkerSymbol,
    QgsSymbolLayer, QgsProperty, QgsRuleBasedRenderer
)
import os

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

# 📁 GeoJSON path
geojson_path = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany.geojson"
layer_name = "all_germany"
layer = QgsVectorLayer(geojson_path, layer_name, "ogr")

if not layer.isValid():
    print("❌ Failed to load all_germany.geojson.")
else:
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

        # ⚫ Outline color: remotely controllable
        symbol.symbolLayer(0).setDataDefinedProperty(
            QgsSymbolLayer.PropertyStrokeColor,
            QgsProperty.fromExpression(
                'CASE WHEN "FernsteuerbarkeitNb" = \'1\' OR "FernsteuerbarkeitDv" = \'1\' '
                'THEN \'green\' ELSE \'black\' END'
            )
        )

        # 🎯 Rule for energy code
        rule = QgsRuleBasedRenderer.Rule(symbol)
        rule.setFilterExpression(f'"Energietraeger" = \'{code}\'')
        label = f"{code} - {energy_labels.get(code, 'Unknown')}"
        rule.setLabel(label)
        root_rule.appendChild(rule)

    # 🎨 Apply renderer and add layer
    renderer = QgsRuleBasedRenderer(root_rule)
    layer.setRenderer(renderer)
    QgsProject.instance().addMapLayer(layer)

    print("✅ all_germany.geojson successfully loaded and styled.")
