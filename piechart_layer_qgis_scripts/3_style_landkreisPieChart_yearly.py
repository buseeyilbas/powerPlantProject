## Filename: 3_style_landkreisPieChart_yearly.py
## QGIS 3.10 / Python 3.7 SAFE
## Nationwide Landkreis – Yearly PieCharts
## Fully mirrors 2_style_statewise_landkreisPieChart_yearly.py
#
#from pathlib import Path
#import json
#
#from qgis.core import (
#    QgsProject,
#    QgsVectorLayer,
#    QgsLayerTreeGroup,
#    QgsCategorizedSymbolRenderer,
#    QgsRendererCategory,
#    QgsFillSymbol,
#    QgsMarkerSymbol,
#    QgsSingleSymbolRenderer,
#    QgsRuleBasedLabeling,
#    QgsPalLayerSettings,
#    QgsTextFormat,
#    QgsTextBufferSettings,
#    QgsFeature,
#    QgsGeometry,
#)
#from qgis.PyQt.QtGui import QColor, QFont
#
## ------------------------------------------------------------
## PATHS
## ------------------------------------------------------------
#
#ROOT_DIR = Path(
#    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly"
#)
#
#CHART_PATH  = ROOT_DIR / "de_yearly_totals_chart.geojson"
#LEGEND_PATH = ROOT_DIR / "de_energy_legend_points.geojson"
#
#GROUP_NAME = "landkreis_pies (yearly)"
#
## ------------------------------------------------------------
## YEAR BINS (ORDER IS CRITICAL)
## ------------------------------------------------------------
#
#YEAR_BINS = [
#    ("pre_1990",  "≤1990"),
#    ("1991_1992", "1991–1992"),
#    ("1993_1994", "1993–1994"),
#    ("1995_1996", "1995–1996"),
#    ("1997_1998", "1997–1998"),
#    ("1999_2000", "1999–2000"),
#    ("2001_2002", "2001–2002"),
#    ("2003_2004", "2003–2004"),
#    ("2005_2006", "2005–2006"),
#    ("2007_2008", "2007–2008"),
#    ("2009_2010", "2009–2010"),
#    ("2011_2012", "2011–2012"),
#    ("2013_2014", "2013–2014"),
#    ("2015_2016", "2015–2016"),
#    ("2017_2018", "2017–2018"),
#    ("2019_2020", "2019–2020"),
#    ("2021_2022", "2021–2022"),
#    ("2023_2024", "2023–2024"),
#    ("2025_2026", "2025–2026"),
#]
#
#YEAR_SLUGS = [s for s, _ in YEAR_BINS]
#
## ------------------------------------------------------------
## COLOR PALETTE (IDENTICAL FAMILY)
## ------------------------------------------------------------
#
#PALETTE = {
#    "pv_kw":      QColor(255, 255,   0, 255),
#    "battery_kw": QColor(148,  87, 235, 255),
#    "wind_kw":    QColor(173, 216, 230, 255),
#    "hydro_kw":   QColor(  0,   0, 255, 255),
#    "biogas_kw":  QColor(  0, 190,   0, 255),
#    "others_kw":  QColor(158, 158, 158, 255),
#}
#
#proj = QgsProject.instance()
#root = proj.layerTreeRoot()
#
## ------------------------------------------------------------
## HELPERS
## ------------------------------------------------------------
#
#def ensure_group(parent, name):
#    grp = parent.findGroup(name)
#    if grp is None:
#        grp = parent.addGroup(name)
#    return grp
#
#
#def set_text_style(pal, size, bold=False, color=QColor(0, 0, 0), buffer=True):
#    fmt = QgsTextFormat()
#    fmt.setFont(QFont("Arial", size, QFont.Bold if bold else QFont.Normal))
#    fmt.setSize(size)
#    fmt.setColor(color)
#
#    buf = QgsTextBufferSettings()
#    buf.setEnabled(buffer)
#    buf.setSize(0.8)
#    buf.setColor(QColor(255, 255, 255))
#    fmt.setBuffer(buf)
#
#    pal.setFormat(fmt)
#
## ------------------------------------------------------------
## PIE POLYGONS
## ------------------------------------------------------------
#
#def style_pie_polygons(layer):
#    cats = []
#    for key, col in PALETTE.items():
#        sym = QgsFillSymbol.createSimple({
#            "color": f"{col.red()},{col.green()},{col.blue()},255",
#            "outline_style": "no",
#        })
#        cats.append(QgsRendererCategory(key, sym, key))
#
#    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
#    layer.setLabelsEnabled(False)
#    layer.triggerRepaint()
#
## ------------------------------------------------------------
## ENERGY LEGEND
## ------------------------------------------------------------
#
#def style_energy_legend(layer):
#    cats = []
#    for key, col in PALETTE.items():
#        sym = QgsMarkerSymbol.createSimple({
#            "name": "circle",
#            "size": "3",
#            "color": f"{col.red()},{col.green()},{col.blue()},255",
#            "outline_style": "no",
#        })
#        cats.append(QgsRendererCategory(key, sym, key))
#    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
#
#    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
#
#    OFFSETS = {
#        "Photovoltaics": 12.5,
#        "Onshore Wind Energy": 18.0,
#        "Hydropower": 12.5,
#        "Biogas": 9.0,
#        "Battery": 9.0,
#        "Others": 9.0,
#    }
#
#    for lbl, xoff in OFFSETS.items():
#        pal = QgsPalLayerSettings()
#        pal.enabled = True
#        pal.fieldName = "legend_label"
#        pal.xOffset = xoff
#        pal.placement = QgsPalLayerSettings.OverPoint
#        set_text_style(pal, size=8)
#
#        rule = QgsRuleBasedLabeling.Rule(pal)
#        rule.setFilterExpression(f"\"legend_label\"='{lbl}'")
#        root_rule.appendChild(rule)
#
#    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
#    layer.setLabelsEnabled(True)
#
## ------------------------------------------------------------
## ROW CHART
## ------------------------------------------------------------
#
#def style_row_chart(layer):
#    cats = []
#    for key, col in PALETTE.items():
#        sym = QgsFillSymbol.createSimple({
#            "color": f"{col.red()},{col.green()},{col.blue()},220",
#            "outline_style": "no",
#        })
#        cats.append(QgsRendererCategory(key, sym, key))
#    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
#
#    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
#
#    # year label
#    pal_y = QgsPalLayerSettings()
#    pal_y.enabled = True
#    pal_y.isExpression = True
#    pal_y.fieldName = 'CASE WHEN "label_anchor"=1 THEN "year_bin_label" END'
#    pal_y.placement = QgsPalLayerSettings.OverPoint
#    set_text_style(pal_y, size=7)
#
#    r_y = QgsRuleBasedLabeling.Rule(pal_y)
#    r_y.setFilterExpression('"label_anchor"=1')
#    root_rule.appendChild(r_y)
#
#    # MW label
#    pal_v = QgsPalLayerSettings()
#    pal_v.enabled = True
#    pal_v.isExpression = True
#    pal_v.fieldName = (
#        'CASE WHEN "value_anchor"=1 '
#        'THEN format_number("total_kw"/1000,1) || \' MW\' END'
#    )
#    pal_v.placement = QgsPalLayerSettings.OverPoint
#    set_text_style(pal_v, size=7)
#
#    r_v = QgsRuleBasedLabeling.Rule(pal_v)
#    r_v.setFilterExpression('"value_anchor"=1')
#    root_rule.appendChild(r_v)
#
#    # title
#    pal_t = QgsPalLayerSettings()
#    pal_t.enabled = True
#    pal_t.isExpression = True
#    pal_t.fieldName = 'CASE WHEN "year_bin_slug"=\'title\' THEN "year_bin_label" END'
#    pal_t.placement = QgsPalLayerSettings.OverPoint
#    set_text_style(pal_t, size=9, bold=True)
#
#    r_t = QgsRuleBasedLabeling.Rule(pal_t)
#    r_t.setFilterExpression('"year_bin_slug"=\'title\'')
#    root_rule.appendChild(r_t)
#
#    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
#    layer.setLabelsEnabled(True)
#
## ------------------------------------------------------------
## YEAR HEADING (MEMORY LAYER)
## ------------------------------------------------------------
#
#def add_year_heading(group, slug, label, installed_mw):
#    uri = "Point?crs=EPSG:4326&field=kind:string&field=label:string"
#    lyr = QgsVectorLayer(uri, slug + "_heading", "memory")
#    pr = lyr.dataProvider()
#
#    feats = []
#
#    f1 = QgsFeature(lyr.fields())
#    f1.setGeometry(QgsGeometry.fromWkt("POINT(9.5 55.0)"))
#    f1["kind"] = "main"
#    f1["label"] = label
#    feats.append(f1)
#
#    if installed_mw is not None:
#        f2 = QgsFeature(lyr.fields())
#        f2.setGeometry(QgsGeometry.fromWkt("POINT(16.0 54.9)"))
#        f2["kind"] = "sub"
#        f2["label"] = "Installed Power: %.1f MW" % installed_mw
#        feats.append(f2)
#
#    pr.addFeatures(feats)
#    lyr.updateExtents()
#
#    sym = QgsMarkerSymbol.createSimple({"size": "0.01", "color": "0,0,0,0"})
#    lyr.setRenderer(QgsSingleSymbolRenderer(sym))
#
#    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())
#
#    for kind, size, bold in [("main", 20, True), ("sub", 12, True)]:
#        pal = QgsPalLayerSettings()
#        pal.enabled = True
#        pal.isExpression = True
#        pal.fieldName = 'CASE WHEN "kind"=\'%s\' THEN "label" END' % kind
#        pal.placement = QgsPalLayerSettings.OverPoint
#        set_text_style(pal, size=size, bold=bold, color=QColor(60,60,60))
#
#        r = QgsRuleBasedLabeling.Rule(pal)
#        r.setFilterExpression('"kind"=\'%s\'' % kind)
#        root_rule.appendChild(r)
#
#    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
#    lyr.setLabelsEnabled(True)
#
#    proj.addMapLayer(lyr, False)
#    group.addLayer(lyr)
#
## ------------------------------------------------------------
## READ INSTALLED MW
## ------------------------------------------------------------
#
#def read_installed_mw():
#    """
#    Return PERIOD installed power per bin (MW), not cumulative.
#    We read cumulative totals from value_anchor==1 points and take diffs along YEAR_SLUGS.
#    """
#    if not CHART_PATH.exists():
#        return {}
#
#    data = json.loads(CHART_PATH.read_text(encoding="utf-8"))
#
#    # 1) cumulative kW from value_anchor==1 points
#    cum_kw = {}
#    for f in data.get("features", []):
#        p = f.get("properties", {})
#        slug = p.get("year_bin_slug")
#        if not slug or slug == "title":
#            continue
#
#        if str(p.get("value_anchor")) != "1":
#            continue
#
#        if slug not in YEAR_SLUGS:
#            continue
#
#        try:
#            cum_kw[slug] = float(p.get("total_kw", 0.0))
#        except Exception:
#            continue
#
#    # 2) period = diff of cumulative
#    out = {}
#    prev = None
#    for slug in YEAR_SLUGS:
#        if slug not in cum_kw:
#            continue
#        if prev is None:
#            period_kw = cum_kw[slug]
#        else:
#            period_kw = cum_kw[slug] - cum_kw.get(prev, 0.0)
#
#        out[slug] = period_kw / 1000.0  # MW
#        prev = slug
#
#    return out
#
#
## ------------------------------------------------------------
## MAIN
## ------------------------------------------------------------
#
#def main():
#    old = root.findGroup(GROUP_NAME)
#    if old:
#        root.removeChildNode(old)
#
#    main_group = ensure_group(root, GROUP_NAME)
#
#    # legend
#    if LEGEND_PATH.exists():
#        leg = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
#        style_energy_legend(leg)
#        proj.addMapLayer(leg, False)
#        main_group.addLayer(leg)
#
#    installed = read_installed_mw()
#
#    for slug, label in YEAR_BINS:
#        grp = ensure_group(main_group, label)
#
#        pie_path = ROOT_DIR / slug / ("de_landkreis_pie_%s.geojson" % slug)
#        if not pie_path.exists():
#            continue
#
#        pies = QgsVectorLayer(str(pie_path), "pies_" + slug, "ogr")
#        style_pie_polygons(pies)
#        proj.addMapLayer(pies, False)
#        grp.addLayer(pies)
#
#        if CHART_PATH.exists():
#            chart = QgsVectorLayer(str(CHART_PATH), "chart_" + slug, "ogr")
#            allowed = YEAR_SLUGS[:YEAR_SLUGS.index(slug)+1]
#            flt = ",".join(["'%s'" % s for s in allowed])
#            chart.setSubsetString(
#                "(\"year_bin_slug\" IN (%s) OR \"year_bin_slug\"='title')" % flt
#            )
#            style_row_chart(chart)
#            proj.addMapLayer(chart, False)
#            grp.addLayer(chart)
#
#        add_year_heading(grp, slug, label, installed.get(slug))
#
#    print("[DONE] 3_style_landkreisPieChart_yearly loaded (QGIS 3.10 safe)")
#
#main()
#


# Filename: 3_style_landkreisPieChart_yearly.py
# Purpose:
#   Nationwide Landkreis yearly piecharts (polygon pies) + row/column charts + legend
#   Fully mirrors 2_style_statewise_landkreisPieChart_yearly.py (same coordinates & formatting).
#
# Requirements:
#   - 2-year bins are cumulative (handled by step3_3/step3_4 outputs; style only loads).
#   - GW unit everywhere:
#       * Row chart + subtitle: 2 decimals (your "2 significant figure" convention)
#       * Column chart values: 1 decimal
#   - Row chart title changed (read from chart layer's "title" point).
#   - Dashed guidelines are loaded and styled.
#   - Column bar chart is loaded (bars + labels) with same coordinates as 2_style / 1_style.
#   - Frames are drawn (row + column) as a memory polygon layer (same coords).
#
# QGIS 3.10 / Python 3.7 SAFE

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
    QgsSingleSymbolRenderer,
    QgsRuleBasedLabeling,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsMarkerSymbol,
    QgsLineSymbol,
    QgsUnitTypes,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
)
from qgis.PyQt.QtGui import QColor, QFont


# ----------------------------------------------------------
# PATHS
# ----------------------------------------------------------
ROOT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly"
)

GROUP_NAME = "nationwide_landkreis_pies (yearly)"

# Files produced by step3_3 (live in ROOT_DIR)
YEARLY_CHART_PATH = ROOT_DIR / "de_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR / "de_yearly_totals_chart_guides.geojson"
LEGEND_PATH = ROOT_DIR / "de_energy_legend_points.geojson"

# Column chart produced by step3_3
STATE_COL_BARS_PATH = ROOT_DIR / "de_state_totals_columnChart_bars.geojson"
STATE_COL_LABELS_PATH = ROOT_DIR / "de_state_totals_columnChart_labels.geojson"


# ----------------------------------------------------------
# SWITCHES
# ----------------------------------------------------------
LOAD_YEARLY_CHART = True
LOAD_GUIDE_LINES = True
LOAD_STATE_COLUMN_CHART = True
LOAD_ENERGY_LEGEND = True
DRAW_CHART_FRAMES = True


# ----------------------------------------------------------
# FRAMES (same as 2_style / 1_style coordinates)
# ----------------------------------------------------------
ROW_FRAME = {
    "xmin": -3.75,
    "ymin": 47.25,
    "xmax": 5.80,
    "ymax": 51.75,
}
COL_FRAME = {
    "xmin": 15.95,
    "ymin": 47.15,
    "xmax": 22.10,
    "ymax": 54.45,
}
FRAME_OUTLINE = QColor(150, 150, 150, 255)
FRAME_WIDTH_MM = 0.4


# ----------------------------------------------------------
# YEAR BINS (same as 2_style source of truth)
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
YEAR_SLUG_ORDER = [slug for (slug, _label, _y1, _y2) in YEAR_BINS]
YEAR_LABEL_MAP = {slug: label for (slug, label, *_rest) in YEAR_BINS}


# ----------------------------------------------------------
# COLORS (same as 2_style / 1_style)
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
    if isinstance(parent, QgsLayerTreeGroup):
        grp = parent.findGroup(name)
        if grp is None:
            grp = parent.addGroup(name)
        return grp
    grp = root.findGroup(name)
    if grp is None:
        grp = root.addGroup(name)
    return grp


def is_anchor_one(v) -> bool:
    """Robust check: accepts 1, 1.0, '1', '1.0', True."""
    if v is None:
        return False
    try:
        return int(float(v)) == 1
    except Exception:
        return str(v).strip() in {"1", "1.0", "true", "True"}


def bin_sort_key_slug(slug: str):
    """Sort bins naturally (pre_1990 first, then by numeric year)."""
    if slug == "pre_1990":
        return (-1, -1)
    m = re.match(r"(\d{4})_(\d{4})", slug)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (9999, slug)


# ----------------------------------------------------------
# PIE STYLING
# ----------------------------------------------------------
def style_pie_polygons(layer: QgsVectorLayer):
    """Categorized fill color by energy_type."""
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
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ENERGY LEGEND (same as 2_style)
# ----------------------------------------------------------
def style_energy_legend_layer(layer: QgsVectorLayer):
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
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    def add_rule(label_value: str, x_offset: float):
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
        pal.fieldName = "legend_label"
        pal.xOffset = x_offset
        pal.yOffset = 0.0
        try:
            pal.placement = QgsPalLayerSettings.OverPoint
        except Exception:
            pass

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 8))
        fmt.setSize(8)
        fmt.setColor(QColor(0, 0, 0))
        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)
        pal.setFormat(fmt)

        rule = QgsRuleBasedLabeling.Rule(pal)
        rule.setFilterExpression(f"\"legend_label\" = '{label_value}'")
        root_rule.appendChild(rule)

    add_rule("Photovoltaics", 12.5)
    add_rule("Onshore Wind Energy", 18.0)
    add_rule("Hydropower", 12.5)
    add_rule("Biogas", 9.0)
    add_rule("Battery", 9.0)
    add_rule("Others", 9.0)
    add_rule("legend_note", 6.0)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ROW CHART (GW: values 2 decimals; title + unit points)
# ----------------------------------------------------------
def style_yearly_chart_layer(layer: QgsVectorLayer):
    fields = [f.name() for f in layer.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

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
        layer.setRenderer(QgsCategorizedSymbolRenderer(energy_field, cats))
    else:
        sym = QgsFillSymbol.createSimple(
            {
                "color": "200,200,200,200",
                "outline_style": "no",
                "outline_color": "0,0,0,0",
                "outline_width": "0",
            }
        )
        layer.setRenderer(QgsSingleSymbolRenderer(sym))

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

    # (2) value labels (GW numbers, 2 decimals, no suffix)
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

    # (4) unit label point ("GW") shown once
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

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def style_yearly_guides_layer(layer: QgsVectorLayer):
    """Dashed guide lines from bar end to value column."""
    sym = QgsLineSymbol.createSimple(
        {"color": "0,0,0,120", "width": "0.20", "line_style": "dash"}
    )
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


# ----------------------------------------------------------
# COLUMN CHART (values 1 decimal GW)
# ----------------------------------------------------------
def style_state_column_bars_layer(layer: QgsVectorLayer):
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

    renderer = QgsCategorizedSymbolRenderer("energy_type", cats)

    default_sym = QgsFillSymbol.createSimple(
        {
            "color": "0,0,0,0",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0",
        }
    )
    try:
        renderer.setSourceSymbol(default_sym)
    except Exception:
        pass

    layer.setRenderer(renderer)
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def style_state_column_labels_layer(layer: QgsVectorLayer):
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
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

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
    st_buf = QgsTextBufferSettings()
    st_buf.setEnabled(False)
    st_fmt.setBuffer(st_buf)
    st_pal.setFormat(st_fmt)
    try:
        st_pal.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass
    st_rule = QgsRuleBasedLabeling.Rule(st_pal)
    st_rule.setFilterExpression("\"kind\" = 'state_label'")
    root_rule.appendChild(st_rule)

    # (2) values (GW, 1 decimal)
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
    val_buf = QgsTextBufferSettings()
    val_buf.setEnabled(False)
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
    title_pal.fieldName = "CASE WHEN \"kind\" = 'title' THEN \"year_bin_label\" ELSE NULL END"
    title_fmt = QgsTextFormat()
    title_fmt.setFont(QFont("Arial", 9, QFont.Bold))
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
    title_rule.setFilterExpression("\"kind\" = 'title'")
    root_rule.appendChild(title_rule)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# FRAMES (memory layer)
# ----------------------------------------------------------
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
    if not DRAW_CHART_FRAMES:
        return

    uri = "Polygon?crs=EPSG:4326&field=kind:string(10)&index=yes"
    layer = QgsVectorLayer(uri, "chart_frames", "memory")
    prov = layer.dataProvider()

    feats = [
        _make_rect_feature(layer, **ROW_FRAME, kind="row"),
        _make_rect_feature(layer, **COL_FRAME, kind="column"),
    ]
    prov.addFeatures(feats)
    layer.updateExtents()

    sym = QgsFillSymbol.createSimple(
        {
            "color": "0,0,0,0",
            "outline_color": f"{FRAME_OUTLINE.red()},{FRAME_OUTLINE.green()},{FRAME_OUTLINE.blue()},{FRAME_OUTLINE.alpha()}",
            "outline_width": str(FRAME_WIDTH_MM),
        }
    )
    try:
        sym.setOutputUnit(QgsUnitTypes.RenderMillimeters)
    except Exception:
        pass

    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()

    QgsProject.instance().addMapLayer(layer, False)
    parent_group.addLayer(layer)


# ----------------------------------------------------------
# YEAR HEADING (memory layer; coords same as 2_style)
# ----------------------------------------------------------
def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label_text: str, per_bin_gw):
    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
        "&index=yes"
    )
    layer = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    prov = layer.dataProvider()

    X_MAIN = 9.7
    Y_MAIN = 55.1
    X_SUB = 13.0
    Y_SUB = 54.9

    feats = []

    f_main = QgsFeature(layer.fields())
    f_main.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_MAIN, Y_MAIN)))
    f_main["kind"] = "main"
    f_main["label"] = label_text
    feats.append(f_main)

    f_sub = QgsFeature(layer.fields())
    f_sub.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_SUB, Y_SUB)))
    f_sub["kind"] = "sub"
    if per_bin_gw is None:
        f_sub["label"] = "Installed Power: n/a"
    else:
        f_sub["label"] = f"Installed Power: {per_bin_gw:,.2f} GW"
    feats.append(f_sub)

    prov.addFeatures(feats)
    layer.updateExtents()

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
    layer.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    pal_main = QgsPalLayerSettings()
    pal_main.enabled = True
    pal_main.isExpression = True
    pal_main.fieldName = 'CASE WHEN "kind" = \'main\' THEN "label" ELSE NULL END'
    try:
        pal_main.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

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

    pal_sub = QgsPalLayerSettings()
    pal_sub.enabled = True
    pal_sub.isExpression = True
    pal_sub.fieldName = 'CASE WHEN "kind" = \'sub\' THEN "label" ELSE NULL END'
    try:
        pal_sub.placement = QgsPalLayerSettings.OverPoint
    except Exception:
        pass

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

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

    proj.addMapLayer(layer, False)
    parent_group.addLayer(layer)


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
def main():
    if not ROOT_DIR.exists():
        print(f"[ERROR] ROOT_DIR does not exist: {ROOT_DIR}")
        return

    # remove old group
    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    group = ensure_group(root, GROUP_NAME)

    # frames
    add_chart_frames(group)

    # legend
    if LOAD_ENERGY_LEGEND and LEGEND_PATH.exists():
        legend = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
        if legend.isValid():
            style_energy_legend_layer(legend)
            proj.addMapLayer(legend, False)
            group.addLayer(legend)
        else:
            print(f"[WARN] Legend layer invalid: {LEGEND_PATH}")
    elif LOAD_ENERGY_LEGEND:
        print(f"[WARN] Legend file not found: {LEGEND_PATH}")

    # PERIOD GW for subtitle (diff of cumulative totals read from chart)
    PER_BIN_GW = {}
    try:
        if YEARLY_CHART_PATH.exists():
            with open(str(YEARLY_CHART_PATH), "r", encoding="utf-8") as f:
                chart = json.load(f)

            cum_kw = {}
            for feat in chart.get("features", []):
                props = feat.get("properties", {})
                slug = props.get("year_bin_slug")
                if not slug or slug == "title":
                    continue
                if not is_anchor_one(props.get("value_anchor")):
                    continue
                try:
                    cum_kw[slug] = float(props.get("total_kw", 0.0))
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
                PER_BIN_GW[slug] = float(period_kw) / 1_000_000.0
                prev = slug
    except Exception as e:
        print(f"[WARN] Could not compute PER_BIN_GW: {e}")
        PER_BIN_GW = {}

    chart_exists = YEARLY_CHART_PATH.exists()
    guides_exists = GUIDES_PATH.exists()

    # bins
    for slug in sorted(YEAR_LABEL_MAP.keys(), key=bin_sort_key_slug):
        bin_label = YEAR_LABEL_MAP[slug]
        bin_group = ensure_group(group, bin_label)

        # ----------------------------------------------------------
        # Load nationwide pie polygons for this bin (step3_4 output)
        # Path: ROOT_DIR/<bin_slug>/de_landkreis_pie_<bin_slug>.geojson
        # ----------------------------------------------------------
        pie_path = ROOT_DIR / slug / f"de_landkreis_pie_{slug}.geojson"
        if pie_path.exists():
            pies = QgsVectorLayer(str(pie_path), f"landkreis_pies_{slug}", "ogr")
            if pies.isValid():
                style_pie_polygons(pies)
                proj.addMapLayer(pies, False)
                bin_group.addLayer(pies)
            else:
                print(f"[WARN] Invalid pie layer: {pie_path}")
        else:
            print(f"[INFO] Pie file missing for bin {slug}: {pie_path}")

        # ----------------------------------------------------------
        # Row chart subset (cumulative up to bin)
        # ----------------------------------------------------------
        if LOAD_YEARLY_CHART and chart_exists:
            chart_lyr = QgsVectorLayer(str(YEARLY_CHART_PATH), f"yearly_rowChart_total_power_{slug}", "ogr")
            if chart_lyr.isValid():
                idx = YEAR_SLUG_ORDER.index(slug) if slug in YEAR_SLUG_ORDER else -1
                if idx >= 0:
                    allowed = YEAR_SLUG_ORDER[: idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)
                    chart_lyr.setSubsetString(
                        f"(\"year_bin_slug\" IN ({allowed_list}) OR \"year_bin_slug\" IN ('title','unit'))"
                    )
                style_yearly_chart_layer(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)

        # ----------------------------------------------------------
        # Dashed guidelines subset
        # ----------------------------------------------------------
        if LOAD_GUIDE_LINES and guides_exists:
            guides_lyr = QgsVectorLayer(str(GUIDES_PATH), f"yearly_rowChart_guides_{slug}", "ogr")
            if guides_lyr.isValid():
                idx = YEAR_SLUG_ORDER.index(slug) if slug in YEAR_SLUG_ORDER else -1
                if idx >= 0:
                    allowed = YEAR_SLUG_ORDER[: idx + 1]
                    allowed_list = ",".join(f"'{s}'" for s in allowed)
                    guides_lyr.setSubsetString(f"\"year_bin_slug\" IN ({allowed_list})")
                style_yearly_guides_layer(guides_lyr)
                proj.addMapLayer(guides_lyr, False)
                bin_group.addLayer(guides_lyr)

        # ----------------------------------------------------------
        # Column chart subset (bars + labels)
        # ----------------------------------------------------------
        if LOAD_STATE_COLUMN_CHART:
            if STATE_COL_BARS_PATH.exists():
                bars_lyr = QgsVectorLayer(str(STATE_COL_BARS_PATH), f"state_columnBars_{slug}", "ogr")
                if bars_lyr.isValid():
                    bars_lyr.setSubsetString(f"\"year_bin_slug\" = '{slug}'")
                    style_state_column_bars_layer(bars_lyr)
                    proj.addMapLayer(bars_lyr, False)
                    bin_group.addLayer(bars_lyr)
            else:
                print(f"[WARN] STATE_COL_BARS_PATH not found: {STATE_COL_BARS_PATH}")

            if STATE_COL_LABELS_PATH.exists():
                labels_lyr = QgsVectorLayer(str(STATE_COL_LABELS_PATH), f"state_columnLabels_{slug}", "ogr")
                if labels_lyr.isValid():
                    labels_lyr.setSubsetString(
                        f"(\"year_bin_slug\" = '{slug}' OR \"year_bin_slug\" = 'state_title')"
                    )
                    style_state_column_labels_layer(labels_lyr)
                    proj.addMapLayer(labels_lyr, False)
                    bin_group.addLayer(labels_lyr)
            else:
                print(f"[WARN] STATE_COL_LABELS_PATH not found: {STATE_COL_LABELS_PATH}")

        # ----------------------------------------------------------
        # Year heading (main + subtitle in GW)
        # ----------------------------------------------------------
        add_year_heading(bin_group, slug, bin_label, PER_BIN_GW.get(slug))

    print("[DONE] Loaded nationwide Landkreis pies with full 2_style-aligned styling.")


main()
