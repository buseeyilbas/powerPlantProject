# Filename: 1_style_statePieChart_yearly.py
# Purpose : Auto-load & style STATE pies for ALL year bins into nested groups:
#           "state_pies (yearly)" -> <Year bin label> ->
#               - de_state_pie_<bin>   (pie polygons)
#               - de_state_pies_<bin>  (pie centers with state_number)
#               - yearly_rowChart_total_power_<bin> (subset of row chart up to that bin)
#               - yearly_rowChart_guides_<bin>      (dashed guide lines)
#               - state_columnChart_<bin>           (stacked state column chart, per bin)
#           Also load:
#               - energy legend points
#               - optional year overview points

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
    QgsVectorLayerSimpleLabeling,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsProperty,
    QgsMarkerSymbol,
    QgsLineSymbol,
    QgsSingleSymbolRenderer,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsUnitTypes,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsFillSymbol,
)
from qgis.PyQt.QtGui import QColor, QFont


# ---------- SETTINGS ----------
ROOT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly")
GROUP_NAME = "state_pies (yearly)"

SHOW_SLICE_LABELS = False
LOAD_CENTER_POINTS = True
LABEL_CENTER_NUMBERS = True

LOAD_YEARLY_CHART = True
LOAD_GUIDE_LINES = True
LOAD_STATE_COLUMN_CHART = True

LOAD_YEAR_OVERVIEW = True
LOAD_ENERGY_LEGEND = True

# Global chart files
YEARLY_CHART_PATH = ROOT_DIR / "de_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR / "de_yearly_totals_chart_guides.geojson"

# State column chart (stacked) - produced by step1_3 as 2 files
STATE_COL_BARS_PATH   = ROOT_DIR / "de_state_totals_columnChart_bars.geojson"
STATE_COL_LABELS_PATH = ROOT_DIR / "de_state_totals_columnChart_labels.geojson"

# ---------- CHART FRAMES (rectangles) ----------
DRAW_CHART_FRAMES = True

# Row chart frame (adjust freely)
ROW_FRAME = {
    "xmin": -3.75,
    "ymin": 47.25,
    "xmax": 5.80,
    "ymax": 51.75,
}

# Column chart frame (adjust freely)
COL_FRAME = {
    "xmin": 15.95,
    "ymin": 47.15,
    "xmax": 22.10,
    "ymax": 54.45,
}

FRAME_OUTLINE = QColor(150, 150, 150, 255)  # gray
FRAME_WIDTH_MM = 0.4



# Year bins and labels (source of truth)
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

# Slug order for cumulative filtering
YEAR_SLUG_ORDER = [slug for (slug, _label, _y1, _y2) in YEAR_BINS]

# Slice / energy palette (shared)
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

def is_anchor_one(v) -> bool:
    """Robust check: accepts 1, 1.0, '1', '1.0', True."""
    if v is None:
        return False
    try:
        return int(float(v)) == 1
    except Exception:
        return str(v).strip() in {"1", "1.0", "true", "True"}

# PERIOD / CUMULATIVE totals in GW (read from chart points)
PER_BIN_GW = {}
CUM_BIN_GW = {}

try:
    if YEARLY_CHART_PATH.exists():
        with open(str(YEARLY_CHART_PATH), "r", encoding="utf-8") as f:
            chart = json.load(f)

        # Read cumulative totals from value_anchor=1 points
        cum_kw = {}  # slug -> cumulative kW
        for feat in chart.get("features", []):
            props = feat.get("properties", {})
            slug = props.get("year_bin_slug")
            if not slug or slug == "title":
                continue
            if not is_anchor_one(props.get("value_anchor")):
                continue
            val = props.get("total_kw", 0.0)
            try:
                cum_kw[slug] = float(val)
            except Exception:
                continue

        # Store cumulative GW (for headings)
        for slug, val_kw in cum_kw.items():
            try:
                CUM_BIN_GW[slug] = float(val_kw) / 1_000_000.0
            except Exception:
                pass

        # Convert cumulative -> period via diff along YEAR_SLUG_ORDER
        prev = None
        for slug in YEAR_SLUG_ORDER:
            if slug not in cum_kw:
                continue
            if prev is None:
                period_kw = cum_kw[slug]
            else:
                period_kw = cum_kw[slug] - cum_kw.get(prev, 0.0)
            PER_BIN_GW[slug] = float(period_kw) / 1_000_000.0
            prev = slug

        print(f"[INFO] Loaded PERIOD GW for {len(PER_BIN_GW)} bins and CUMULATIVE GW for {len(CUM_BIN_GW)} bins.")
    else:
        print(f"[WARN] YEARLY_CHART_PATH not found: {YEARLY_CHART_PATH}")
except Exception as e:
    print(f"[WARN] Could not compute PER_BIN_GW: {e}")
    PER_BIN_GW = {}



def ensure_group(parent, name: str):
    if isinstance(parent, QgsLayerTreeGroup):
        grp = parent.findGroup(name)
        if grp is None:
            grp = parent.addGroup(name)
        return grp
    grp = root.findGroup(name)
    if grp is None:
        grp = root.addGroup(name)
    return grp


def style_year_overview_layer(lyr: QgsVectorLayer):
    """Overview year labels north of Germany."""
    sym = QgsMarkerSymbol.createSimple(
        {
            "name": "square",
            "size": "0.01",
            "color": "0,0,0,0",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        }
    )
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = '"year_bin_label"'

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 8))
    fmt.setSize(8)
    fmt.setColor(QColor(0, 0, 0))

    buf = QgsTextBufferSettings()
    buf.setEnabled(False)
    fmt.setBuffer(buf)

    pal.setFormat(fmt)

    try:
        pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

def style_state_column_bars_layer(lyr: QgsVectorLayer):
    """
    COLUMN CHART - BARS (POLYGONS):
      - Color polygons by energy_type using PALETTE (same as row chart)
      - Unknown categories -> fully transparent (no gray background)
      - No labels in this layer
    """

    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},220",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
        cats.append(QgsRendererCategory(key, sym, key))

    renderer = QgsCategorizedSymbolRenderer("energy_type", cats)

    # IMPORTANT: make default symbol invisible so "unknown" energy_type doesn't become gray
    default_sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    try:
        renderer.setSourceSymbol(default_sym)  # QGIS 3.x: default symbol
    except Exception:
        pass

    lyr.setRenderer(renderer)

    lyr.setLabelsEnabled(False)
    lyr.triggerRepaint()


def style_state_column_labels_layer(lyr: QgsVectorLayer):
    """
    COLUMN CHART - LABELS (POINTS):
      - kind='state_label'  -> 1..16 (bold)
      - kind='value_label'  -> GW number (1 decimal)
      - kind='title'        -> title text
    """

    # invisible point marker
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

    # (1) state numbers
    st_pal = QgsPalLayerSettings()
    st_pal.enabled = True
    st_pal.isExpression = True
    st_pal.fieldName = (
        "CASE WHEN \"kind\" = 'state_label' THEN to_string(\"state_number\") ELSE NULL END"
    )
    st_fmt = QgsTextFormat()
    st_fmt.setFont(QFont("Arial", 7, QFont.Bold))
    st_fmt.setSize(7)
    st_fmt.setColor(QColor(0, 0, 0))
    st_buf = QgsTextBufferSettings(); st_buf.setEnabled(False)
    st_fmt.setBuffer(st_buf)
    st_pal.setFormat(st_fmt)
    try:
        st_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    st_rule = QgsRuleBasedLabeling.Rule(st_pal)
    st_rule.setFilterExpression("\"kind\" = 'state_label'")
    root_rule.appendChild(st_rule)

    # (2) values (GW, 1 decimal, no suffix)
    val_pal = QgsPalLayerSettings()
    val_pal.enabled = True
    val_pal.isExpression = True
    val_pal.fieldName = (
        "CASE WHEN \"kind\" = 'value_label' THEN format_number(\"total_kw\" / 1000000.0, 1) ELSE NULL END"
    )
    val_fmt = QgsTextFormat()
    val_fmt.setFont(QFont("Arial", 7))
    val_fmt.setSize(7)
    val_fmt.setColor(QColor(0, 0, 0))
    val_buf = QgsTextBufferSettings(); val_buf.setEnabled(False)
    val_fmt.setBuffer(val_buf)
    val_pal.setFormat(val_fmt)
    try:
        val_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    val_rule = QgsRuleBasedLabeling.Rule(val_pal)
    val_rule.setFilterExpression("\"kind\" = 'value_label'")
    root_rule.appendChild(val_rule)

    # (3) title
    title_pal = QgsPalLayerSettings()
    title_pal.enabled = True
    title_pal.isExpression = True
    title_pal.fieldName = (
        "CASE WHEN \"kind\" = 'title' THEN \"year_bin_label\" ELSE NULL END"
    )
    title_fmt = QgsTextFormat()
    title_fmt.setFont(QFont("Arial", 9, QFont.Bold))
    title_fmt.setSize(9)
    title_fmt.setColor(QColor(0, 0, 0))
    title_buf = QgsTextBufferSettings(); title_buf.setEnabled(False)
    title_fmt.setBuffer(title_buf)
    title_pal.setFormat(title_fmt)
    try:
        title_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    title_rule = QgsRuleBasedLabeling.Rule(title_pal)
    title_rule.setFilterExpression("\"kind\" = 'title'")
    root_rule.appendChild(title_rule)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()



def style_state_pie_layer(lyr: QgsVectorLayer):
    """Categorized pie polygons by energy_type; optional anchor labels."""
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple(
            {
                "color": f"{color.red()},{color.green()},{color.blue()},255",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0",
            }
        )
        cats.append(QgsRendererCategory(key, sym, key))
    lyr.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    if SHOW_SLICE_LABELS:
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = True
        pal.fieldName = 'CASE WHEN "label_anchor"=1 THEN "name" ELSE NULL END'

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 9))
        fmt.setSize(9)
        fmt.setColor(QColor(0, 0, 0))

        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)

        pal.setFormat(fmt)

        size_expr = (
            "CASE "
            " WHEN @map_scale <= 1500000 THEN 10 "
            " WHEN @map_scale <= 3000000 THEN 9 "
            " WHEN @map_scale <= 6000000 THEN 8 "
            " ELSE 7 END"
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


def style_center_layer(lyr: QgsVectorLayer, label_numbers: bool = True):
    """
    Style for pie center points:
    - marker invisible
    - state_number labels with per-state offset
    """

    sym = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "size": "2.8",
            "color": "0,0,0,0",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        }
    )
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    if not label_numbers:
        lyr.setLabelsEnabled(False)
        lyr.triggerRepaint()
        return

    def make_rule(filter_expr: str, x_off: float, y_off: float) -> QgsRuleBasedLabeling.Rule:
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
        pal.fieldName = "state_number"

        try:
            pal.placement = QgsPalLayerSettings.OverPoint
        except Exception:
            pass

        pal.xOffset = x_off
        pal.yOffset = y_off

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 9))
        fmt.setSize(9)
        fmt.setColor(QColor(0, 0, 0))

        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)

        pal.setFormat(fmt)

        rule = QgsRuleBasedLabeling.Rule(pal)
        if filter_expr:
            rule.setFilterExpression(filter_expr)
        return rule

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    root_rule.appendChild(make_rule('"state_number" IN (3,5,6)', 0.0, 0.0))  # Berlin, Bremen, Hamburg
    root_rule.appendChild(make_rule('"state_number" = 12', -3.5, -2.0))  # Saarland
    root_rule.appendChild(make_rule('"state_number" IN (1,4,7,8,9,11,13,14,16)', -7.0, -2.5))
    root_rule.appendChild(make_rule('"state_number" = 2', 11.0, 4.0))  # Bayern
    root_rule.appendChild(make_rule('"state_number" IN (10,15)', 9.0, 2.0))

    labeling = QgsRuleBasedLabeling(root_rule)
    lyr.setLabeling(labeling)
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_energy_legend_layer(lyr: QgsVectorLayer):
    """Energy legend layer (colored dots + labels)."""

    cats = []
    for key, color in PALETTE.items():
        sym = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "size": "3.0",
                "color": f"{color.red()},{color.green()},{color.blue()},255",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0",
            }
        )
        cats.append(QgsRendererCategory(key, sym, key))

    note_sym = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "size": "0.01",
            "color": "0,0,0,0",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        }
    )
    cats.append(QgsRendererCategory("legend_note", note_sym, "legend_note"))

    lyr.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

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

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()




def style_yearly_chart_layer(lyr: QgsVectorLayer):
    """
    Styling for the YEARLY ROW chart:
      - stacked bar polygons color-coded by energy_type
      - year labels on left  (POINTs with label_anchor = 1)
      - GW numbers on right (POINTs with value_anchor = 1)  -> NO "GW" suffix
      - title point (year_bin_slug = 'title')
      - unit point  (year_bin_slug = 'unit') -> shows "GW" once
    """

    fields = [f.name() for f in lyr.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

    # Polygons by energy_type
    if energy_field:
        cats = []
        for key, color in PALETTE.items():
            sym = QgsFillSymbol.createSimple(
                {
                    "color": f"{color.red()},{color.green()},{color.blue()},220",
                    "outline_style": "no",
                    "outline_color": "0,0,0,0",
                    "outline_width": "0",
                }
            )
            cats.append(QgsRendererCategory(key, sym, key))
        lyr.setRenderer(QgsCategorizedSymbolRenderer(energy_field, cats))
    else:
        sym = QgsFillSymbol.createSimple(
            {
                "color": "200,200,200,200",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0",
            }
        )
        lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # (1) year labels
    year_pal = QgsPalLayerSettings()
    year_pal.enabled = True
    year_pal.isExpression = True
    year_pal.fieldName = 'CASE WHEN "label_anchor" = 1 THEN "year_bin_label" ELSE NULL END'

    year_fmt = QgsTextFormat()
    year_fmt.setFont(QFont("Arial", 7))
    year_fmt.setSize(7)
    year_fmt.setColor(QColor(0, 0, 0))
    year_buf = QgsTextBufferSettings()
    year_buf.setEnabled(False)
    year_fmt.setBuffer(year_buf)
    year_pal.setFormat(year_fmt)

    try:
        year_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    year_rule = QgsRuleBasedLabeling.Rule(year_pal)
    year_rule.setFilterExpression('"label_anchor" = 1')
    root_rule.appendChild(year_rule)

    # (2) value labels (GW numbers, 2 digits, no suffix)
    value_pal = QgsPalLayerSettings()
    value_pal.enabled = True
    value_pal.isExpression = True
    value_pal.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000000.00, 2) '
        'ELSE NULL END'
    )

    value_fmt = QgsTextFormat()
    value_fmt.setFont(QFont("Arial", 7))
    value_fmt.setSize(7)
    value_fmt.setColor(QColor(0, 0, 0))
    value_buf = QgsTextBufferSettings()
    value_buf.setEnabled(False)
    value_fmt.setBuffer(value_buf)
    value_pal.setFormat(value_fmt)

    try:
        value_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    value_rule = QgsRuleBasedLabeling.Rule(value_pal)
    value_rule.setFilterExpression('"value_anchor" = 1')
    root_rule.appendChild(value_rule)

    # (3) chart title
    title_pal = QgsPalLayerSettings()
    title_pal.enabled = True
    title_pal.isExpression = True
    title_pal.fieldName = 'CASE WHEN "year_bin_slug" = \'title\' THEN "year_bin_label" ELSE NULL END'

    title_fmt = QgsTextFormat()
    title_fmt.setFont(QFont("Arial", 9))
    title_fmt.setSize(9)
    title_fmt.setColor(QColor(0, 0, 0))
    title_buf = QgsTextBufferSettings()
    title_buf.setEnabled(False)
    title_fmt.setBuffer(title_buf)
    title_pal.setFormat(title_fmt)

    try:
        title_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    title_rule = QgsRuleBasedLabeling.Rule(title_pal)
    title_rule.setFilterExpression('"year_bin_slug" = \'title\'')
    root_rule.appendChild(title_rule)

    # (4) unit label ("GW") point
    unit_pal = QgsPalLayerSettings()
    unit_pal.enabled = True
    unit_pal.isExpression = True
    unit_pal.fieldName = 'CASE WHEN "year_bin_slug" = \'unit\' THEN "year_bin_label" ELSE NULL END'

    unit_fmt = QgsTextFormat()
    unit_fmt.setFont(QFont("Arial", 9, QFont.Bold))
    unit_fmt.setSize(9)
    unit_fmt.setColor(QColor(0, 0, 0))
    unit_buf = QgsTextBufferSettings()
    unit_buf.setEnabled(False)
    unit_fmt.setBuffer(unit_buf)
    unit_pal.setFormat(unit_fmt)

    try:
        unit_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    unit_rule = QgsRuleBasedLabeling.Rule(unit_pal)
    unit_rule.setFilterExpression('"year_bin_slug" = \'unit\'')
    root_rule.appendChild(unit_rule)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_yearly_guides_layer(lyr: QgsVectorLayer):
    """Dashed guide lines from bar end to value column (constant thickness)."""
    sym = QgsLineSymbol.createSimple({"color": "0,0,0,120", "width": "0.20", "line_style": "dash"})

    try:
        sym.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    try:
        sl = sym.symbolLayer(0)
        sl.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    lyr.setRenderer(QgsSingleSymbolRenderer(sym))
    lyr.setLabelsEnabled(False)
    lyr.triggerRepaint()


def pretty_year_label(bin_dir: Path) -> str:
    """Try to read a human label from meta JSON. Fallback to slug."""
    slug = bin_dir.name
    meta = bin_dir / f"state_pie_style_meta_{slug}.json"
    if meta.exists():
        try:
            obj = json.loads(meta.read_text(encoding="utf-8"))
            lbl = obj.get("year_bin")
            if isinstance(lbl, str) and lbl.strip():
                return lbl
        except Exception:
            pass

    m = re.match(r"(\d{4})_(\d{4})", slug)
    if m:
        return f"{m.group(1)}–{m.group(2)}"
    if slug == "pre_1990":
        return "≤1990 — Pre-EEG"
    return slug


def bin_sort_key(p: Path):
    """Sort bins naturally (pre_1990 first, then by numeric year)."""
    s = p.name
    if s == "pre_1990":
        return (-1, -1)
    m = re.match(r"(\d{4})_(\d{4})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (9999, s)

def _make_rect_feature(layer: QgsVectorLayer, xmin, ymin, xmax, ymax, kind: str) -> QgsFeature:
    f = QgsFeature(layer.fields())
    ring = [
        QgsPointXY(xmin, ymin),
        QgsPointXY(xmax, ymin),
        QgsPointXY(xmax, ymax),
        QgsPointXY(xmin, ymax),
        QgsPointXY(xmin, ymin),
    ]
    f.setGeometry(QgsGeometry.fromPolygonXY([ring]))
    f["kind"] = kind
    return f


def add_chart_frames(parent_group: QgsLayerTreeGroup):
    """
    Adds ONE memory polygon layer with TWO rectangles:
      - kind='row'    frame for row chart
      - kind='column' frame for column chart
    No inner lines possible (only 2 polygon features).
    """

    if not DRAW_CHART_FRAMES:
        return

    uri = "Polygon?crs=EPSG:4326&field=kind:string(10)&index=yes"
    lyr = QgsVectorLayer(uri, "chart_frames", "memory")
    prov = lyr.dataProvider()

    feats = []
    feats.append(_make_rect_feature(lyr, **ROW_FRAME, kind="row"))
    feats.append(_make_rect_feature(lyr, **COL_FRAME, kind="column"))

    prov.addFeatures(feats)
    lyr.updateExtents()

    # transparent fill + gray outline
    sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",
        "outline_color": f"{FRAME_OUTLINE.red()},{FRAME_OUTLINE.green()},{FRAME_OUTLINE.blue()},{FRAME_OUTLINE.alpha()}",
        "outline_width": str(FRAME_WIDTH_MM),
    })
    try:
        sym.setOutputUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    lyr.setRenderer(QgsSingleSymbolRenderer(sym))
    lyr.setLabelsEnabled(False)
    lyr.triggerRepaint()

    QgsProject.instance().addMapLayer(lyr, False)
    parent_group.addLayer(lyr)


def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label_text: str):
    """
    One in-memory point layer with TWO labels:
      - main year heading (big, bold)
      - subheading: Installed Power for this period (GW)
    """

    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
        "&index=yes"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    prov = lyr.dataProvider()

    # NOTE: You already adjusted these coordinates in your local file.
    # Keep them here exactly as you want:
    X_MAIN = 9.3
    Y_MAIN = 54.9
    X_SUB = 11.8
    Y_SUB = 54.8

    feats = []

    f_main = QgsFeature(lyr.fields())
    f_main.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_MAIN, Y_MAIN)))
    f_main["kind"] = "main"
    f_main["label"] = label_text
    feats.append(f_main)

    f_sub = QgsFeature(lyr.fields())
    f_sub.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_SUB, Y_SUB)))
    f_sub["kind"] = "sub"
    feats.append(f_sub)

    gw_per = PER_BIN_GW.get(slug)
    if gw_per is None:
        sub_text = "Installed Power: n/a"
    else:
        # 2 digits looks clean for headings; change to 1 if you prefer.
        sub_text = f"Installed Power: {gw_per:,.2f} GW"
    f_sub["label"] = sub_text

    prov.addFeatures(feats)
    lyr.updateExtents()

    sym = QgsMarkerSymbol.createSimple(
        {
            "name": "circle",
            "size": "0.01",
            "color": "0,0,0,0",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        }
    )
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # main heading
    pal_main = QgsPalLayerSettings()
    pal_main.enabled = True
    pal_main.isExpression = True
    pal_main.fieldName = 'CASE WHEN "kind" = \'main\' THEN "label" ELSE NULL END'

    fmt_main = QgsTextFormat()
    fmt_main.setFont(QFont("Arial", 18, QFont.Bold))
    fmt_main.setSize(20)
    fmt_main.setColor(QColor(0, 0, 0))
    buf_main = QgsTextBufferSettings()
    buf_main.setEnabled(False)
    fmt_main.setBuffer(buf_main)
    pal_main.setFormat(fmt_main)

    rule_main = QgsRuleBasedLabeling.Rule(pal_main)
    rule_main.setFilterExpression('"kind" = \'main\'')
    root_rule.appendChild(rule_main)

    # subheading
    pal_sub = QgsPalLayerSettings()
    pal_sub.enabled = True
    pal_sub.isExpression = True
    pal_sub.fieldName = 'CASE WHEN "kind" = \'sub\' THEN "label" ELSE NULL END'

    fmt_sub = QgsTextFormat()
    fmt_sub.setFont(QFont("Arial", 12, QFont.Bold))
    fmt_sub.setSize(12)
    fmt_sub.setColor(QColor(60, 60, 60))
    buf_sub = QgsTextBufferSettings()
    buf_sub.setEnabled(False)
    fmt_sub.setBuffer(buf_sub)
    pal_sub.setFormat(fmt_sub)

    rule_sub = QgsRuleBasedLabeling.Rule(pal_sub)
    rule_sub.setFilterExpression('"kind" = \'sub\'')
    root_rule.appendChild(rule_sub)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

    QgsProject.instance().addMapLayer(lyr, False)
    parent_group.addLayer(lyr)


def main():
    if not ROOT_DIR.exists():
        print(f"[ERROR] ROOT_DIR does not exist: {ROOT_DIR}")
        return

    parent_group = ensure_group(root, GROUP_NAME)
    
    
    # frames (row + column)
    add_chart_frames(parent_group)


    # Optional overview layer
    if LOAD_YEAR_OVERVIEW:
        overview_path = ROOT_DIR / "de_year_overview_points.geojson"
        if overview_path.exists():
            ov_lyr = QgsVectorLayer(str(overview_path), "year_overview", "ogr")
            if ov_lyr.isValid():
                style_year_overview_layer(ov_lyr)
                proj.addMapLayer(ov_lyr, False)
                parent_group.addLayer(ov_lyr)

    # Energy legend layer
    if LOAD_ENERGY_LEGEND:
        legend_path = ROOT_DIR / "de_energy_legend_points.geojson"
        if legend_path.exists():
            legend_lyr = QgsVectorLayer(str(legend_path), "energy_legend", "ogr")
            if legend_lyr.isValid():
                style_energy_legend_layer(legend_lyr)
                proj.addMapLayer(legend_lyr, False)
                parent_group.addLayer(legend_lyr)
        else:
            print(f"[WARN] Energy legend file not found: {legend_path}")

    chart_exists = YEARLY_CHART_PATH.exists()

    # All bin directories
    bin_dirs = sorted([p for p in ROOT_DIR.iterdir() if p.is_dir()], key=bin_sort_key)

    for bin_dir in bin_dirs:
        slug = bin_dir.name
        label = pretty_year_label(bin_dir)

        bin_group = ensure_group(parent_group, label)

        # ----- PIE POLYGONS -----
        pie_path = bin_dir / f"de_state_pie_{slug}.geojson"
        if pie_path.exists():
            pie_lyr = QgsVectorLayer(str(pie_path), f"de_state_pie_{slug}", "ogr")
            if pie_lyr.isValid():
                style_state_pie_layer(pie_lyr)
                proj.addMapLayer(pie_lyr, False)
                bin_group.addLayer(pie_lyr)
        else:
            print(f"[WARN] Pie polygons not found for {slug}: {pie_path}")

        # ----- PIE CENTERS -----
        if LOAD_CENTER_POINTS:
            center_path = bin_dir / f"de_state_pies_{slug}.geojson"
            if center_path.exists():
                center_lyr = QgsVectorLayer(str(center_path), f"de_state_pies_{slug}", "ogr")
                if center_lyr.isValid():
                    style_center_layer(center_lyr, LABEL_CENTER_NUMBERS)
                    proj.addMapLayer(center_lyr, False)
                    bin_group.addLayer(center_lyr)
            else:
                print(f"[WARN] Pie centers not found for {slug}: {center_path}")

        # ----- YEARLY ROW CHART (subset) -----
        if LOAD_YEARLY_CHART and chart_exists:
            chart_lyr = QgsVectorLayer(str(YEARLY_CHART_PATH), f"yearly_rowChart_total_power_{slug}", "ogr")
            if chart_lyr.isValid():
                if slug in YEAR_SLUG_ORDER:
                    idx = YEAR_SLUG_ORDER.index(slug)
                    allowed = YEAR_SLUG_ORDER[: idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)
                    expr = f"(\"year_bin_slug\" IN ({allowed_list}) OR \"year_bin_slug\" IN ('title','unit'))"
                    chart_lyr.setSubsetString(expr)

                style_yearly_chart_layer(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)
        elif LOAD_YEARLY_CHART and not chart_exists:
            print(f"[WARN] Global yearly chart file not found: {YEARLY_CHART_PATH}")

        # ----- GUIDE LINES (subset) -----
        if LOAD_GUIDE_LINES and GUIDES_PATH.exists():
            guides_lyr = QgsVectorLayer(str(GUIDES_PATH), f"yearly_rowChart_guides_{slug}", "ogr")
            if guides_lyr.isValid():
                if slug in YEAR_SLUG_ORDER:
                    idx = YEAR_SLUG_ORDER.index(slug)
                    allowed = YEAR_SLUG_ORDER[: idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)
                    guides_lyr.setSubsetString(f"\"year_bin_slug\" IN ({allowed_list})")

                style_yearly_guides_layer(guides_lyr)
                proj.addMapLayer(guides_lyr, False)
                bin_group.addLayer(guides_lyr)


        # ----- STATE COLUMN CHART (subset) -----
        if LOAD_STATE_COLUMN_CHART:
            # BARS
            if not STATE_COL_BARS_PATH.exists():
                print(f"[WARN] STATE_COL_BARS_PATH not found: {STATE_COL_BARS_PATH}")
            else:
                bars_lyr = QgsVectorLayer(str(STATE_COL_BARS_PATH), f"state_columnBars_{slug}", "ogr")
                if not bars_lyr.isValid():
                    print(f"[WARN] Column BARS layer invalid: {STATE_COL_BARS_PATH}")
                else:
                    # bars are per-bin polygons only
                    bars_lyr.setSubsetString(f"\"year_bin_slug\" = '{slug}'")
                    style_state_column_bars_layer(bars_lyr)
                    proj.addMapLayer(bars_lyr, False)
                    bin_group.addLayer(bars_lyr)

            # LABELS (numbers + values + title)
            if not STATE_COL_LABELS_PATH.exists():
                print(f"[WARN] STATE_COL_LABELS_PATH not found: {STATE_COL_LABELS_PATH}")
            else:
                labels_lyr = QgsVectorLayer(str(STATE_COL_LABELS_PATH), f"state_columnLabels_{slug}", "ogr")
                if not labels_lyr.isValid():
                    print(f"[WARN] Column LABELS layer invalid: {STATE_COL_LABELS_PATH}")
                else:
                    # keep current bin labels + the one global title point
                    labels_lyr.setSubsetString(
                        f"(\"year_bin_slug\" = '{slug}' OR \"year_bin_slug\" = 'state_title')"
                    )
                    style_state_column_labels_layer(labels_lyr)
                    proj.addMapLayer(labels_lyr, False)
                    bin_group.addLayer(labels_lyr)
        
        print("[DEBUG] bars fields:", [f.name() for f in bars_lyr.fields()])
        print("[DEBUG] bars featureCount:", bars_lyr.featureCount())


        # ----- YEAR HEADING (BIG TITLE) -----
        add_year_heading(bin_group, slug, label)


main()
