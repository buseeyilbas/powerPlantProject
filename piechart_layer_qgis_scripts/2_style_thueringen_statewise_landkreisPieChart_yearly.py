# Filename: 2_style_thueringen_statewise_landkreisPieChart_yearly.py
# Purpose:
#   Thüringen-only QGIS loader & styler for statewise Landkreis yearly pie charts.
#   - Loads a SINGLE Thüringen pie layer per bin
#   - Loads Thüringen cumulative row chart + energy legend created by step2_5
#   - Loads Thüringen Landkreis numbering:
#       * Numbers on map (inside polygons) via NUMBER_POINTS_PATH
#       * Right-side list via NUMBER_LIST_PATH
#
# QGIS 3.10 SAFE — rule-based labels where needed.

from pathlib import Path
import json

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsSingleSymbolRenderer, QgsRuleBasedLabeling,
    QgsMarkerSymbol, QgsFeature, QgsGeometry, QgsPointXY,
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
LEGEND_PATH = ROOT_DIR / "thueringen_landkreis_energy_legend_points.geojson"

# Landkreis numbering layers created by step2_5
NUMBER_POINTS_PATH = ROOT_DIR / "thueringen_landkreis_number_points.geojson"
NUMBER_LIST_PATH   = ROOT_DIR / "thueringen_landkreis_number_list_points.geojson"

GROUP_NAME = "thueringen_statewise_landkreis_pies (yearly)"


# ----------------------------------------------------------
#                 YEAR BINS
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


# ----------------------------------------------------------
#                 COLORS
# ----------------------------------------------------------
PALETTE = {
    "pv_kw":      QColor(255, 255, 0, 255),
    "battery_kw": QColor(148, 87, 235, 255),
    "wind_kw":    QColor(173, 216, 230, 255),
    "hydro_kw":   QColor(0, 0, 255, 255),
    "biogas_kw":  QColor(0, 190, 0, 255),
    "others_kw":  QColor(158, 158, 158, 255),
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

    # Keep as-is (you said it looks good in Thüringen view)
    add_label_rule('"legend_label" = \'Photovoltaics\'',        12.5)
    add_label_rule('"legend_label" = \'Onshore Wind Energy\'',  18.0)
    add_label_rule('"legend_label" = \'Hydropower\'',           12.5)
    add_label_rule('"legend_label" = \'Biogas\'',                9.0)
    add_label_rule('"legend_label" = \'Battery\'',               9.0)
    add_label_rule('"legend_label" = \'Others\'',                9.0)
    add_label_rule('"energy_type" = \'legend_note\'',            6.0)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


# ----------------------------------------------------------
# ROW CHART STYLING
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

    # VALUE LABELS (right points)
    pal_val = QgsPalLayerSettings()
    pal_val.enabled = True
    pal_val.isExpression = True
    pal_val.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000.0, 1) || \' MW\' '
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

    # Thüringen heading coordinates
    X_MAIN, Y_MAIN = 10.8, 51.7
    X_SUB,  Y_SUB  = 11.4, 51.6

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

    # invisible marker
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
    """
    Numbers inside Thüringen Landkreis polygons:
    - uses NUMBER_POINTS layer (point geometry) created by step2_5
    - label = "num"
    - halo enabled
    """
    # invisible marker
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0",
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    # Default (simple) labeling now.
    # If you later want Sunda-like manual offsets per num, we can switch this to RuleBasedLabeling.
    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = 'to_string("num")'
    pal.placement = QgsPalLayerSettings.OverPoint
    pal.xOffset = 0.0
    pal.yOffset = 0.0

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
    """
    Right-side list: one text line per Landkreis.
    step2_5 already writes 'label' like: '1. Eichsfeld'
    """
    # invisible marker
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
    pal.xOffset = 0.0
    pal.yOffset = 0.0

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


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
def main():
    if not ROOT_DIR.exists():
        print(f"[ERROR] ROOT_DIR does not exist: {ROOT_DIR}")
        return

    # remove old group for clean reruns
    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    group = ensure_group(root, GROUP_NAME)

    # 1) Energy legend (left side)
    if LEGEND_PATH.exists():
        legend = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
        if legend.isValid():
            style_energy_legend(legend)
            proj.addMapLayer(legend, False)
            group.addLayer(legend)
    else:
        print(f"[WARN] LEGEND_PATH not found: {LEGEND_PATH}")

    # 2) Landkreis numbering (map numbers + right-side list)
    if NUMBER_POINTS_PATH.exists():
        num_pts = QgsVectorLayer(str(NUMBER_POINTS_PATH), "thueringen_landkreis_numbers", "ogr")
        if num_pts.isValid():
            style_kreis_number_points_layer(num_pts)
            proj.addMapLayer(num_pts, False)
            group.addLayer(num_pts)
    else:
        print(f"[WARN] Number points not found: {NUMBER_POINTS_PATH}")

    if NUMBER_LIST_PATH.exists():
        num_list = QgsVectorLayer(str(NUMBER_LIST_PATH), "thueringen_landkreis_number_list", "ogr")
        if num_list.isValid():
            style_kreis_number_list_layer(num_list)
            proj.addMapLayer(num_list, False)
            group.addLayer(num_list)
    else:
        print(f"[WARN] Number list not found: {NUMBER_LIST_PATH}")

    # 3) Chart exists?
    chart_exists = CHART_PATH.exists()
    if not chart_exists:
        print(f"[WARN] CHART_PATH not found: {CHART_PATH}")

    # PERIOD MW (diff of cumulative) from chart GeoJSON
    PER_BIN_MW = {}
    if chart_exists:
        try:
            with open(str(CHART_PATH), "r", encoding="utf-8") as f:
                chart = json.load(f)

            cum_kw = {}
            for feat in chart.get("features", []):
                props = feat.get("properties", {})
                slug = props.get("year_bin_slug")
                if not slug or slug == "title":
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
                PER_BIN_MW[slug] = period_kw / 1000.0
                prev = slug

            print(f"[INFO] Loaded PERIOD Installed Power (MW) for {len(PER_BIN_MW)} bins (diff of cumulative).")
        except Exception as e:
            print(f"[WARN] Could not compute PER_BIN_MW: {e}")
            PER_BIN_MW = {}

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

        # Row chart subset up to this bin
        if chart_exists:
            chart_lyr = QgsVectorLayer(str(CHART_PATH), f"yearly_rowChart_{slug}", "ogr")
            if chart_lyr.isValid():
                idx = YEAR_SLUGS.index(slug)
                allowed = YEAR_SLUGS[:idx + 1]
                allowed_str = ",".join(f"'{s}'" for s in allowed)
                expr = f"(\"year_bin_slug\" IN ({allowed_str}) OR \"year_bin_slug\" = 'title')"
                chart_lyr.setSubsetString(expr)

                style_row_chart(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)

        # Heading (main + Installed Power)
        add_year_heading(bin_group, slug, YEAR_LABEL_MAP[slug], PER_BIN_MW.get(slug))

    print("[DONE] Thüringen statewise Landkreis pies (yearly) loaded and styled.")


main()
