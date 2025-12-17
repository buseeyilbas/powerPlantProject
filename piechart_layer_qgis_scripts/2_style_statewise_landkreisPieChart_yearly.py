# Filename: 2_style_statewise_landkreisPieChart_yearly.py
# Purpose : EXACT same visual structure as state_pies (yearly),
#           but without HUD, without state numbers, without center labels.
#           Loads:
#             • per-bin Landkreis pies (grouped)
#             • global yearly row chart (subset per bin)
#             • energy legend (top-left)
#             • year titles (main + Installed Power: X MW)
#
# QGIS 3.10 SAFE — fully rule-based labels.

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsVectorLayerSimpleLabeling, QgsPalLayerSettings, QgsTextFormat,
    QgsTextBufferSettings, QgsProperty, QgsSingleSymbolRenderer,
    QgsRuleBasedLabeling
)
from qgis.PyQt.QtGui import QColor, QFont
from pathlib import Path
import json
import re

# ----------------------------------------------------------
#               PATHS (adjust if needed)
# ----------------------------------------------------------

ROOT_DIR = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies_yearly")
CHART_PATH = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly\de_yearly_totals_chart.geojson")
LEGEND_PATH = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly\de_energy_legend_points.geojson")

GROUP_NAME = "statewise_landkreis_pies (yearly)"

# ----------------------------------------------------------
#                 YEAR BINS (same as state script)
# ----------------------------------------------------------
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

YEAR_SLUGS = [slug for (slug, *_ ) in YEAR_BINS]
YEAR_LABEL_MAP = {slug: label for (slug, label, *_ ) in YEAR_BINS}

# energy colors (same order as pies + chart)
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

# ----------------------------------------------------------
# UTILITIES
# ----------------------------------------------------------
def ensure_group(parent, name: str):
    grp = parent.findGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.findGroup(name)
    if grp is None:
        grp = parent.addGroup(name) if isinstance(parent, QgsLayerTreeGroup) else root.addGroup(name)
    return grp

def style_pie_polygons(layer: QgsVectorLayer):
    """Categorized fill color by energy_type (same as state pies)."""
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
# ENERGY LEGEND (top-left)
# ----------------------------------------------------------
def style_energy_legend(layer: QgsVectorLayer):
    """Same energy legend as state script (rule-based offsets)."""

    # SYMBOLS
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

    # transparent note
    note = QgsMarkerSymbol.createSimple({
        "name": "circle", "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no"
    })
    cats.append(QgsRendererCategory("legend_note", note, "legend_note"))

    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    # RULE-BASED LABELS
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    def add(lb: str, x: float):
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.fieldName = "legend_label"
        pal.xOffset = x
        pal.yOffset = 0
        pal.placement = QgsPalLayerSettings.OverPoint

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 8))
        fmt.setSize(8)
        fmt.setColor(QColor(0,0,0))

        buf = QgsTextBufferSettings()
        buf.setEnabled(False)
        fmt.setBuffer(buf)

        pal.setFormat(fmt)

        r = QgsRuleBasedLabeling.Rule(pal)
        r.setFilterExpression(f'"legend_label" = \'{lb}\'')
        root_rule.appendChild(r)

    # same offsets as your final state version
    add("Photovoltaics",        12.5)
    add("Onshore Wind Energy",  18.0)
    add("Hydropower",           12.5)
    add("Biogas",                9.0)
    add("Battery",               9.0)
    add("Others",                9.0)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

# ----------------------------------------------------------
# ROW CHART STYLING  (same as state)
# ----------------------------------------------------------
def style_row_chart(layer: QgsVectorLayer):
    """Stacked bars, year labels, MW labels, chart title."""
    fields = [f.name() for f in layer.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

    # polygons
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

    # LABELS (rule-based)
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # YEAR LABEL left
    pal_year = QgsPalLayerSettings()
    pal_year.enabled = True
    pal_year.isExpression = True
    pal_year.fieldName = 'CASE WHEN "label_anchor"=1 THEN "year_bin_label" END'
    try: pal_year.placement = QgsPalLayerSettings.OverPoint
    except: pass

    fmt_year = QgsTextFormat()
    fmt_year.setFont(QFont("Arial", 7))
    fmt_year.setSize(7)
    fmt_year.setColor(QColor(0,0,0))
    pal_year.setFormat(fmt_year)

    r_year = QgsRuleBasedLabeling.Rule(pal_year)
    r_year.setFilterExpression('"label_anchor" = 1')
    root_rule.appendChild(r_year)

    # MW LABEL right
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000.0,1) || \' MW\' END'
    )
    try: pal_val.placement = QgsPalLayerSettings.OverPoint
    except: pass

    fmt_val = QgsTextFormat()
    fmt_val.setFont(QFont("Arial", 7))
    fmt_val.setSize(7)
    fmt_val.setColor(QColor(0,0,0))
    pal_val.setFormat(fmt_val)

    r_val = QgsRuleBasedLabeling.Rule(pal_val)
    r_val.setFilterExpression('"value_anchor" = 1')
    root_rule.appendChild(r_val)

    # TITLE (year_bin_slug = 'title')
    pal_title = QgsPalLayerSettings()
    pal_title.enabled = True
    pal_title.isExpression = True
    pal_title.fieldName = 'CASE WHEN "year_bin_slug"=\'title\' THEN "year_bin_label" END'
    try: pal_title.placement = QgsPalLayerSettings.OverPoint
    except: pass

    fmt_title = QgsTextFormat()
    fmt_title.setFont(QFont("Arial", 9))
    fmt_title.setSize(9)
    fmt_title.setColor(QColor(0,0,0))
    pal_title.setFormat(fmt_title)

    r_title = QgsRuleBasedLabeling.Rule(pal_title)
    r_title.setFilterExpression('"year_bin_slug" = \'title\'')
    root_rule.appendChild(r_title)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()

# ----------------------------------------------------------
# LOAD YEAR HEADING (main + subheading MW)
# ----------------------------------------------------------
def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label: str, per_bin_mw: float):
    """Create a small in-memory layer with big title + subheading."""
    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    pr = lyr.dataProvider()

    feats = []

    # Main title (top of Germany)
    f_main = QgsFeature(lyr.fields())
    f_main.setGeometry(QgsGeometry.fromWkt("POINT(9.5 55.0)"))
    f_main["kind"] = "main"
    f_main["label"] = label
    feats.append(f_main)

    # Subheading
    if per_bin_mw is not None:
        f_sub = QgsFeature(lyr.fields())
        f_sub.setGeometry(QgsGeometry.fromWkt("POINT(16.0 54.9)"))
        f_sub["kind"] = "sub"
        f_sub["label"] = f"Installed Power: {per_bin_mw:,.1f} MW"
        feats.append(f_sub)

    pr.addFeatures(feats)
    lyr.updateExtents()

    # invisible symbol
    sym = QgsMarkerSymbol.createSimple({
        "name": "square",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_color": "0,0,0,0"
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    # rule-based labels
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # main
    pal_m = QgsPalLayerSettings()
    pal_m.enabled = True
    pal_m.isExpression = True
    pal_m.fieldName = 'CASE WHEN "kind"=\'main\' THEN "label" END'
    pal_m.placement = QgsPalLayerSettings.OverPoint

    fmt_m = QgsTextFormat()
    fmt_m.setFont(QFont("Arial", 20, QFont.Bold))
    fmt_m.setSize(20)
    fmt_m.setColor(QColor(0,0,0))
    pal_m.setFormat(fmt_m)

    r_m = QgsRuleBasedLabeling.Rule(pal_m)
    r_m.setFilterExpression('"kind" = \'main\'')
    root_rule.appendChild(r_m)

    # sub
    pal_s = QgsPalLayerSettings()
    pal_s.enabled = True
    pal_s.isExpression = True
    pal_s.fieldName = 'CASE WHEN "kind"=\'sub\' THEN "label" END'
    pal_s.placement = QgsPalLayerSettings.OverPoint

    fmt_s = QgsTextFormat()
    fmt_s.setFont(QFont("Arial", 12))
    fmt_s.setSize(12)
    fmt_s.setColor(QColor(60,60,60))
    pal_s.setFormat(fmt_s)

    r_s = QgsRuleBasedLabeling.Rule(pal_s)
    r_s.setFilterExpression('"kind" = \'sub\'')
    root_rule.appendChild(r_s)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

    proj.addMapLayer(lyr, False)
    parent_group.addLayer(lyr)

# ----------------------------------------------------------
# MAIN LOADER
# ----------------------------------------------------------
def main():
    # remove old group
    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    group = ensure_group(root, GROUP_NAME)

    # ------------------------------------------------------
    # LOAD ENERGY LEGEND
    # ------------------------------------------------------
    if LEGEND_PATH.exists():
        legend = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
        if legend.isValid():
            style_energy_legend(legend)
            proj.addMapLayer(legend, False)
            group.addLayer(legend)

    # ------------------------------------------------------
    # LOAD WHOLE ROW CHART (subset per bin)
    # ------------------------------------------------------
    chart_exists = CHART_PATH.exists()

    # Extract PER_BIN_MW from chart
    PER_BIN_MW = {}
    if chart_exists:
        with open(str(CHART_PATH), "r", encoding="utf-8") as f:
            chart = json.load(f)

        for feat in chart["features"]:
            p = feat["properties"]
            if p.get("energy_type") == "heading_sub":
                slug = p["year_bin_slug"]
                PER_BIN_MW[slug] = float(p.get("total_kw", 0.0)) / 1000.0

    # ------------------------------------------------------
    # LOAD PIES PER BIN
    # ------------------------------------------------------
    for slug in YEAR_SLUGS:
        # group for this bin
        bin_group = ensure_group(group, YEAR_LABEL_MAP[slug])

        # load all pies for all states (but landkreis)
        pies = sorted(ROOT_DIR.glob(f"de_*_landkreis_pie_{slug}.geojson"))
        if not pies:
            continue

        for p in pies:
            state_name = p.stem.replace("de_", "").replace(f"_landkreis_pie_{slug}", "")
            lyr_name = f"{state_name} ({slug})"
            lyr = QgsVectorLayer(str(p), lyr_name, "ogr")
            if lyr.isValid():
                proj.addMapLayer(lyr, False)
                bin_group.addLayer(lyr)
                style_pie_polygons(lyr)

        # row chart subset
        if chart_exists:
            chart_lyr = QgsVectorLayer(str(CHART_PATH), f"yearly_rowChart_{slug}", "ogr")
            if chart_lyr.isValid():
                if slug in YEAR_SLUGS:
                    idx = YEAR_SLUGS.index(slug)
                    allowed = YEAR_SLUGS[:idx+1]
                    allowed_str = ",".join(f"'{s}'" for s in allowed)
                    expr = f"(\"year_bin_slug\" IN ({allowed_str}) OR \"year_bin_slug\"='title')"
                    chart_lyr.setSubsetString(expr)
                style_row_chart(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)

        # heading (big title)
        add_year_heading(bin_group, slug, YEAR_LABEL_MAP[slug], PER_BIN_MW.get(slug))

    print("[DONE] Loaded statewise_landkreis pies with full styling.")

main()
