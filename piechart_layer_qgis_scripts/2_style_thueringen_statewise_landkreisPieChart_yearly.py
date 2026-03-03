# Filename: 2_style_thueringen_statewise_landkreisPieChart_yearly.py
# Purpose:
#   Thüringen-only QGIS loader & styler for statewise Landkreis yearly pie charts.
#   - Loads a SINGLE Thüringen Landkreis pie layer per bin
#   - Loads Thüringen cumulative ROW chart (+ optional guide lines + frame) created by step2_5
#   - Loads Thüringen energy legend created by step2_5
#   - Loads Thüringen Landkreis numbering:
#       * Numbers on map (inside polygons) via NUMBER_POINTS_PATH
#       * Right-side list via NUMBER_LIST_PATH
#
# Notes:
#   - Row chart unit stays in MW.
#   - MW is shown as a separate POINT (year_bin_slug='unit') aligned with the numbers column,
#     similar to the Germany setup.
#
# QGIS 3.10 SAFE — rule-based labels where needed.

from pathlib import Path
import json

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
#               PATHS (THUERINGEN)
# ----------------------------------------------------------
ROOT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_statewise_landkreis_pies_yearly"
)

CHART_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart_guides.geojson"
FRAME_PATH = ROOT_DIR / "thueringen_landkreis_yearly_totals_chart_frame.geojson"

LEGEND_PATH = ROOT_DIR / "thueringen_landkreis_energy_legend_points.geojson"

# Landkreis numbering layers created by step2_5
NUMBER_POINTS_PATH = ROOT_DIR / "thueringen_landkreis_number_points.geojson"
NUMBER_LIST_PATH = ROOT_DIR / "thueringen_landkreis_number_list_points.geojson"

GROUP_NAME = "thueringen_statewise_landkreis_pies (yearly)"

NUMBER_POINTS_PATH = ROOT_DIR / "thueringen_landkreis_number_points.geojson"
NUMBER_LIST_PATH = ROOT_DIR / "thueringen_landkreis_number_list_points.geojson"

# Column chart layers created by step2_5
COL_BARS_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_bars.geojson"
COL_LABELS_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_labels.geojson"

# step0 centers file (for Landkreis HUD names)
CENTERS_PATH = ROOT_DIR.parent / "thueringen_landkreis_centers" / "thueringen_landkreis_centers.geojson"

COL_FRAME_PATH = ROOT_DIR / "thu_landkreis_totals_columnChart_frame.geojson"

# ----------------------------------------------------------
#                 SETTINGS
# ----------------------------------------------------------
LOAD_GUIDE_LINES = True
LOAD_ROW_FRAME = True


# ----------------------------------------------------------
#                 YEAR BINS
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
#                 COLORS
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


def style_pie_polygons(layer: QgsVectorLayer):
    """Categorized fill color by energy_type."""
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0"
        })
        cats.append(QgsRendererCategory(key, sym, key))
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ENERGY LEGEND
# ----------------------------------------------------------
def style_energy_legend(layer: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "size": "3.0",
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        cats.append(QgsRendererCategory(key, sym, key))

    note = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    cats.append(QgsRendererCategory("legend_note", note, "legend_note"))

    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    def add_label_rule(filter_expr: str, x_offset: float):
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.fieldName = "legend_label"
        pal.placement = QgsPalLayerSettings.OverPoint
        pal.xOffset = x_offset
        pal.yOffset = 0.0

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 8))
        fmt.setSize(8)
        fmt.setColor(QColor(0, 0, 0))

        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)

        pal.setFormat(fmt)

        rule = QgsRuleBasedLabeling.Rule(pal)
        rule.setFilterExpression(filter_expr)
        root_rule.appendChild(rule)

    add_label_rule('"legend_label" = \'Photovoltaics\'', 12.5)
    add_label_rule('"legend_label" = \'Onshore Wind Energy\'', 18.0)
    add_label_rule('"legend_label" = \'Hydropower\'', 12.5)
    add_label_rule('"legend_label" = \'Biogas\'', 9.0)
    add_label_rule('"legend_label" = \'Battery\'', 9.0)
    add_label_rule('"legend_label" = \'Others\'', 9.0)
    add_label_rule('"energy_type" = \'legend_note\'', 6.0)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ROW CHART STYLING (MW, unit as separate point)
# ----------------------------------------------------------
def style_row_chart(layer: QgsVectorLayer):
    """
    ROW chart styling:
      - stacked bars: polygons categorized by energy_type
      - year labels: label_anchor = 1 (points)
      - values: value_anchor = 1 (points) -> MW number only (no suffix)
      - title: year_bin_slug = 'title' (point)
      - unit:  year_bin_slug = 'unit'  (point) -> shows "MW" once
    """
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
        layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    else:
        sym = QgsFillSymbol.createSimple({"color": "200,200,200,200"})
        layer.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # YEAR LABELS (left points)
    pal_year = QgsPalLayerSettings()
    pal_year.enabled = True
    pal_year.isExpression = True
    pal_year.fieldName = 'CASE WHEN "label_anchor" = 1 THEN "year_bin_label" ELSE NULL END'
    pal_year.placement = QgsPalLayerSettings.OverPoint

    fmt_year = QgsTextFormat()
    fmt_year.setFont(QFont("Arial", 7))
    fmt_year.setSize(7)
    fmt_year.setColor(QColor(0, 0, 0))
    buf_year = QgsTextBufferSettings()
    buf_year.setEnabled(False)
    fmt_year.setBuffer(buf_year)
    pal_year.setFormat(fmt_year)

    r_year = QgsRuleBasedLabeling.Rule(pal_year)
    r_year.setFilterExpression('"label_anchor" = 1')
    root_rule.appendChild(r_year)

    # VALUE LABELS (right points) -> MW number only
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000.0, 1) '
        'ELSE NULL END'
    )
    pal_val.placement = QgsPalLayerSettings.OverPoint

    fmt_val = QgsTextFormat()
    fmt_val.setFont(QFont("Arial", 7))
    fmt_val.setSize(7)
    fmt_val.setColor(QColor(0, 0, 0))
    buf_val = QgsTextBufferSettings()
    buf_val.setEnabled(False)
    fmt_val.setBuffer(buf_val)
    pal_val.setFormat(fmt_val)

    r_val = QgsRuleBasedLabeling.Rule(pal_val)
    r_val.setFilterExpression('"value_anchor" = 1')
    root_rule.appendChild(r_val)

    # TITLE
    pal_title = QgsPalLayerSettings()
    pal_title.enabled = True
    pal_title.isExpression = True
    pal_title.fieldName = 'CASE WHEN "year_bin_slug" = \'title\' THEN "year_bin_label" ELSE NULL END'
    pal_title.placement = QgsPalLayerSettings.OverPoint

    fmt_title = QgsTextFormat()
    fmt_title.setFont(QFont("Arial", 9))
    fmt_title.setSize(9)
    fmt_title.setColor(QColor(0, 0, 0))
    buf_title = QgsTextBufferSettings()
    buf_title.setEnabled(False)
    fmt_title.setBuffer(buf_title)
    pal_title.setFormat(fmt_title)

    r_title = QgsRuleBasedLabeling.Rule(pal_title)
    r_title.setFilterExpression('"year_bin_slug" = \'title\'')
    root_rule.appendChild(r_title)

    # UNIT (MW) as separate point
    pal_unit = QgsPalLayerSettings()
    pal_unit.enabled = True
    pal_unit.isExpression = True
    pal_unit.fieldName = 'CASE WHEN "year_bin_slug" = \'unit\' THEN "year_bin_label" ELSE NULL END'
    pal_unit.placement = QgsPalLayerSettings.OverPoint

    fmt_unit = QgsTextFormat()
    fmt_unit.setFont(QFont("Arial", 9, QFont.Bold))
    fmt_unit.setSize(9)
    fmt_unit.setColor(QColor(0, 0, 0))
    buf_unit = QgsTextBufferSettings()
    buf_unit.setEnabled(False)
    fmt_unit.setBuffer(buf_unit)
    pal_unit.setFormat(fmt_unit)

    r_unit = QgsRuleBasedLabeling.Rule(pal_unit)
    r_unit.setFilterExpression('"year_bin_slug" = \'unit\'')
    root_rule.appendChild(r_unit)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def style_row_guides(layer: QgsVectorLayer):
    """Dashed guide lines for row chart."""
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
    """Single rectangle outline frame (no fill)."""
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
# COLUMN CHART STYLING (Landkreis, stacked bars + labels)
# ----------------------------------------------------------
def style_column_bars(layer: QgsVectorLayer):
    """Stacked column bars: categorized fill by energy_type."""
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
    """Labels for column chart: landkreis number + value + titles."""
    # invisible marker
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

    # Landkreis number under each column
    pal_num = QgsPalLayerSettings()
    pal_num.enabled = True
    pal_num.isExpression = True
    pal_num.fieldName = 'CASE WHEN "kind" = \'landkreis_label\' THEN to_string("landkreis_number") ELSE NULL END'
    pal_num.placement = QgsPalLayerSettings.OverPoint

    fmt_num = QgsTextFormat()
    fmt_num.setFont(QFont("Arial", 7))
    fmt_num.setSize(7)
    fmt_num.setColor(QColor(0, 0, 0))
    buf_num = QgsTextBufferSettings()
    buf_num.setEnabled(False)
    fmt_num.setBuffer(buf_num)
    pal_num.setFormat(fmt_num)

    r_num = QgsRuleBasedLabeling.Rule(pal_num)
    r_num.setFilterExpression('"kind" = \'landkreis_label\'')
    root_rule.appendChild(r_num)

    # Value label above bar (MW)
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "kind" = \'value_label\' '
        'THEN format_number("total_kw" / 1000.0, 1) '
        'ELSE NULL END'
    )
    pal_val.placement = QgsPalLayerSettings.OverPoint

    fmt_val = QgsTextFormat()
    fmt_val.setFont(QFont("Arial", 7))
    fmt_val.setSize(7)
    fmt_val.setColor(QColor(0, 0, 0))
    buf_val = QgsTextBufferSettings()
    buf_val.setEnabled(False)
    fmt_val.setBuffer(buf_val)
    pal_val.setFormat(fmt_val)

    r_val = QgsRuleBasedLabeling.Rule(pal_val)
    r_val.setFilterExpression('"kind" = \'value_label\'')
    root_rule.appendChild(r_val)

    # Title label(s): use "text" if present, else year_bin_label
    pal_title = QgsPalLayerSettings()
    pal_title.enabled = True
    pal_title.isExpression = True
    pal_title.fieldName = (
        'CASE WHEN "kind" = \'title\' '
        'THEN coalesce("text", "year_bin_label") '
        'ELSE NULL END'
    )
    pal_title.placement = QgsPalLayerSettings.OverPoint

    fmt_title = QgsTextFormat()
    fmt_title.setFont(QFont("Arial", 9, QFont.Bold))
    fmt_title.setSize(9)
    fmt_title.setColor(QColor(0, 0, 0))
    buf_title = QgsTextBufferSettings()
    buf_title.setEnabled(False)
    fmt_title.setBuffer(buf_title)
    pal_title.setFormat(fmt_title)

    r_title = QgsRuleBasedLabeling.Rule(pal_title)
    r_title.setFilterExpression('"kind" = \'title\'')
    root_rule.appendChild(r_title)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

# ----------------------------------------------------------
# YEAR HEADING (main + Installed Power: X MW)
# ----------------------------------------------------------
def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label: str, per_bin_mw: float):
    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    pr = lyr.dataProvider()

    # Thüringen heading coordinates (edit freely)
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
    pal_m.placement = QgsPalLayerSettings.OverPoint

    fmt_m = QgsTextFormat()
    fmt_m.setFont(QFont("Arial", 20, QFont.Bold))
    fmt_m.setSize(20)
    fmt_m.setColor(QColor(0, 0, 0))
    bufm = QgsTextBufferSettings()
    bufm.setEnabled(False)
    fmt_m.setBuffer(bufm)
    pal_m.setFormat(fmt_m)

    r_m = QgsRuleBasedLabeling.Rule(pal_m)
    r_m.setFilterExpression('"kind" = \'main\'')
    root_rule.appendChild(r_m)

    pal_s = QgsPalLayerSettings()
    pal_s.enabled = True
    pal_s.isExpression = True
    pal_s.fieldName = 'CASE WHEN "kind" = \'sub\' THEN "label" ELSE NULL END'
    pal_s.placement = QgsPalLayerSettings.OverPoint

    fmt_s = QgsTextFormat()
    fmt_s.setFont(QFont("Arial", 12, QFont.Bold))
    fmt_s.setSize(12)
    fmt_s.setColor(QColor(60, 60, 60))
    bufs = QgsTextBufferSettings()
    bufs.setEnabled(False)
    fmt_s.setBuffer(bufs)
    pal_s.setFormat(fmt_s)

    r_s = QgsRuleBasedLabeling.Rule(pal_s)
    r_s.setFilterExpression('"kind" = \'sub\'')
    root_rule.appendChild(r_s)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

    QgsProject.instance().addMapLayer(lyr, False)
    parent_group.addLayer(lyr)


# ----------------------------------------------------------
# LANDKREIS NUMBERING (MAP + RIGHT LIST)
# ----------------------------------------------------------
def style_kreis_number_points_layer(lyr: QgsVectorLayer):
    """Numbers inside Thüringen Landkreis polygons."""
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
    pal.placement = QgsPalLayerSettings.OverPoint

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
    """Right-side list: one text line per Landkreis."""
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
    pal.placement = QgsPalLayerSettings.OverPoint

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
# HUD: LANDKREIS NAMES (top-right, 3 columns: 8-8-7)
# ----------------------------------------------------------
def add_landkreis_hud_names(parent_group: QgsLayerTreeGroup):
    """
    Draw Landkreis names at top-right as 3 columns (8-8-7).
    Uses CENTERS_PATH attributes for stable numbering + names.
    """
    if not CENTERS_PATH.exists():
        print(f"[WARN] CENTERS_PATH not found (HUD names skipped): {CENTERS_PATH}")
        return

    centers = QgsVectorLayer(str(CENTERS_PATH), "thueringen_centers_for_hud", "ogr")
    if not centers.isValid():
        print("[WARN] Could not load centers layer for HUD names.")
        return

    fields = [f.name() for f in centers.fields()]

    # Detect schema
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

    # Sort: by number if possible, else by name
    items.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 999, t[1]))
    
    # Fallback numbering if centers file has no usable number column
    if all(t[0] is None for t in items):
        items = [(i + 1, nm, sl) for i, (_n, nm, sl) in enumerate(items)]

    # 3 columns: 8 / 8 / 7
    col_limits = [8, 8, 7]

    # ---- POSITION (tune these freely) ----
    X_COLS = [13.00, 13.60, 14.20]  # 3 anchor X positions (top-right)
    Y_TOP = 51.80                   # start Y
    DY = -0.045                     # line spacing

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

            # Keep it compact: "12  Gotha"
            if n is not None:
                txt = f"{n:02d}  {nm}"
            else:
                txt = nm

            y = Y_TOP + j * DY

            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            f["label"] = txt
            feats.append(f)

    pr.addFeatures(feats)
    lyr.updateExtents()

    # invisible marker + label
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
    pal.placement = QgsPalLayerSettings.OverPoint

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

    # Remove old group for clean reruns
    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    group = ensure_group(root, GROUP_NAME)

    # 1) Energy legend
    if LEGEND_PATH.exists():
        legend = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
        if legend.isValid():
            style_energy_legend(legend)
            proj.addMapLayer(legend, False)
            group.addLayer(legend)
    else:
        print(f"[WARN] LEGEND_PATH not found: {LEGEND_PATH}")

    # 2) Landkreis numbering
    if NUMBER_POINTS_PATH.exists():
        num_pts = QgsVectorLayer(str(NUMBER_POINTS_PATH), "thueringen_landkreis_numbers", "ogr")
        if num_pts.isValid():
            style_kreis_number_points_layer(num_pts)
            proj.addMapLayer(num_pts, False)
            group.addLayer(num_pts)
    else:
        print(f"[WARN] Number points not found: {NUMBER_POINTS_PATH}")

    # 2.5) HUD Landkreis names (top-right, 3 columns)
    add_landkreis_hud_names(group)

    # 3) Chart exists?
    chart_exists = CHART_PATH.exists()
    if not chart_exists:
        print(f"[WARN] CHART_PATH not found: {CHART_PATH}")

    # PERIOD MW (diff of cumulative) from chart GeoJSON (read value_anchor points)
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
                if str(props.get("value_anchor")) != "1":
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

            print(f"[INFO] Loaded PERIOD Installed Power (MW) for {len(per_bin_mw)} bins (diff of cumulative).")
        except Exception as e:
            print(f"[WARN] Could not compute per_bin_mw: {e}")
            per_bin_mw = {}

    # 4) Per-bin loading
    for slug in YEAR_SLUGS:
        bin_group = ensure_group(group, YEAR_LABEL_MAP[slug])

        # Pie polygons
        pie_path = ROOT_DIR / slug / f"thueringen_landkreis_pie_{slug}.geojson"
        if pie_path.exists():
            lyr = QgsVectorLayer(str(pie_path), f"thueringen_landkreis_pie_{slug}", "ogr")
            if lyr.isValid():
                proj.addMapLayer(lyr, False)
                bin_group.addLayer(lyr)
                style_pie_polygons(lyr)
        else:
            print(f"[WARN] Pie polygons missing for {slug}: {pie_path.name}")

        # Row chart subset up to this bin (keep title + unit always)
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

        # Guide lines subset up to this bin
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

        # Frame (single rectangle) — load once per bin group (same layer filtered or not needed)
        if LOAD_ROW_FRAME and FRAME_PATH.exists():
            frame_lyr = QgsVectorLayer(str(FRAME_PATH), f"thueringen_rowFrame_{slug}", "ogr")
            if frame_lyr.isValid():
                style_row_frame(frame_lyr)
                proj.addMapLayer(frame_lyr, False)
                bin_group.addLayer(frame_lyr)
                
        # Column chart bars (cumulative subset up to this bin)
        if COL_BARS_PATH.exists():
            col_bars = QgsVectorLayer(str(COL_BARS_PATH), f"thueringen_colBars_{slug}", "ogr")
            if col_bars.isValid():
                idx = YEAR_SLUGS.index(slug)
                allowed = YEAR_SLUGS[: idx + 1]
                allowed_str = ",".join(f"'{s}'" for s in allowed)

                # show cumulative bins + (optional) nothing else
                col_bars.setSubsetString(f"\"year_bin_slug\" = '{slug}'")

                style_column_bars(col_bars)
                proj.addMapLayer(col_bars, False)
                bin_group.addLayer(col_bars)
        else:
            print(f"[WARN] Column bars not found: {COL_BARS_PATH}")

        # Column chart labels (include title layer 'landkreis_title')
        if COL_LABELS_PATH.exists():
            col_lbl = QgsVectorLayer(str(COL_LABELS_PATH), f"thueringen_colLabels_{slug}", "ogr")
            if col_lbl.isValid():
                idx = YEAR_SLUGS.index(slug)
                allowed = YEAR_SLUGS[: idx + 1]
                allowed_str = ",".join(f"'{s}'" for s in allowed)

                # include per-bin titles + static title slug
                col_lbl.setSubsetString(
                    f"(\"year_bin_slug\" = '{slug}' OR \"year_bin_slug\" = 'landkreis_title')"
                )

                style_column_labels(col_lbl)
                proj.addMapLayer(col_lbl, False)
                bin_group.addLayer(col_lbl)
        else:
            print(f"[WARN] Column labels not found: {COL_LABELS_PATH}")
            
        
        # Column chart frame
        if COL_FRAME_PATH.exists():
            col_frame = QgsVectorLayer(str(COL_FRAME_PATH), f"thueringen_colFrame_{slug}", "ogr")
            if col_frame.isValid():
                style_column_frame(col_frame)
                proj.addMapLayer(col_frame, False)
                bin_group.addLayer(col_frame)

        # Heading (main + Installed Power per 2-year bin)
        add_year_heading(bin_group, slug, YEAR_LABEL_MAP[slug], per_bin_mw.get(slug))

    print("[DONE] Thüringen statewise Landkreis pies (yearly) loaded and styled.")


main()