# Filename: 3_style_landkreisPieChart_yearly.py
# QGIS 3.10 / Python 3.7 SAFE
# Nationwide Landkreis – Yearly PieCharts
# Fully mirrors 2_style_statewise_landkreisPieChart_yearly.py

from pathlib import Path
import json

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsFillSymbol,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsRuleBasedLabeling,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsFeature,
    QgsGeometry,
)
from qgis.PyQt.QtGui import QColor, QFont

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

ROOT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly"
)

CHART_PATH  = ROOT_DIR / "de_yearly_totals_chart.geojson"
LEGEND_PATH = ROOT_DIR / "de_energy_legend_points.geojson"

GROUP_NAME = "landkreis_pies (yearly)"

# ------------------------------------------------------------
# YEAR BINS (ORDER IS CRITICAL)
# ------------------------------------------------------------

YEAR_BINS = [
    ("pre_1990",  "≤1990"),
    ("1991_1992", "1991–1992"),
    ("1993_1994", "1993–1994"),
    ("1995_1996", "1995–1996"),
    ("1997_1998", "1997–1998"),
    ("1999_2000", "1999–2000"),
    ("2001_2002", "2001–2002"),
    ("2003_2004", "2003–2004"),
    ("2005_2006", "2005–2006"),
    ("2007_2008", "2007–2008"),
    ("2009_2010", "2009–2010"),
    ("2011_2012", "2011–2012"),
    ("2013_2014", "2013–2014"),
    ("2015_2016", "2015–2016"),
    ("2017_2018", "2017–2018"),
    ("2019_2020", "2019–2020"),
    ("2021_2022", "2021–2022"),
    ("2023_2024", "2023–2024"),
    ("2025_2026", "2025–2026"),
]

YEAR_SLUGS = [s for s, _ in YEAR_BINS]

# ------------------------------------------------------------
# COLOR PALETTE (IDENTICAL FAMILY)
# ------------------------------------------------------------

PALETTE = {
    "pv_kw":      QColor(255, 255,   0, 255),
    "battery_kw": QColor(148,  87, 235, 255),
    "wind_kw":    QColor(173, 216, 230, 255),
    "hydro_kw":   QColor(  0,   0, 255, 255),
    "biogas_kw":  QColor(  0, 190,   0, 255),
    "others_kw":  QColor(158, 158, 158, 255),
}

proj = QgsProject.instance()
root = proj.layerTreeRoot()

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def ensure_group(parent, name):
    grp = parent.findGroup(name)
    if grp is None:
        grp = parent.addGroup(name)
    return grp


def set_text_style(pal, size, bold=False, color=QColor(0, 0, 0), buffer=True):
    fmt = QgsTextFormat()
    fmt.setFont(QFont("Arial", size, QFont.Bold if bold else QFont.Normal))
    fmt.setSize(size)
    fmt.setColor(color)

    buf = QgsTextBufferSettings()
    buf.setEnabled(buffer)
    buf.setSize(0.8)
    buf.setColor(QColor(255, 255, 255))
    fmt.setBuffer(buf)

    pal.setFormat(fmt)

# ------------------------------------------------------------
# PIE POLYGONS
# ------------------------------------------------------------

def style_pie_polygons(layer):
    cats = []
    for key, col in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{col.red()},{col.green()},{col.blue()},255",
            "outline_style": "no",
        })
        cats.append(QgsRendererCategory(key, sym, key))

    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()

# ------------------------------------------------------------
# ENERGY LEGEND
# ------------------------------------------------------------

def style_energy_legend(layer):
    cats = []
    for key, col in PALETTE.items():
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "size": "3",
            "color": f"{col.red()},{col.green()},{col.blue()},255",
            "outline_style": "no",
        })
        cats.append(QgsRendererCategory(key, sym, key))
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    OFFSETS = {
        "Photovoltaics": 12.5,
        "Onshore Wind Energy": 18.0,
        "Hydropower": 12.5,
        "Biogas": 9.0,
        "Battery": 9.0,
        "Others": 9.0,
    }

    for lbl, xoff in OFFSETS.items():
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.fieldName = "legend_label"
        pal.xOffset = xoff
        pal.placement = QgsPalLayerSettings.OverPoint
        set_text_style(pal, size=8)

        rule = QgsRuleBasedLabeling.Rule(pal)
        rule.setFilterExpression(f"\"legend_label\"='{lbl}'")
        root_rule.appendChild(rule)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)

# ------------------------------------------------------------
# ROW CHART
# ------------------------------------------------------------

def style_row_chart(layer):
    cats = []
    for key, col in PALETTE.items():
        sym = QgsFillSymbol.createSimple({
            "color": f"{col.red()},{col.green()},{col.blue()},220",
            "outline_style": "no",
        })
        cats.append(QgsRendererCategory(key, sym, key))
    layer.setRenderer(QgsCategorizedSymbolRenderer("energy_type", cats))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # year label
    pal_y = QgsPalLayerSettings()
    pal_y.enabled = True
    pal_y.isExpression = True
    pal_y.fieldName = 'CASE WHEN "label_anchor"=1 THEN "year_bin_label" END'
    pal_y.placement = QgsPalLayerSettings.OverPoint
    set_text_style(pal_y, size=7)

    r_y = QgsRuleBasedLabeling.Rule(pal_y)
    r_y.setFilterExpression('"label_anchor"=1')
    root_rule.appendChild(r_y)

    # MW label
    pal_v = QgsPalLayerSettings()
    pal_v.enabled = True
    pal_v.isExpression = True
    pal_v.fieldName = (
        'CASE WHEN "value_anchor"=1 '
        'THEN format_number("total_kw"/1000,1) || \' MW\' END'
    )
    pal_v.placement = QgsPalLayerSettings.OverPoint
    set_text_style(pal_v, size=7)

    r_v = QgsRuleBasedLabeling.Rule(pal_v)
    r_v.setFilterExpression('"value_anchor"=1')
    root_rule.appendChild(r_v)

    # title
    pal_t = QgsPalLayerSettings()
    pal_t.enabled = True
    pal_t.isExpression = True
    pal_t.fieldName = 'CASE WHEN "year_bin_slug"=\'title\' THEN "year_bin_label" END'
    pal_t.placement = QgsPalLayerSettings.OverPoint
    set_text_style(pal_t, size=9, bold=True)

    r_t = QgsRuleBasedLabeling.Rule(pal_t)
    r_t.setFilterExpression('"year_bin_slug"=\'title\'')
    root_rule.appendChild(r_t)

    layer.setLabeling(QgsRuleBasedLabeling(root_rule))
    layer.setLabelsEnabled(True)

# ------------------------------------------------------------
# YEAR HEADING (MEMORY LAYER)
# ------------------------------------------------------------

def add_year_heading(group, slug, label, installed_mw):
    uri = "Point?crs=EPSG:4326&field=kind:string&field=label:string"
    lyr = QgsVectorLayer(uri, slug + "_heading", "memory")
    pr = lyr.dataProvider()

    feats = []

    f1 = QgsFeature(lyr.fields())
    f1.setGeometry(QgsGeometry.fromWkt("POINT(9.5 55.0)"))
    f1["kind"] = "main"
    f1["label"] = label
    feats.append(f1)

    if installed_mw is not None:
        f2 = QgsFeature(lyr.fields())
        f2.setGeometry(QgsGeometry.fromWkt("POINT(16.0 54.9)"))
        f2["kind"] = "sub"
        f2["label"] = "Installed Power: %.1f MW" % installed_mw
        feats.append(f2)

    pr.addFeatures(feats)
    lyr.updateExtents()

    sym = QgsMarkerSymbol.createSimple({"size": "0.01", "color": "0,0,0,0"})
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    for kind, size, bold in [("main", 20, True), ("sub", 12, False)]:
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = True
        pal.fieldName = 'CASE WHEN "kind"=\'%s\' THEN "label" END' % kind
        pal.placement = QgsPalLayerSettings.OverPoint
        set_text_style(pal, size=size, bold=bold, color=QColor(60,60,60))

        r = QgsRuleBasedLabeling.Rule(pal)
        r.setFilterExpression('"kind"=\'%s\'' % kind)
        root_rule.appendChild(r)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)

    proj.addMapLayer(lyr, False)
    group.addLayer(lyr)

# ------------------------------------------------------------
# READ INSTALLED MW
# ------------------------------------------------------------

def read_installed_mw():
    out = {}
    if not CHART_PATH.exists():
        return out
    data = json.loads(CHART_PATH.read_text(encoding="utf-8"))
    for f in data.get("features", []):
        p = f.get("properties", {})
        if p.get("label_anchor") == 1:
            slug = p.get("year_bin_slug")
            if slug in YEAR_SLUGS:
                out[slug] = float(p.get("total_kw", 0)) / 1000.0
    return out

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def main():
    old = root.findGroup(GROUP_NAME)
    if old:
        root.removeChildNode(old)

    main_group = ensure_group(root, GROUP_NAME)

    # legend
    if LEGEND_PATH.exists():
        leg = QgsVectorLayer(str(LEGEND_PATH), "energy_legend", "ogr")
        style_energy_legend(leg)
        proj.addMapLayer(leg, False)
        main_group.addLayer(leg)

    installed = read_installed_mw()

    for slug, label in YEAR_BINS:
        grp = ensure_group(main_group, label)

        pie_path = ROOT_DIR / slug / ("de_landkreis_pie_%s.geojson" % slug)
        if not pie_path.exists():
            continue

        pies = QgsVectorLayer(str(pie_path), "pies_" + slug, "ogr")
        style_pie_polygons(pies)
        proj.addMapLayer(pies, False)
        grp.addLayer(pies)

        if CHART_PATH.exists():
            chart = QgsVectorLayer(str(CHART_PATH), "chart_" + slug, "ogr")
            allowed = YEAR_SLUGS[:YEAR_SLUGS.index(slug)+1]
            flt = ",".join(["'%s'" % s for s in allowed])
            chart.setSubsetString(
                "(\"year_bin_slug\" IN (%s) OR \"year_bin_slug\"='title')" % flt
            )
            style_row_chart(chart)
            proj.addMapLayer(chart, False)
            grp.addLayer(chart)

        add_year_heading(grp, slug, label, installed.get(slug))

    print("[DONE] 3_style_landkreisPieChart_yearly loaded (QGIS 3.10 safe)")

main()
