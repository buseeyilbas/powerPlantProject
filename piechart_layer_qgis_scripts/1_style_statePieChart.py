# Auto-load + style single-layer state pies (QGIS 3.10-safe)
# Added: toggle labels with SHOW_LABELS variable

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsFillSymbol, QgsVectorLayerSimpleLabeling, QgsPalLayerSettings,
    QgsTextFormat, QgsTextBufferSettings, QgsProperty
)
from qgis.PyQt.QtGui import QColor, QFont
from pathlib import Path

SHOW_LABELS = False  # True or False

PALETTE = {
    "pv_kw": QColor(255,255,0,255),
    "battery_kw": QColor(148,87,235,255),
    "wind_kw": QColor(173,216,230,255),
    "hydro_kw": QColor(0,0,255,255),
    "biogas_kw": QColor(0,190,0,255),
    "others_kw": QColor(158,158,158,255),
}

BASE_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts")
GEOJSON_PATH = BASE_DIR / "de_state_pie.geojson"

proj = QgsProject.instance()

# Auto-load if missing
lyr = next((L for L in proj.mapLayers().values()
            if L.name()=="de_state_pie" or L.source().endswith("de_state_pie.geojson")), None)
if not lyr:
    if not GEOJSON_PATH.exists():
        raise Exception(f"GeoJSON not found: {GEOJSON_PATH}")
    lyr = QgsVectorLayer(str(GEOJSON_PATH), "de_state_pie", "ogr")
    if not lyr.isValid():
        raise Exception("Failed to load layer.")
    proj.addMapLayer(lyr)
    print(f"Loaded: {GEOJSON_PATH.name}")

# Style by energy_type
cats = []
for key, color in PALETTE.items():
    sym = QgsFillSymbol.createSimple({
        "color": f"{color.red()},{color.green()},{color.blue()},255",
        "outline_color": "50,50,50,150",
        "outline_width": "0.2"
    })
    cats.append(QgsRendererCategory(key, sym, key))
lyr.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

if SHOW_LABELS:
    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = 'CASE WHEN "label_anchor"=1 THEN "name" ELSE NULL END'

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 9))
    fmt.setSize(9)
    fmt.setColor(QColor(25,25,25))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.8)
    buf.setColor(QColor(255,255,255))
    fmt.setBuffer(buf)
    pal.setFormat(fmt)

    size_expr = (
        'CASE '
        ' WHEN @map_scale <= 1500000 THEN 10 '
        ' WHEN @map_scale <= 3000000 THEN 9 '
        ' WHEN @map_scale <= 6000000 THEN 8 '
        ' ELSE 7 END'
    )
    ddp = pal.dataDefinedProperties()
    ddp.setProperty(QgsPalLayerSettings.Size, QgsProperty.fromExpression(size_expr))
    pal.setDataDefinedProperties(ddp)

    try:
        pal.placement = QgsPalLayerSettings.OverPolygon
    except Exception:
        pass

    lyr.setLabelsEnabled(True)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
else:
    lyr.setLabelsEnabled(False)

lyr.triggerRepaint()
iface.layerTreeView().refreshLayerSymbology(lyr.id())
print(f"Styled state pies (labels {'ON' if SHOW_LABELS else 'OFF'}).")
