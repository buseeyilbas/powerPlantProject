# Filename: 2_style_thueringen_statewise_landkreisPieChart_yearly.py
# Purpose:
#   Thüringen-only QGIS loader & styler for statewise Landkreis yearly pie charts.
#   - Loads a SINGLE Thüringen Landkreis pie layer per bin
#   - Loads Thüringen cumulative ROW chart (+ optional guide lines + frame) created by step2_5
#   - Loads Thüringen cumulative COLUMN chart (+ frame) created by step2_5
#   - Loads Thüringen energy legend / pie size legend / legend frames created by step2_5
#   - Loads Thüringen Landkreis numbering:
#       * Numbers on map
#       * HUD / side list if available
#
# Notes:
#   - Row chart stays in MW.
#   - Column chart stays unchanged.
#   - Landkreis numbers on the map stay unchanged.
#   - Legend/title styling is aligned with 1_style_thueringen_statePieChart_yearly.py.

from pathlib import Path
import json
import re

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsFillSymbol,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsSingleSymbolRenderer,
    QgsRuleBasedLabeling,
    QgsMarkerSymbol,
    QgsLineSymbol,
    QgsUnitTypes,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor, QFont


# ----------------------------------------------------------
# PATHS
# ----------------------------------------------------------
ROOT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_statewise_landkreis_pies_yearly"
)

GROUP_NAME = "thueringen_statewise_landkreis_pies (yearly)"

# Row chart
CHART_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart_guides.geojson"
FRAME_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart_frame.geojson"

# Column chart
COL_BARS_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_bars.geojson"
COL_LABELS_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_labels.geojson"
COL_FRAME_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_frame.geojson"

# Legends / frames from step2_5
ENERGY_LEGEND_PATH = ROOT_DIR / "thueringen_landkreis_energy_legend_points.geojson"
PIE_SIZE_LEGEND_CIRCLES_PATH = ROOT_DIR / "thueringen_pie_size_legend_circles.geojson"
PIE_SIZE_LEGEND_LABELS_PATH = ROOT_DIR / "thueringen_pie_size_legend_labels.geojson"
LEGEND_FRAMES_PATH = ROOT_DIR / "thueringen_legend_frames.geojson"

# Landkreis numbering layers
NUMBER_POINTS_PATH = ROOT_DIR / "thueringen_landkreis_number_points.geojson"
NUMBER_LIST_PATH = ROOT_DIR / "thueringen_landkreis_number_list_points.geojson"

# step0 centers file (for optional HUD names)
CENTERS_PATH = ROOT_DIR.parent / "thueringen_landkreis_centers" / "thueringen_landkreis_centers.geojson"


# ----------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------
LOAD_GUIDE_LINES = True
LOAD_ROW_FRAME = True
LOAD_COLUMN_FRAME = True

LOAD_ENERGY_LEGEND = True
LOAD_PIE_SIZE_LEGEND = True
LOAD_LEGEND_FRAMES = True

LOAD_NUMBER_POINTS = True
LOAD_NUMBER_LIST = False
LOAD_HUD_NAMES = True

# Match 1_style_thueringen_statePieChart_yearly.py
UNIFIED_TITLE_FONT_FAMILY = "Arial"
UNIFIED_TITLE_FONT_SIZE = 10
UNIFIED_TITLE_FONT_WEIGHT = QFont.Bold


# ----------------------------------------------------------
# YEAR BINS
# ----------------------------------------------------------
YEAR_BINS = [
    ("pre_1990", "≤1990", None, 1990),
    ("1991_1992", "1991–1992", 1991, 1992),
    ("1993_1994", "1993–1994", 1993, 1994),
    ("1995_1996", "1995–1996", 1995, 1996),
    ("1997_1998", "1997–1998", 1997, 1998),
    ("1999_2000", "1999–2000", 1999, 2000),
    ("2001_2002", "2001–2002", 2001, 2002),
    ("2003_2004", "2003–2004", 2003, 2004),
    ("2005_2006", "2005–2006", 2005, 2006),
    ("2007_2008", "2007–2008", 2007, 2008),
    ("2009_2010", "2009–2010", 2009, 2010),
    ("2011_2012", "2011–2012", 2011, 2012),
    ("2013_2014", "2013–2014", 2013, 2014),
    ("2015_2016", "2015–2016", 2015, 2016),
    ("2017_2018", "2017–2018", 2017, 2018),
    ("2019_2020", "2019–2020", 2019, 2020),
    ("2021_2022", "2021–2022", 2021, 2022),
    ("2023_2024", "2023–2024", 2023, 2024),
    ("2025_2026", "2025–2026", 2025, 2026),
]
YEAR_SLUGS = [slug for (slug, *_ ) in YEAR_BINS]
YEAR_LABEL_MAP = {slug: label for (slug, label, *_ ) in YEAR_BINS}


# ----------------------------------------------------------
# COLORS
# ----------------------------------------------------------
PALETTE = {
    "pv_kw": QColor(255, 255, 0, 255),
    "battery_kw": QColor(148, 87, 235, 255),
    "wind_kw": QColor(173, 216, 230, 255),
    "hydro_kw": QColor(0, 0, 255, 255),
    "biogas_kw": QColor(0, 190, 0, 255),
    "others_kw": QColor(158, 158, 158, 255),
}

proj = QgsProject.instance()
root = proj.layerTreeRoot()


# ----------------------------------------------------------
# UTILITIES
# ----------------------------------------------------------
def ensure_group(parent, name: str):
    grp = parent.findGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.findGroup(name)
    if grp is None:
        grp = parent.addGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.addGroup(name)
    return grp


def make_unified_title_format():
    fmt = QgsTextFormat()
    fmt.setFont(QFont(UNIFIED_TITLE_FONT_FAMILY, UNIFIED_TITLE_FONT_SIZE, UNIFIED_TITLE_FONT_WEIGHT))
    fmt.setSize(UNIFIED_TITLE_FONT_SIZE)
    fmt.setColor(QColor(0, 0, 0))

    buf = QgsTextBufferSettings()
    buf.setEnabled(False)
    fmt.setBuffer(buf)
    return fmt


def is_anchor_one(v) -> bool:
    if v is None:
        return False
    try:
        return int(float(v)) == 1
    except Exception:
        return str(v).strip() in {"1", "1.0", "true", "True"}


# ----------------------------------------------------------
# PIE POLYGONS
# ----------------------------------------------------------
def style_pie_polygons(layer: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        cats.append(QgsRendererCategory(key, sym, key))

    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ENERGY LEGEND (match 1_style)
# ----------------------------------------------------------
def style_energy_legend_layer(layer: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "size": "5.0",
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        cats.append(QgsRendererCategory(key, sym, key))

    title_sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    cats.append(QgsRendererCategory("legend_title", title_sym, "legend_title"))

    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    def add_label_rule(filter_expr: str, x_offset: float):
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
        pal.fieldName = "legend_label"
        try:
            pal.placement = QgsPalLayerSettings.OverPoint
        except Exception:
            pass
        pal.xOffset = x_offset
        pal.yOffset = 0.0

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 9))
        fmt.setSize(9)
        fmt.setColor(QColor(0, 0, 0))
        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)
        pal.setFormat(fmt)

        rule = QgsRuleBasedLabeling.Rule(pal)
        rule.setFilterExpression(filter_expr)
        root_rule.appendChild(rule)

    def add_title_rule():
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
        pal.fieldName = "legend_label"
        pal.xOffset = 0
        pal.yOffset = 0
        pal.setFormat(make_unified_title_format())

        rule = QgsRuleBasedLabeling.Rule(pal)
        rule.setFilterExpression("\"energy_type\" = 'legend_title'")
        root_rule.appendChild(rule)

    add_label_rule("\"legend_label\" = 'Photovoltaics'", 15.0)
    add_label_rule("\"legend_label\" = 'Onshore Wind Energy'", 21.0)
    add_label_rule("\"legend_label\" = 'Hydropower'", 15.0)
    add_label_rule("\"legend_label\" = 'Biogas'", 11.0)
    add_label_rule("\"legend_label\" = 'Battery'", 11.0)
    add_label_rule("\"legend_label\" = 'Others'", 11.0)
    add_title_rule()

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# PIE SIZE LEGEND (match 1_style)
# ----------------------------------------------------------
def style_pie_size_legend_circles_layer(layer: QgsVectorLayer):
    sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",
        "outline_color": "90,90,90,255",
        "outline_width": "0.35",
    })
    try:
        sym.setOutputUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def style_pie_size_legend_labels_layer(layer: QgsVectorLayer):
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    title_pal = QgsPalLayerSettings()
    title_pal.enabled = True
    title_pal.isExpression = True
    title_pal.fieldName = 'CASE WHEN "kind" = \'title\' THEN "legend_label" ELSE NULL END'
    title_pal.setFormat(make_unified_title_format())
    try:
        title_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    title_rule = QgsRuleBasedLabeling.Rule(title_pal)
    title_rule.setFilterExpression("\"kind\" = 'title'")
    root_rule.appendChild(title_rule)

    item_pal = QgsPalLayerSettings()
    item_pal.enabled = True
    item_pal.isExpression = True
    item_pal.fieldName = 'CASE WHEN "kind" = \'item\' THEN "legend_label" ELSE NULL END'
    item_fmt = QgsTextFormat()
    item_fmt.setFont(QFont("Arial", 8))
    item_fmt.setSize(8)
    item_fmt.setColor(QColor(0, 0, 0))
    item_buf = QgsTextBufferSettings()
    item_buf.setEnabled(False)
    item_fmt.setBuffer(item_buf)
    item_pal.setFormat(item_fmt)
    try:
        item_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    item_rule = QgsRuleBasedLabeling.Rule(item_pal)
    item_rule.setFilterExpression("\"kind\" = 'item'")
    root_rule.appendChild(item_rule)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# LEGEND FRAMES
# ----------------------------------------------------------
def style_legend_frames_layer(layer: QgsVectorLayer):
    sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",
        "outline_color": "150,150,150,255",
        "outline_width": "0.4",
    })
    try:
        sym.setOutputUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ROW CHART (keep as-is, just style cleanup if needed)
# ----------------------------------------------------------
def style_row_chart(layer: QgsVectorLayer):
    fields = [f.name() for f in layer.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

    if energy_field:
        cats = []
        for key, color in PALETTE.items():
            sym = QgsFillSymbol.createSimple({
                "color": f"{color.red()},{color.green()},{color.blue()},220",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0",
            })
            cats.append(QgsRendererCategory(key, sym, key))
        layer.setRenderer(QgsCategorizedSymbolRenderer(energy_field, cats))
    else:
        sym = QgsFillSymbol.createSimple({
            "color": "200,200,200,200",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        layer.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # year labels
    pal_year = QgsPalLayerSettings()
    pal_year.enabled = True
    pal_year.isExpression = True
    pal_year.fieldName = 'CASE WHEN "label_anchor" = 1 THEN "year_bin_label" ELSE NULL END'
    try:
        pal_year.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_year = QgsTextFormat()
    fmt_year.setFont(QFont("Arial", 7))
    fmt_year.setSize(7)
    fmt_year.setColor(QColor(0, 0, 0))
    buf_year = QgsTextBufferSettings()
    buf_year.setEnabled(False)
    fmt_year.setBuffer(buf_year)
    pal_year.setFormat(fmt_year)

    rule_year = QgsRuleBasedLabeling.Rule(pal_year)
    rule_year.setFilterExpression("\"label_anchor\" = 1")
    root_rule.appendChild(rule_year)

    # value labels in MW
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000.0, 1) '
        'ELSE NULL END'
    )
    try:
        pal_val.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_val = QgsTextFormat()
    fmt_val.setFont(QFont("Arial", 7))
    fmt_val.setSize(7)
    fmt_val.setColor(QColor(0, 0, 0))
    buf_val = QgsTextBufferSettings()
    buf_val.setEnabled(False)
    fmt_val.setBuffer(buf_val)
    pal_val.setFormat(fmt_val)

    rule_val = QgsRuleBasedLabeling.Rule(pal_val)
    rule_val.setFilterExpression("\"value_anchor\" = 1")
    root_rule.appendChild(rule_val)

    # title
    pal_title = QgsPalLayerSettings()
    pal_title.enabled = True
    pal_title.isExpression = True
    pal_title.fieldName = 'CASE WHEN "year_bin_slug" = \'title\' THEN "year_bin_label" ELSE NULL END'
    try:
        pal_title.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_title = QgsTextFormat()
    fmt_title.setFont(QFont("Arial", 9, QFont.Bold))
    fmt_title.setSize(9)
    fmt_title.setColor(QColor(0, 0, 0))
    buf_title = QgsTextBufferSettings()
    buf_title.setEnabled(False)
    fmt_title.setBuffer(buf_title)
    pal_title.setFormat(fmt_title)

    rule_title = QgsRuleBasedLabeling.Rule(pal_title)
    rule_title.setFilterExpression("\"year_bin_slug\" = 'title'")
    root_rule.appendChild(rule_title)

    # unit
    pal_unit = QgsPalLayerSettings()
    pal_unit.enabled = True
    pal_unit.isExpression = True
    pal_unit.fieldName = 'CASE WHEN "year_bin_slug" = \'unit\' THEN "year_bin_label" ELSE NULL END'
    try:
        pal_unit.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_unit = QgsTextFormat()
    fmt_unit.setFont(QFont("Arial", 9, QFont.Bold))
    fmt_unit.setSize(9)
    fmt_unit.setColor(QColor(0, 0, 0))
    buf_unit = QgsTextBufferSettings()
    buf_unit.setEnabled(False)
    fmt_unit.setBuffer(buf_unit)
    pal_unit.setFormat(fmt_unit)

    rule_unit = QgsRuleBasedLabeling.Rule(pal_unit)
    rule_unit.setFilterExpression("\"year_bin_slug\" = 'unit'")
    root_rule.appendChild(rule_unit)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def style_row_guides(layer: QgsVectorLayer):
    sym = QgsLineSymbol.createSimple({
        "color": "0,0,0,120",
        "width": "0.20",
        "line_style": "dash",
    })
    try:
        sym.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass
    try:
        sl = sym.symbolLayer(0)
        sl.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def style_row_frame(layer: QgsVectorLayer):
    sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",
        "outline_color": "160,160,160,255",
        "outline_width": "0.35",
        "outline_style": "solid",
    })
    try:
        sym.setOutputUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def style_column_frame(layer: QgsVectorLayer):
    style_row_frame(layer)


# ----------------------------------------------------------
# COLUMN CHART (keep as-is)
# ----------------------------------------------------------
def style_column_bars(layer: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},220",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        cats.append(QgsRendererCategory(key, sym, key))
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def style_column_labels(layer: QgsVectorLayer):
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # landkreis number below bar
    pal_num = QgsPalLayerSettings()
    pal_num.enabled = True
    pal_num.isExpression = True
    pal_num.fieldName = 'CASE WHEN "kind" = \'landkreis_label\' THEN to_string("landkreis_number") ELSE NULL END'
    try:
        pal_num.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_num = QgsTextFormat()
    fmt_num.setFont(QFont("Arial", 7))
    fmt_num.setSize(7)
    fmt_num.setColor(QColor(0, 0, 0))
    buf_num = QgsTextBufferSettings()
    buf_num.setEnabled(False)
    fmt_num.setBuffer(buf_num)
    pal_num.setFormat(fmt_num)

    r_num = QgsRuleBasedLabeling.Rule(pal_num)
    r_num.setFilterExpression("\"kind\" = 'landkreis_label'")
    root_rule.appendChild(r_num)

    # value label above bar
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "kind" = \'value_label\' '
        'THEN format_number("total_kw" / 1000.0, 1) '
        'ELSE NULL END'
    )
    try:
        pal_val.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_val = QgsTextFormat()
    fmt_val.setFont(QFont("Arial", 7))
    fmt_val.setSize(7)
    fmt_val.setColor(QColor(0, 0, 0))
    buf_val = QgsTextBufferSettings()
    buf_val.setEnabled(False)
    fmt_val.setBuffer(buf_val)
    pal_val.setFormat(fmt_val)

    r_val = QgsRuleBasedLabeling.Rule(pal_val)
    r_val.setFilterExpression("\"kind\" = 'value_label'")
    root_rule.appendChild(r_val)

    # title
    pal_title = QgsPalLayerSettings()
    pal_title.enabled = True
    pal_title.isExpression = True
    pal_title.fieldName = (
        'CASE WHEN "kind" = \'title\' '
        'THEN coalesce("text", "year_bin_label") '
        'ELSE NULL END'
    )
    try:
        pal_title.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_title = QgsTextFormat()
    fmt_title.setFont(QFont("Arial", 9, QFont.Bold))
    fmt_title.setSize(9)
    fmt_title.setColor(QColor(0, 0, 0))
    buf_title = QgsTextBufferSettings()
    buf_title.setEnabled(False)
    fmt_title.setBuffer(buf_title)
    pal_title.setFormat(fmt_title)

    r_title = QgsRuleBasedLabeling.Rule(pal_title)
    r_title.setFilterExpression("\"kind\" = 'title'")
    root_rule.appendChild(r_title)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# YEAR HEADING (match 1_style)
# ----------------------------------------------------------
def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label: str, per_bin_mw: float):
    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    pr = lyr.dataProvider()

    X_MAIN, Y_MAIN = 10.8, 51.7
    X_SUB, Y_SUB = 11.4, 51.6

    feats = []

    f_main = QgsFeature(lyr.fields())
    f_main.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_MAIN, Y_MAIN)))
    f_main["kind"] = "main"
    f_main["label"] = label
    feats.append(f_main)

    sub_txt = f"Installed Power: {per_bin_mw:,.1f} MW" if per_bin_mw is not None else "Installed Power: n/a"
    f_sub = QgsFeature(lyr.fields())
    f_sub.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_SUB, Y_SUB)))
    f_sub["kind"] = "sub"
    f_sub["label"] = sub_txt
    feats.append(f_sub)

    pr.addFeatures(feats)
    lyr.updateExtents()

    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    pal_m = QgsPalLayerSettings()
    pal_m.enabled = True
    pal_m.isExpression = True
    pal_m.fieldName = 'CASE WHEN "kind" = \'main\' THEN "label" ELSE NULL END'
    try:
        pal_m.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_m = QgsTextFormat()
    fmt_m.setFont(QFont("Arial", 20, QFont.Bold))
    fmt_m.setSize(20)
    fmt_m.setColor(QColor(0, 0, 0))
    bufm = QgsTextBufferSettings()
    bufm.setEnabled(False)
    fmt_m.setBuffer(bufm)
    pal_m.setFormat(fmt_m)

    r_m = QgsRuleBasedLabeling.Rule(pal_m)
    r_m.setFilterExpression("\"kind\" = 'main'")
    root_rule.appendChild(r_m)

    pal_s = QgsPalLayerSettings()
    pal_s.enabled = True
    pal_s.isExpression = True
    pal_s.fieldName = 'CASE WHEN "kind" = \'sub\' THEN "label" ELSE NULL END'
    try:
        pal_s.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt_s = QgsTextFormat()
    fmt_s.setFont(QFont("Arial", 12, QFont.Bold))
    fmt_s.setSize(12)
    fmt_s.setColor(QColor(60, 60, 60))
    bufs = QgsTextBufferSettings()
    bufs.setEnabled(False)
    fmt_s.setBuffer(bufs)
    pal_s.setFormat(fmt_s)

    r_s = QgsRuleBasedLabeling.Rule(pal_s)
    r_s.setFilterExpression("\"kind\" = 'sub'")
    root_rule.appendChild(r_s)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

    QgsProject.instance().addMapLayer(lyr, False)
    parent_group.addLayer(lyr)


# ----------------------------------------------------------
# LANDKREIS NUMBERING (keep as-is)
# ----------------------------------------------------------
def style_kreis_number_points_layer(lyr: QgsVectorLayer):
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = 'to_string("num")'
    try:
        pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 10, QFont.Bold))
    fmt.setSize(10)
    fmt.setColor(QColor(0, 0, 0))

    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.8)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)

    pal.setFormat(fmt)

    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_kreis_number_list_layer(lyr: QgsVectorLayer):
    sym = QgsMarkerSymbol.createSimple({
        "name": "square",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = '"label"'
    try:
        pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 7))
    fmt.setSize(7)
    fmt.setColor(QColor(0, 0, 0))

    buf = QgsTextBufferSettings()
    buf.setEnabled(False)
    fmt.setBuffer(buf)

    pal.setFormat(fmt)

    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


# ----------------------------------------------------------
# OPTIONAL HUD NAMES (keep as-is)
# ----------------------------------------------------------
def add_landkreis_hud_names(parent_group: QgsLayerTreeGroup):
    if not LOAD_HUD_NAMES:
        return

    if not CENTERS_PATH.exists():
        print(f"[WARN] CENTERS_PATH not found (HUD names skipped): {CENTERS_PATH}")
        return

    centers = QgsVectorLayer(str(CENTERS_PATH), "thueringen_centers_for_hud", "ogr")
    if not centers.isValid():
        print("[WARN] Could not load centers layer for HUD names.")
        return

    fields = [f.name() for f in centers.fields()]

    num_col = None
    for c in ["num", "kreis_number", "landkreis_number", "number", "kreis_num", "lk_number"]:
        if c in fields:
            num_col = c
            break

    name_col = None
    for c in ["kreis_name", "landkreis_name", "name"]:
        if c in fields:
            name_col = c
            break

    slug_col = None
    for c in ["kreis_slug", "landkreis_slug", "slug", "kreis_key"]:
        if c in fields:
            slug_col = c
            break

    if name_col is None:
        print("[WARN] Centers layer has no name column for HUD names.")
        return

    items = []
    for ft in centers.getFeatures():
        try:
            n = int(ft[num_col]) if num_col else None
        except Exception:
            n = None
        nm = str(ft[name_col]) if ft[name_col] is not None else ""
        sl = str(ft[slug_col]) if slug_col else ""
        if nm.strip():
            items.append((n, nm, sl))

    items.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 999, t[1]))

    if all(t[0] is None for t in items):
        items = [(i + 1, nm, sl) for i, (_n, nm, sl) in enumerate(items)]

    col_limits = [8, 8, 7]
    X_COLS = [13.00, 13.60, 14.20]
    Y_TOP = 51.80
    DY = -0.045

    uri = (
        "Point?crs=EPSG:4326"
        "&field=label:string(200)"
    )
    lyr = QgsVectorLayer(uri, "thueringen_landkreis_hud_names", "memory")
    pr = lyr.dataProvider()

    feats = []
    idx0 = 0
    for col_i, cnt in enumerate(col_limits):
        x = X_COLS[col_i]
        for j in range(cnt):
            if idx0 >= len(items):
                break
            n, nm, _sl = items[idx0]
            idx0 += 1

            txt = f"{n:02d}  {nm}" if n is not None else nm
            y = Y_TOP + j * DY

            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            f["label"] = txt
            feats.append(f)

    pr.addFeatures(feats)
    lyr.updateExtents()

    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.fieldName = "label"
    try:
        pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 6.5))
    fmt.setSize(6.5)
    fmt.setColor(QColor(0, 0, 0))

    buf = QgsTextBufferSettings()
    buf.setEnabled(False)
    fmt.setBuffer(buf)

    pal.setFormat(fmt)

    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

    QgsProject.instance().addMapLayer(lyr, False)
    parent_group.addLayer(lyr)


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
def main():
    if not ROOT_DIR.exists():
        print(f"[ERROR] ROOT_DIR does not exist: {ROOT_DIR}")
        return

    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    group = ensure_group(root, GROUP_NAME)

    # Legends first
    if LOAD_ENERGY_LEGEND and ENERGY_LEGEND_PATH.exists():
        legend = QgsVectorLayer(str(ENERGY_LEGEND_PATH), "energy_legend", "ogr")
        if legend.isValid():
            style_energy_legend_layer(legend)
            proj.addMapLayer(legend, False)
            group.addLayer(legend)
    elif LOAD_ENERGY_LEGEND:
        print(f"[WARN] ENERGY_LEGEND_PATH not found: {ENERGY_LEGEND_PATH}")

    if LOAD_PIE_SIZE_LEGEND and PIE_SIZE_LEGEND_CIRCLES_PATH.exists():
        pie_leg_circles = QgsVectorLayer(str(PIE_SIZE_LEGEND_CIRCLES_PATH), "pie_size_legend_circles", "ogr")
        if pie_leg_circles.isValid():
            style_pie_size_legend_circles_layer(pie_leg_circles)
            proj.addMapLayer(pie_leg_circles, False)
            group.addLayer(pie_leg_circles)
    elif LOAD_PIE_SIZE_LEGEND:
        print(f"[WARN] PIE_SIZE_LEGEND_CIRCLES_PATH not found: {PIE_SIZE_LEGEND_CIRCLES_PATH}")

    if LOAD_PIE_SIZE_LEGEND and PIE_SIZE_LEGEND_LABELS_PATH.exists():
        pie_leg_labels = QgsVectorLayer(str(PIE_SIZE_LEGEND_LABELS_PATH), "pie_size_legend_labels", "ogr")
        if pie_leg_labels.isValid():
            style_pie_size_legend_labels_layer(pie_leg_labels)
            proj.addMapLayer(pie_leg_labels, False)
            group.addLayer(pie_leg_labels)
    elif LOAD_PIE_SIZE_LEGEND:
        print(f"[WARN] PIE_SIZE_LEGEND_LABELS_PATH not found: {PIE_SIZE_LEGEND_LABELS_PATH}")

    if LOAD_LEGEND_FRAMES and LEGEND_FRAMES_PATH.exists():
        legend_frames = QgsVectorLayer(str(LEGEND_FRAMES_PATH), "legend_frames", "ogr")
        if legend_frames.isValid():
            style_legend_frames_layer(legend_frames)
            proj.addMapLayer(legend_frames, False)
            group.addLayer(legend_frames)
    elif LOAD_LEGEND_FRAMES:
        print(f"[WARN] LEGEND_FRAMES_PATH not found: {LEGEND_FRAMES_PATH}")

    # Landkreis numbering
    if LOAD_NUMBER_POINTS and NUMBER_POINTS_PATH.exists():
        num_pts = QgsVectorLayer(str(NUMBER_POINTS_PATH), "thueringen_landkreis_numbers", "ogr")
        if num_pts.isValid():
            style_kreis_number_points_layer(num_pts)
            proj.addMapLayer(num_pts, False)
            group.addLayer(num_pts)
    elif LOAD_NUMBER_POINTS:
        print(f"[WARN] Number points not found: {NUMBER_POINTS_PATH}")

    if LOAD_NUMBER_LIST and NUMBER_LIST_PATH.exists():
        num_list = QgsVectorLayer(str(NUMBER_LIST_PATH), "thueringen_landkreis_number_list", "ogr")
        if num_list.isValid():
            style_kreis_number_list_layer(num_list)
            proj.addMapLayer(num_list, False)
            group.addLayer(num_list)
    elif LOAD_NUMBER_LIST:
        print(f"[WARN] Number list not found: {NUMBER_LIST_PATH}")

    add_landkreis_hud_names(group)

    chart_exists = CHART_PATH.exists()

    # period MW from cumulative row chart
    per_bin_mw = {}
    if chart_exists:
        try:
            with open(str(CHART_PATH), "r", encoding="utf-8") as f:
                chart = json.load(f)

            cum_kw = {}
            for feat in chart.get("features", []):
                props = feat.get("properties", {})
                slug = props.get("year_bin_slug")
                if not slug or slug in {"title", "unit"}:
                    continue
                if not is_anchor_one(props.get("value_anchor")):
                    continue
                try:
                    cum_kw[slug] = float(props.get("total_kw", 0.0))
                except Exception:
                    continue

            prev = None
            for slug in YEAR_SLUGS:
                if slug not in cum_kw:
                    continue
                if prev is None:
                    period_kw = cum_kw[slug]
                else:
                    period_kw = cum_kw[slug] - cum_kw.get(prev, 0.0)
                per_bin_mw[slug] = period_kw / 1000.0
                prev = slug

            print(f"[INFO] Loaded PERIOD Installed Power (MW) for {len(per_bin_mw)} bins.")
        except Exception as e:
            print(f"[WARN] Could not compute per_bin_mw: {e}")
            per_bin_mw = {}

    for slug in YEAR_SLUGS:
        bin_group = ensure_group(group, YEAR_LABEL_MAP[slug])

        # pie polygons
        pie_path = ROOT_DIR / slug / f"thueringen_landkreis_pie_{slug}.geojson"
        if pie_path.exists():
            lyr = QgsVectorLayer(str(pie_path), f"thueringen_landkreis_pie_{slug}", "ogr")
            if lyr.isValid():
                proj.addMapLayer(lyr, False)
                bin_group.addLayer(lyr)
                style_pie_polygons(lyr)
        else:
            print(f"[WARN] Pie polygons missing for {slug}: {pie_path.name}")

        # row chart
        if chart_exists:
            chart_lyr = QgsVectorLayer(str(CHART_PATH), f"thueringen_rowChart_{slug}", "ogr")
            if chart_lyr.isValid():
                idx = YEAR_SLUGS.index(slug)
                allowed = YEAR_SLUGS[: idx + 1]
                allowed_str = ",".join(f"'{s}'" for s in allowed)
                expr = f"(\"year_bin_slug\" IN ({allowed_str}) OR \"year_bin_slug\" IN ('title','unit'))"
                chart_lyr.setSubsetString(expr)
                style_row_chart(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)

        # row guides
        if LOAD_GUIDE_LINES and GUIDES_PATH.exists():
            guides_lyr = QgsVectorLayer(str(GUIDES_PATH), f"thueringen_rowGuides_{slug}", "ogr")
            if guides_lyr.isValid():
                idx = YEAR_SLUGS.index(slug)
                allowed = YEAR_SLUGS[: idx + 1]
                allowed_str = ",".join(f"'{s}'" for s in allowed)
                guides_lyr.setSubsetString(f"\"year_bin_slug\" IN ({allowed_str})")
                style_row_guides(guides_lyr)
                proj.addMapLayer(guides_lyr, False)
                bin_group.addLayer(guides_lyr)

        # row frame
        if LOAD_ROW_FRAME and FRAME_PATH.exists():
            frame_lyr = QgsVectorLayer(str(FRAME_PATH), f"thueringen_rowFrame_{slug}", "ogr")
            if frame_lyr.isValid():
                style_row_frame(frame_lyr)
                proj.addMapLayer(frame_lyr, False)
                bin_group.addLayer(frame_lyr)

        # column bars
        if COL_BARS_PATH.exists():
            col_bars = QgsVectorLayer(str(COL_BARS_PATH), f"thueringen_colBars_{slug}", "ogr")
            if col_bars.isValid():
                col_bars.setSubsetString(f"\"year_bin_slug\" = '{slug}'")
                style_column_bars(col_bars)
                proj.addMapLayer(col_bars, False)
                bin_group.addLayer(col_bars)
        else:
            print(f"[WARN] Column bars not found: {COL_BARS_PATH}")

        # column labels
        if COL_LABELS_PATH.exists():
            col_lbl = QgsVectorLayer(str(COL_LABELS_PATH), f"thueringen_colLabels_{slug}", "ogr")
            if col_lbl.isValid():
                col_lbl.setSubsetString(
                    f"(\"year_bin_slug\" = '{slug}' OR \"year_bin_slug\" = 'landkreis_title')"
                )
                style_column_labels(col_lbl)
                proj.addMapLayer(col_lbl, False)
                bin_group.addLayer(col_lbl)
        else:
            print(f"[WARN] Column labels not found: {COL_LABELS_PATH}")

        # column frame
        if LOAD_COLUMN_FRAME and COL_FRAME_PATH.exists():
            col_frame = QgsVectorLayer(str(COL_FRAME_PATH), f"thueringen_colFrame_{slug}", "ogr")
            if col_frame.isValid():
                style_column_frame(col_frame)
                proj.addMapLayer(col_frame, False)
                bin_group.addLayer(col_frame)

        # heading
        add_year_heading(bin_group, slug, YEAR_LABEL_MAP[slug], per_bin_mw.get(slug))

    print("[DONE] Thüringen statewise Landkreis pies (yearly) loaded and styled.")


main()