# Filename: 1_style_statePieChart_yearly.py
# Purpose : Auto-load & style STATE pies for ALL year bins into nested groups:
#           "state_pies (yearly)" -> <Year bin label> ->
#               - de_state_pie_<bin>   (pie polygons)
#               - de_state_pies_<bin>  (pie centers with state_number)
#               - yearly_rowChart_total_power_<bin> (subset of row chart up to that bin)
#           Also load:
#               - HUD state-number grid (de_state_numbers_fixed.geojson)

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsVectorLayerSimpleLabeling, QgsPalLayerSettings, QgsTextFormat,
    QgsTextBufferSettings, QgsProperty, QgsMarkerSymbol,
    QgsSingleSymbolRenderer, QgsUnitTypes, QgsRuleBasedLabeling, Qgis,
    QgsFeature, QgsGeometry, QgsPointXY
)
from qgis.PyQt.QtGui import QColor, QFont
from pathlib import Path
import json
import re

# ---------- SETTINGS ----------
ROOT_DIR   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly")
GROUP_NAME = "state_pies (yearly)"

SHOW_SLICE_LABELS    = False      # labels on pie polygons (anchor slice)
LOAD_CENTER_POINTS   = True       # load de_state_pies_<bin>.geojson
LABEL_CENTER_NUMBERS = True       # label center points with state_number
LOAD_HUD_LAYER       = True       # load de_state_numbers_fixed.geojson
LOAD_YEARLY_CHART    = True       # load yearly_rowChart_total_power.geojson per bin
LOAD_YEAR_OVERVIEW   = True
LOAD_ENERGY_LEGEND   = True


# Global yearly totals chart (all years, all energies)
YEARLY_CHART_PATH = ROOT_DIR / "de_yearly_totals_chart.geojson"

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

# Year-bin slug order, used for cumulative filters of the chart per bin
YEAR_SLUG_ORDER = [
    "pre_1990",
    "1991_1992",
    "1993_1994",
    "1995_1996",
    "1997_1998",
    "1999_2000",
    "2001_2002",
    "2003_2004",
    "2005_2006",
    "2007_2008",
    "2009_2010",
    "2011_2012",
    "2013_2014",
    "2015_2016",
    "2017_2018",
    "2019_2020",
    "2021_2022",
    "2023_2024",
    "2025_2026",
]

# slug -> label map
YEAR_LABEL_MAP = {slug: label for (slug, label, _y1, _y2) in YEAR_BINS}

# Order for cumulative filter on the chart
YEAR_SLUG_ORDER = [slug for (slug, _label, _y1, _y2) in YEAR_BINS]

# Slice / energy palette (shared with pies and chart)
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

YEARLY_CHART_PATH = ROOT_DIR / "de_yearly_totals_chart.geojson"


# which energy types count for totals (still used in other places if needed)
ENERGY_KEYS = ["pv_kw", "battery_kw", "wind_kw", "hydro_kw", "biogas_kw", "others_kw"]

# PER_BIN_GW: per 2-year bin PERIOD installed power (GW)
# Robust: compute as difference of cumulative totals between consecutive bins.
PER_BIN_GW = {}

# CUM_BIN_GW: per bin CUMULATIVE installed power (GW)
CUM_BIN_GW = {}


try:
    if YEARLY_CHART_PATH.exists():
        with open(str(YEARLY_CHART_PATH), "r", encoding="utf-8") as f:
            chart = json.load(f)

        # 1) Read cumulative totals from value_anchor=1 points
        cum_kw = {}  # slug -> cumulative kW
        for feat in chart.get("features", []):
            props = feat.get("properties", {})
            slug = props.get("year_bin_slug")
            if not slug or slug == "title":
                continue

            if str(props.get("value_anchor")) != "1":
                continue

            val = props.get("total_kw", 0.0)
            try:
                cum_kw[slug] = float(val)
            except Exception:
                continue

        # Store cumulative GW directly (for headings)
        for slug, val_kw in cum_kw.items():
            try:
                CUM_BIN_GW[slug] = float(val_kw) / 1000000.0
            except Exception:
                pass


        # 2) Convert cumulative -> period via diff along YEAR_SLUG_ORDER
        prev = None
        for slug in YEAR_SLUG_ORDER:
            if slug not in cum_kw:
                continue
            if prev is None:
                period_kw = cum_kw[slug]  # first bin: period == cumulative
            else:
                period_kw = cum_kw[slug] - cum_kw.get(prev, 0.0)

            PER_BIN_GW[slug] = period_kw / 1000000.0  # GW
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


def style_state_pie_layer(lyr: QgsVectorLayer):
    """Categorized pie polygons by energy_type; optional anchor labels."""
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


def style_center_layer(lyr: QgsVectorLayer, label_numbers: bool = True):
    """
    Style for pie center points:

    - marker invisible (only pies visible)
    - state_number labels with per-state offset:

      A) 3 Berlin, 5 Bremen, 6 Hamburg   -> center (0, 0)
      B) 12 Saarland                     -> x=-3.5,  y=-2.0
      C) 1,4,7,8,9,11,13,14,16           -> x=-7,    y=-2.5
      D) 2 Bayern                        -> x=11,    y=4
      E) 10,15                           -> x=9,     y=2
    """

    # 1) Marker: fully transparent so only pies are visible
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

    # Helper to create one rule with given filter + offsets
    def make_rule(filter_expr: str, x_off: float, y_off: float) -> QgsRuleBasedLabeling.Rule:
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
        pal.fieldName = "state_number"

        pal.placement = QgsPalLayerSettings.OverPoint
        pal.xOffset = x_off
        pal.yOffset = y_off

        fmt = QgsTextFormat()
        fmt.setFont(QFont("Arial", 9))
        fmt.setSize(9)
        fmt.setColor(QColor(0, 0, 0))

        buf = QgsTextBufferSettings()
        buf.setEnabled(False)  # no halo
        fmt.setBuffer(buf)

        pal.setFormat(fmt)

        rule = QgsRuleBasedLabeling.Rule(pal)
        if filter_expr:
            rule.setFilterExpression(filter_expr)
        return rule

    # Root rule (empty base)
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # A) Berlin, Bremen, Hamburg (no offset)
    root_rule.appendChild(make_rule('"state_number" IN (3,5,6)', 0.0, 0.0))

    # B) Saarland
    root_rule.appendChild(make_rule('"state_number" = 12', -3.5, -2.0))

    # C) 1,4,7,8,9,11,13,14,16
    root_rule.appendChild(make_rule('"state_number" IN (1,4,7,8,9,11,13,14,16)', -7.0, -2.5))

    # D) Bayern
    root_rule.appendChild(make_rule('"state_number" = 2', 11.0, 4.0))

    # E) 10,15
    root_rule.appendChild(make_rule('"state_number" IN (10,15)', 9.0, 2.0))

    labeling = QgsRuleBasedLabeling(root_rule)
    lyr.setLabeling(labeling)
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()

def style_hud_layer(lyr: QgsVectorLayer):
    """
    HUD layer with per-row (row_index) offset control.
    User can manually define xOffset per row.
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

    # ---- SIMPLE labeling (no rules) ----
    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = 'to_string("state_number") || \'  \' || "state_name"'
    pal.placement = QgsPalLayerSettings.OverPoint

    # tek kolon hizalama
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


def style_energy_legend_layer(lyr: QgsVectorLayer):
    """
    Left-top energy legend with per-label X offset using rule-based labeling.
    Fully QGIS 3.10 compatible.
    """

    # --- SYMBOLS (renkli daireler) ---
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

    # note row is transparent
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

    # ----------------------------------------
    # RULE-BASED LABELING (QGIS 3.10 SAFE)
    # ----------------------------------------
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    def add_label_rule(filter_expr: str, x_offset: float):
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = False
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

    # ---- Senin offset değerlerini uyguluyoruz ----
    add_label_rule('"legend_label" = \'Photovoltaics\'',        12.5)
    add_label_rule('"legend_label" = \'Onshore Wind Energy\'',  18.0)
    add_label_rule('"legend_label" = \'Hydropower\'',           12.5)
    add_label_rule('"legend_label" = \'Biogas\'',                9.0)
    add_label_rule('"legend_label" = \'Battery\'',               9.0)
    add_label_rule('"legend_label" = \'Others\'',                9.0)

    # "legend_note" satırı (isteğe bağlı)
    add_label_rule('"energy_type" = \'legend_note\'',            6.0)

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
    lyr.triggerRepaint()


def style_yearly_chart_layer(lyr: QgsVectorLayer):
    """
    Styling for the ROW chart:
      - stacked bar polygons color-coded by energy_type
      - year labels on left  (POINTs with label_anchor = 1)
      - GW labels on right  (POINTs with value_anchor = 1)
    """

    fields = [f.name() for f in lyr.fields()]
    energy_field = "energy_type" if "energy_type" in fields else None

    # --- polygon coloring ---
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

        # heading_* kategorileri hiç eklemiyoruz → legend'da sadece energy types
        lyr.setRenderer(QgsCategorizedSymbolRenderer(energy_field, cats))
    else:
        sym = QgsFillSymbol.createSimple({
            "color": "200,200,200,200",
            "outline_style": "no",
            "outline_color": "0,0,0,0",
            "outline_width": "0"
        })
        lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    # ---------- LABELS ----------
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # (1) YEAR LABELS (POINTS)
    year_pal = QgsPalLayerSettings()
    year_pal.enabled = True
    year_pal.isExpression = True
    year_pal.fieldName = (
        'CASE WHEN "label_anchor" = 1 THEN "year_bin_label" ELSE NULL END'
    )

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

    # (2) VALUE LABELS (POINTS) – sağdaki küçük GW değerleri
    value_pal = QgsPalLayerSettings()
    value_pal.enabled = True
    value_pal.isExpression = True
    value_pal.fieldName = (
        'CASE WHEN "value_anchor" = 1 '
        'THEN format_number("total_kw" / 1000000.00, 1) || \' GW\' '
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

    # (3) CHART TITLE (POINT: year_bin_slug = 'title')
    title_pal = QgsPalLayerSettings()
    title_pal.enabled = True
    title_pal.isExpression = True
    title_pal.fieldName = (
        'CASE WHEN "year_bin_slug" = \'title\' '
        'THEN "year_bin_label" ELSE NULL END'
    )

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

    lyr.setLabeling(QgsRuleBasedLabeling(root_rule))
    lyr.setLabelsEnabled(True)
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

def add_year_heading(parent_group: QgsLayerTreeGroup, slug: str, label_text: str):
    """
    Create one in-memory point layer with TWO labels:
      - main year heading (big, bold)
      - subheading: Installed Power for this period (GW), smaller text
    """

    uri = (
        "Point?crs=EPSG:4326"
        "&field=kind:string(10)"
        "&field=label:string(200)"
        "&index=yes"
    )
    lyr = QgsVectorLayer(uri, f"{slug}_heading", "memory")
    prov = lyr.dataProvider()

    # ---- UPDATED COORDINATES (STEP1_3 ile tam uyumlu) ----
    X_MAIN = 9.5
    Y_MAIN = 55.0

    X_SUB = 16.0
    Y_SUB = 54.9

    feats = []

    # --- main heading ---
    f_main = QgsFeature(lyr.fields())
    f_main.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_MAIN, Y_MAIN)))
    f_main["kind"] = "main"
    f_main["label"] = label_text
    feats.append(f_main)
    
    # --- sub heading ---
    f_sub = QgsFeature(lyr.fields())
    f_sub.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X_SUB, Y_SUB)))
    f_sub["kind"] = "sub"
    # f_sub["label"] will be assigned below (sub_text)
    feats.append(f_sub)



    # --- subheading: CUMULATIVE Installed Power (GW) ---
    gw_cum = CUM_BIN_GW.get(slug)
    gw_per = PER_BIN_GW.get(slug)


    sub_text = f"Installed Power: {gw_per:,.1f} GW"
    f_sub["label"] = sub_text



    prov.addFeatures(feats)
    lyr.updateExtents()

    # invisible marker
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "0.01",
        "color": "0,0,0,0",
        "outline_style": "no",
        "outline_color": "0,0,0,0",
        "outline_width": "0"
    })
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))

    # rule-based labels
    root_rule = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

    # main heading style
    pal_main = QgsPalLayerSettings()
    pal_main.enabled = True
    pal_main.isExpression = True
    pal_main.fieldName = 'CASE WHEN "kind" = \'main\' THEN "label" ELSE NULL END'

    fmt_main = QgsTextFormat()
    fmt_main.setFont(QFont("Arial", 20, QFont.Bold))
    fmt_main.setSize(20)
    fmt_main.setColor(QColor(0, 0, 0))
    fmt_main.setBuffer(QgsTextBufferSettings())
    pal_main.setFormat(fmt_main)

    rule_main = QgsRuleBasedLabeling.Rule(pal_main)
    rule_main.setFilterExpression('"kind" = \'main\'')
    root_rule.appendChild(rule_main)

    # subheading style
    pal_sub = QgsPalLayerSettings()
    pal_sub.enabled = True
    pal_sub.isExpression = True
    pal_sub.fieldName = 'CASE WHEN "kind" = \'sub\' THEN "label" ELSE NULL END'

    fmt_sub = QgsTextFormat()
    fmt_sub.setFont(QFont("Arial", 12, QFont.Bold))
    fmt_sub.setSize(12)
    fmt_sub.setColor(QColor(60, 60, 60))
    fmt_sub.setBuffer(QgsTextBufferSettings())
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

    # HUD layer (once)
    if LOAD_HUD_LAYER:
        hud_path = ROOT_DIR / "de_state_numbers_fixed.geojson"
        if hud_path.exists():
            hud_lyr = QgsVectorLayer(str(hud_path), "de_state_numbers_fixed", "ogr")
            if hud_lyr.isValid():
                style_hud_layer(hud_lyr)
                proj.addMapLayer(hud_lyr, False)
                parent_group.addLayer(hud_lyr)
        else:
            print(f"[WARN] HUD layer not found: {hud_path}")

    # Optional overview layer (if you have one, otherwise silently skip)
    if LOAD_YEAR_OVERVIEW:
        overview_path = ROOT_DIR / "de_year_overview_points.geojson"
        if overview_path.exists():
            ov_lyr = QgsVectorLayer(str(overview_path), "year_overview", "ogr")
            if ov_lyr.isValid():
                style_year_overview_layer(ov_lyr)
                proj.addMapLayer(ov_lyr, False)
                parent_group.addLayer(ov_lyr)

    # We will re-use the same global chart file, subset per bin
    chart_exists = YEARLY_CHART_PATH.exists()

        # Energy legend layer (top-left)
    if LOAD_ENERGY_LEGEND:
        legend_path = ROOT_DIR / "de_energy_legend_points.geojson"
        if legend_path.exists():
            legend_lyr = QgsVectorLayer(str(legend_path), "energy_legend", "ogr")
            if legend_lyr.isValid():
                style_energy_legend_layer(legend_lyr)
                QgsProject.instance().addMapLayer(legend_lyr, False)
                parent_group.addLayer(legend_lyr)
        else:
            print(f"[WARN] Energy legend file not found: {legend_path}")


    # All bin directories
    bin_dirs = [p for p in ROOT_DIR.iterdir() if p.is_dir()]
    bin_dirs = sorted(bin_dirs, key=bin_sort_key)

    for bin_dir in bin_dirs:
        slug = bin_dir.name
        label = pretty_year_label(bin_dir)

        # Group per year bin
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

        # ----- YEARLY CHART (subset) -----
        if LOAD_YEARLY_CHART and chart_exists:
            chart_lyr = QgsVectorLayer(str(YEARLY_CHART_PATH), f"yearly_rowChart_total_power_{slug}", "ogr")
            if chart_lyr.isValid():
                # cumulative filter: all slugs up to current one
                if slug in YEAR_SLUG_ORDER:
                    idx = YEAR_SLUG_ORDER.index(slug)
                    allowed = YEAR_SLUG_ORDER[:idx+1]

                    allowed_list = ",".join(f"'{s}'" for s in allowed)

                    # title feature’ını da her zaman tut
                    expr = (
                        f"(\"year_bin_slug\" IN ({allowed_list}) "
                        f"OR \"year_bin_slug\" = 'title')"
                    )

                    chart_lyr.setSubsetString(expr)

                style_yearly_chart_layer(chart_lyr)
                proj.addMapLayer(chart_lyr, False)
                bin_group.addLayer(chart_lyr)
        elif LOAD_YEARLY_CHART and not chart_exists:
            print(f"[WARN] Global yearly chart file not found: {YEARLY_CHART_PATH}")

        # ----- YEAR HEADING (BIG TITLE) -----
        add_year_heading(bin_group, slug, label)


main()