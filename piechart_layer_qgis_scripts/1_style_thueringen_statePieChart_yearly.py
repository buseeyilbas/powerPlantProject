# Filename: 1_style_thueringen_statePieChart_yearly.py
# Purpose : Auto-load & style THUERINGEN STATE pies for ALL year bins into nested groups:
#           "thueringen_state_pies (yearly)" -> <Year bin label> ->
#               - thueringen_state_pie_<bin>   (pie polygons)
#               - thueringen_state_pies_<bin>  (pie center points)
#               - yearly_rowChart_total_power_<bin> (subset of row chart up to that bin)
#               - yearly_rowChart_guides_<bin>      (dashed guide lines)
#           Also load (optional):
#               - Energy legend points (thueringen_energy_legend_points.geojson)
#
# Notes:
# - QGIS 3.10 compatible
# - MW stays (Thüringen scale)

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
    QgsUnitTypes,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
)
from qgis.PyQt.QtGui import QColor, QFont


# ---------- SETTINGS ----------
ROOT_DIR   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_state_pies_yearly")
GROUP_NAME = "thueringen_state_pies (yearly)"

SHOW_SLICE_LABELS    = False
LOAD_CENTER_POINTS   = True
LABEL_CENTER_NUMBERS = False

LOAD_YEARLY_CHART    = True
LOAD_GUIDE_LINES     = True

LOAD_YEAR_OVERVIEW   = False
LOAD_ENERGY_LEGEND   = True

# Global chart files (from step1_5)
YEARLY_CHART_PATH = ROOT_DIR / "thueringen_yearly_totals_chart.geojson"
GUIDES_PATH       = ROOT_DIR / "thueringen_yearly_totals_chart_guides.geojson"

# ---------- CHART FRAME (rectangle) ----------
DRAW_CHART_FRAMES = True

# Row chart frame (you will SHIFT/resize by editing these numbers)
ROW_FRAME = {
    "xmin": 8.25,
    "ymin": 50.23,
    "xmax": 9.85,
    "ymax": 51.22,
}
FRAME_OUTLINE  = QColor(150, 150, 150, 255)
FRAME_WIDTH_MM = 0.4


# Year bins and labels (source of truth)
YEAR_BINS = [
    ("pre_1990",  "≤1990",     None, 1990),
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

YEAR_SLUG_ORDER = [slug for (slug, _label, _y1, _y2) in YEAR_BINS]

# Slice / energy palette
PALETTE = {
    "pv_kw":      QColor(255,255,0,255),
    "battery_kw": QColor(148,87,235,255),
    "wind_kw":    QColor(173,216,230,255),
    "hydro_kw":   QColor(0,0,255,255),
    "biogas_kw":  QColor(0,190,0,255),
    "others_kw":  QColor(158,158,158,255),
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


# PERIOD MW: diff of cumulative totals read from chart point anchors
PER_BIN_MW = {}

try:
    if YEARLY_CHART_PATH.exists():
        with open(str(YEARLY_CHART_PATH), "r", encoding="utf-8") as f:
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
                cum_kw[slug] = float(props.get("total_kw", 0.0) or 0.0)
            except Exception:
                continue

        prev = None
        for slug in YEAR_SLUG_ORDER:
            if slug not in cum_kw:
                continue
            if prev is None:
                period_kw = cum_kw[slug]
            else:
                period_kw = cum_kw[slug] - cum_kw.get(prev, 0.0)

            PER_BIN_MW[slug] = float(period_kw) / 1000.0
            prev = slug

        print(f"[INFO] Loaded PERIOD Installed Power (MW) for {len(PER_BIN_MW)} bins (diff of cumulative).")
    else:
        print(f"[WARN] YEARLY_CHART_PATH not found: {YEARLY_CHART_PATH}")
except Exception as e:
    print(f"[WARN] Could not compute PER_BIN_MW: {e}")
    PER_BIN_MW = {}


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


def style_state_pie_layer(lyr: QgsVectorLayer):
    cats = []
    for key, color in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{color.red()},{color.green()},{color.blue()},255",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        })
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

        try:
            pal.placement = QgsPalLayerSettings.OverPolygon
        except Exception:
            pass

        lyr.setLabelsEnabled(True)
        lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    else:
        lyr.setLabelsEnabled(False)

    lyr.triggerRepaint()


def style_center_layer(lyr: QgsVectorLayer, label_numbers: bool = False):
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "2.8",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0"
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    if not label_numbers:
        lyr.setLabelsEnabled(False)
        lyr.triggerRepaint()
        return

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = False
    pal.fieldName = "state_number"
    try:
        pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", 9))
    fmt.setSize(9)
    fmt.setColor(QColor(0, 0, 0))
    buf = QgsTextBufferSettings()
    buf.setEnabled(False)
    fmt.setBuffer(buf)
    pal.setFormat(fmt)

    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_energy_legend_layer(lyr: QgsVectorLayer):
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

    note_sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
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

    add_label_rule('"legend_label" = \'Photovoltaics\'',        12.5)
    add_label_rule('"legend_label" = \'Onshore Wind Energy\'',  18.0)
    add_label_rule('"legend_label" = \'Hydropower\'',           12.5)
    add_label_rule('"legend_label" = \'Biogas\'',                9.0)
    add_label_rule('"legend_label" = \'Battery\'',               9.0)
    add_label_rule('"legend_label" = \'Others\'',                9.0)
    add_label_rule('"energy_type" = \'legend_note\'',            6.0)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_yearly_chart_layer(lyr: QgsVectorLayer):
    """
    ROW chart styling (MW):
      - stacked polygons by energy_type
      - year labels: label_anchor=1
      - value labels: value_anchor=1 (numbers only)
      - title: year_bin_slug='title'
      - unit: year_bin_slug='unit'  (optional; if your geojson has it)
    """

    fields = [f.name() for f in lyr.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

    if energy_field:
        cats = []
        for key, color in PALETTE.items():
            sym = QgsFillSymbol.createSimple({
                "color": f"{color.red()},{color.green()},{color.blue()},220",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0"
            })
            cats.append(QgsRendererCategory(key, sym, key))
        lyr.setRenderer(QgsCategorizedSymbolRenderer(energy_field, cats))
    else:
        sym = QgsFillSymbol.createSimple({
            "color": "200,200,200,200",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0"
        })
        lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # (1) YEAR labels
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

    # (2) VALUE labels (MW numbers only; unit printed once via 'unit' point if exists)
    value_pal = QgsPalLayerSettings()
    value_pal.enabled = True
    value_pal.isExpression = True
    value_pal.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000.0, 1) '
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

    # (3) TITLE
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

    # (4) unit label ("MW") point
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

    # (4) UNIT point (optional)
    if "year_bin_slug" in fields:
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

    lyr.setRenderer(QgsSingleSymbolRenderer(sym))
    lyr.setLabelsEnabled(False)
    lyr.triggerRepaint()


def pretty_year_label(bin_dir: Path) -> str:
    slug = bin_dir.name
    meta = bin_dir / f"thueringen_state_pie_style_meta_{slug}.json"
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


def add_row_chart_frame(parent_group: QgsLayerTreeGroup):
    """One memory polygon layer with ONE rectangle (no inner lines)."""
    if not DRAW_CHART_FRAMES:
        return

    uri = "Polygon?crs=EPSG:4326&field=kind:string(10)&index=yes"
    lyr = QgsVectorLayer(uri, "thueringen_chart_frame", "memory")
    prov = lyr.dataProvider()

    f = _make_rect_feature(lyr, **ROW_FRAME, kind="row")
    prov.addFeatures([f])
    lyr.updateExtents()

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
    TWO labels:
      - main year heading
      - Installed Power (period) in MW
    You will tweak coordinates anyway.
    """
    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
        "&index=yes"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    prov = lyr.dataProvider()

    # Adjust for Thüringen view
    X_MAIN, Y_MAIN = 10.8, 51.7
    X_SUB,  Y_SUB  = 11.4, 51.6

    feats = []

    f_main = QgsFeature(lyr.fields())
    f_main.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_MAIN, Y_MAIN)))
    f_main["kind"] = "main"
    f_main["label"] = label_text
    feats.append(f_main)

    mw_val = PER_BIN_MW.get(slug)
    sub_text = f"Installed Power: {mw_val:,.1f} MW" if mw_val is not None else "Installed Power: n/a"

    f_sub = QgsFeature(lyr.fields())
    f_sub.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_SUB, Y_SUB)))
    f_sub["kind"] = "sub"
    f_sub["label"] = sub_text
    feats.append(f_sub)

    prov.addFeatures(feats)
    lyr.updateExtents()

    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0"
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    pal_main = QgsPalLayerSettings()
    pal_main.enabled = True
    pal_main.isExpression = True
    pal_main.fieldName = 'CASE WHEN "kind" = \'main\' THEN "label" ELSE NULL END'
    fmt_main = QgsTextFormat()
    fmt_main.setFont(QFont("Arial", 20, QFont.Bold))
    fmt_main.setSize(20)
    fmt_main.setColor(QColor(0, 0, 0))
    buf_main = QgsTextBufferSettings()
    buf_main.setEnabled(False)
    fmt_main.setBuffer(buf_main)
    pal_main.setFormat(fmt_main)
    rule_main = QgsRuleBasedLabeling.Rule(pal_main)
    rule_main.setFilterExpression('"kind" = \'main\'')
    root_rule.appendChild(rule_main)

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

    # Frame (row chart only)
    add_row_chart_frame(parent_group)

    # Energy legend (once)
    if LOAD_ENERGY_LEGEND:
        legend_path = ROOT_DIR / "thueringen_energy_legend_points.geojson"
        if legend_path.exists():
            legend_lyr = QgsVectorLayer(str(legend_path), "energy_legend", "ogr")
            if legend_lyr.isValid():
                style_energy_legend_layer(legend_lyr)
                proj.addMapLayer(legend_lyr, False)
                parent_group.addLayer(legend_lyr)
        else:
            print(f"[WARN] Energy legend file not found: {legend_path}")

    chart_exists = YEARLY_CHART_PATH.exists()

    bin_dirs = sorted([p for p in ROOT_DIR.iterdir() if p.is_dir()], key=bin_sort_key)

    for bin_dir in bin_dirs:
        slug = bin_dir.name
        label = pretty_year_label(bin_dir)

        bin_group = ensure_group(parent_group, label)

        # ----- PIE POLYGONS -----
        pie_path = bin_dir / f"thueringen_state_pie_{slug}.geojson"
        if pie_path.exists():
            pie_lyr = QgsVectorLayer(str(pie_path), f"thueringen_state_pie_{slug}", "ogr")
            if pie_lyr.isValid():
                style_state_pie_layer(pie_lyr)
                proj.addMapLayer(pie_lyr, False)
                bin_group.addLayer(pie_lyr)
        else:
            print(f"[WARN] Pie polygons not found for {slug}: {pie_path}")

        # ----- PIE CENTERS -----
        if LOAD_CENTER_POINTS:
            center_path = bin_dir / f"thueringen_state_pies_{slug}.geojson"
            if center_path.exists():
                center_lyr = QgsVectorLayer(str(center_path), f"thueringen_state_pies_{slug}", "ogr")
                if center_lyr.isValid():
                    style_center_layer(center_lyr, LABEL_CENTER_NUMBERS)
                    proj.addMapLayer(center_lyr, False)
                    bin_group.addLayer(center_lyr)

        # ----- YEARLY ROW CHART (subset cumulative) -----
        if LOAD_YEARLY_CHART and chart_exists:
            chart_lyr = QgsVectorLayer(str(YEARLY_CHART_PATH), f"yearly_rowChart_total_power_{slug}", "ogr")
            if chart_lyr.isValid():
                if slug in YEAR_SLUG_ORDER:
                    idx = YEAR_SLUG_ORDER.index(slug)
                    allowed = YEAR_SLUG_ORDER[:idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)

                    # Keep title + unit points always if they exist
                    expr = (
                        f"(\"year_bin_slug\" IN ({allowed_list}) "
                        f"OR \"year_bin_slug\" IN ('title','unit'))"
                    )
                    chart_lyr.setSubsetString(expr)

                style_yearly_chart_layer(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)

        # ----- GUIDE LINES (subset) -----
        if LOAD_GUIDE_LINES and GUIDES_PATH.exists():
            guides_lyr = QgsVectorLayer(str(GUIDES_PATH), f"yearly_rowChart_guides_{slug}", "ogr")
            if guides_lyr.isValid():
                if slug in YEAR_SLUG_ORDER:
                    idx = YEAR_SLUG_ORDER.index(slug)
                    allowed = YEAR_SLUG_ORDER[:idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)
                    guides_lyr.setSubsetString(f"\"year_bin_slug\" IN ({allowed_list})")

                style_yearly_guides_layer(guides_lyr)
                proj.addMapLayer(guides_lyr, False)
                bin_group.addLayer(guides_lyr)

        # ----- YEAR HEADING -----
        add_year_heading(bin_group, slug, label)

    print("[DONE] Thüringen state pies (yearly) loaded + row chart (MW) + guides + frame.")


main()