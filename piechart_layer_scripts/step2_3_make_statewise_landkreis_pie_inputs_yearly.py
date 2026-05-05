# Filename: step2_3_make_statewise_landkreis_pie_inputs_yearly.py
# Purpose :
#   Yearly LANDKREIS pie INPUT POINTS for all states, using AGS-based centers (step2_0 centers file).
#
#   REQUIREMENTS COVERED (aligned with step1_3):
#   - 2-year bins → pies are CUMULATIVE over time (size grows monotonically).
#   - Germany-wide ROW chart (cumulative) with:
#       * title
#       * dashed guidelines as a separate LineString layer
#       * frame (rectangle) as a polygon layer
#   - State COLUMN chart (cumulative) added with SAME coordinates as step1_3:
#       * bars (polygons) + labels (points)
#       * frame (rectangle)
#       * x-axis labels use 2-letter state abbreviations
#   - Energy type legend + pie size legend + legend frames use SAME layout as step1_3
#
#   IMPORTANT:
#   - NO state numbers / abbreviations are added on the map itself here.
#   - Pie size legend values are selected for the landkreis version (still labeled in GW).
#
#   Outputs:
#     1) OUT_DIR/<bin_slug>/de_landkreis_pies_<bin_slug>.geojson
#     2) OUT_DIR/<state_slug>/<bin_slug>/de_<state_slug>_landkreis_pies_<bin_slug>.geojson
#     3) OUT_DIR/_STATEWISE_size_meta.json
#     4) OUT_DIR/de_yearly_totals.json
#     5) OUT_DIR/de_yearly_totals_chart.geojson
#     6) OUT_DIR/de_yearly_totals_chart_guides.geojson
#     7) OUT_DIR/de_yearly_totals_chart_frame.geojson
#     8) OUT_DIR/de_state_totals_columnChart_bars.geojson
#     9) OUT_DIR/de_state_totals_columnChart_labels.geojson
#    10) OUT_DIR/de_state_totals_columnChart_frame.geojson
#    11) OUT_DIR/de_energy_legend_points.geojson
#    12) OUT_DIR/de_pie_size_legend_circles.geojson
#    13) OUT_DIR/de_pie_size_legend_labels.geojson
#    14) OUT_DIR/de_legend_frames.geojson

from pathlib import Path
import os
import re
import json
import unicodedata
import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, LineString
from pyproj import Transformer

# ------------------------------ PATHS ------------------------------

INPUT_ROOT = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis_yearly"
)

OUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies_yearly"
)

CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\landkreis_centers\de_landkreis_centers.geojson"
)

# ------------------------------ YEAR BINS ------------------------------
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
BIN_LABEL = {slug: lbl for slug, lbl, *_ in YEAR_BINS}

# ------------------------------ ENERGY ------------------------------
ENERGY_CODE_TO_LABEL = {
    "2403": "Tiefe Geothermie",
    "2405": "Klärgas",
    "2406": "Druckentspannung",
    "2493": "Biogas",
    "2495": "Photovoltaik",
    "2496": "Stromspeicher (Battery Storage)",
    "2497": "Windenergie Onshore",
    "2498": "Wasserkraft",
}

PRIORITY = {
    "Photovoltaik": "pv_kw",
    "Windenergie Onshore": "wind_kw",
    "Wasserkraft": "hydro_kw",
    "Stromspeicher (Battery Storage)": "battery_kw",
    "Biogas": "biogas_kw",
}
OTHERS = "others_kw"

PART_FIELDS = [
    "pv_kw",
    "wind_kw",
    "hydro_kw",
    "battery_kw",
    "biogas_kw",
    "others_kw",
]

# Keep synchronized with step2_4
R_MIN_M = 5000.0
R_MAX_M = 30000.0

# ------------------------------ STATE ORDER / LABELS ------------------------------
STATE_SLUG_TO_NUMBER = {
    "baden-wuerttemberg": 1,
    "bayern": 2,
    "berlin": 3,
    "brandenburg": 4,
    "bremen": 5,
    "hamburg": 6,
    "hessen": 7,
    "mecklenburg-vorpommern": 8,
    "niedersachsen": 9,
    "nordrhein-westfalen": 10,
    "rheinland-pfalz": 11,
    "saarland": 12,
    "sachsen": 13,
    "sachsen-anhalt": 14,
    "schleswig-holstein": 15,
    "thueringen": 16,
    "thüringen": 16,
    "thuringen": 16,
}

STATE_SLUG_TO_ABBREV = {
    "baden-wuerttemberg": "BW",
    "bayern": "BY",
    "berlin": "BE",
    "brandenburg": "BB",
    "bremen": "HB",
    "hamburg": "HH",
    "hessen": "HE",
    "mecklenburg-vorpommern": "MV",
    "niedersachsen": "NI",
    "nordrhein-westfalen": "NW",
    "rheinland-pfalz": "RP",
    "saarland": "SL",
    "sachsen": "SN",
    "sachsen-anhalt": "ST",
    "schleswig-holstein": "SH",
    "thueringen": "TH",
    "thüringen": "TH",
    "thuringen": "TH",
}

# ------------------------------ SHARED TEXT / LEGEND LAYOUT (match step1_3) ------------------------------
UNIFIED_TITLE_TEXT = {
    "energy_legend": "Energy Type Color Legend",
    "pie_size_legend": "Pie Size Legend",
    "row_chart": "Cumulative Installed Power (2-Year Periods)",
    "column_chart": "Cumulative Installed Power by State (GW)",
}

# Same coordinates / same frame sizes as step1_3 for all legends + charts (except pie size legend which is separate)
LEGEND_R_MIN_M = 5000.0
LEGEND_R_MAX_M = 30000.0
PIE_LEGEND_VALUES_GW = [0.1, 0.5, 1, 2, 3]  # selected for landkreis version
PIE_LEGEND_CENTER_LON = 3.0
PIE_LEGEND_TOP_LAT = 54.8
PIE_LEGEND_LABEL_DX_DEG = 1.2
PIE_LEGEND_TITLE_LAT = 55.10
PIE_LEGEND_EXTRA_GAP_M = 22000.0

LEG_BASE_LON = -2.85
LEG_TOP_LAT = 54.8
LEG_ROW_STEP = -0.3
LEGEND_TITLE_LAT = PIE_LEGEND_TITLE_LAT - 0.1

LEGEND_FRAME_YMAX = 55.35
LEGEND_FRAME_YMIN = 53.10

ENERGY_FRAME_XMIN = -3.45
ENERGY_FRAME_XMAX = 0.65

PIE_FRAME_XMIN = 1.85
PIE_FRAME_XMAX = 5.95

# ------------------------------ HELPERS ------------------------------
def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def extract_ags5(row: pd.Series):
    for cand in (
        "Gemeindeschluessel",
        "gemeindeschluessel",
        "AGS",
        "ags",
        "ags_id",
        "kreisschluessel",
        "rs",
    ):
        if cand in row and pd.notna(row[cand]):
            digits = re.sub(r"[^0-9]", "", str(row[cand]))
            if len(digits) >= 5:
                return digits[:5]
    return None


def parse_number(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def energy_norm(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]
        sn = norm(s)
        if "solar" in sn or "photovolta" in sn or sn == "pv":
            return "Photovoltaik"
        if "wind" in sn:
            return "Windenergie Onshore"
        if "wasser" in sn or "hydro" in sn:
            return "Wasserkraft"
        if "stromspeicher" in sn or "speicher" in sn or "battery" in sn:
            return "Stromspeicher (Battery Storage)"
        if "biogas" in sn or sn == "gas":
            return "Biogas"

    fn = norm(filename_hint)
    if "solar" in fn or "photovolta" in fn or "pv" in fn:
        return "Photovoltaik"
    if "wind" in fn:
        return "Windenergie Onshore"
    if "wasser" in fn or "hydro" in fn:
        return "Wasserkraft"
    if "stromspeicher" in fn or "speicher" in fn or "battery" in fn:
        return "Stromspeicher (Battery Storage)"
    if "biogas" in fn:
        return "Biogas"
    return "Unknown"


DATE_CANDS = [
    "Inbetriebnahmedatum",
    "commissioning_date",
    "Baujahr",
    "year",
    "Year",
    "YEAR",
    "Inbetriebnahme",
]


def extract_year(row, filename=""):
    for col in DATE_CANDS:
        if col in row and pd.notna(row[col]):
            s = str(row[col]).strip()
            m = re.search(r"(19|20)\d{2}", s)
            if m:
                y = int(m.group(0))
                if 1900 <= y <= 2100:
                    return y
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if pd.notna(dt):
                    return int(dt.year)
            except Exception:
                pass

    m = re.search(r"(19|20)\d{2}", filename)
    if m:
        y = int(m.group(0))
        if 1900 <= y <= 2100:
            return y
    return None


def year_to_bin(y):
    if y is None:
        return ("unknown", "Unknown / NA")
    for slug, lbl, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return (slug, lbl)
    return ("unknown", "Unknown / NA")


def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


def load_centers():
    if not CENTERS_PATH.exists():
        raise RuntimeError(f"Centers file not found: {CENTERS_PATH}")
    g = gpd.read_file(CENTERS_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    centers = {}
    state_by_ags = {}
    for _, r in g.iterrows():
        ags = str(r.get("ags5", "")).strip()
        if not ags:
            continue
        centers[ags] = (float(r.geometry.x), float(r.geometry.y))
        state_by_ags[ags] = str(r.get("state_slug", "")).strip()
    print(f"[CENTERS] Loaded {len(centers)} centers from {CENTERS_PATH}")
    return centers, state_by_ags


def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:
        return (omin + omax) / 2.0
    t = (val - vmin) / (vmax - vmin)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return omin + t * (omax - omin)


def make_circle_polygon_lonlat(center_lon, center_lat, radius_m, n=128):
    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    cxm, cym = to_m.transform(center_lon, center_lat)
    pts = []
    for i in range(n + 1):
        ang = 2.0 * math.pi * i / n
        x = cxm + radius_m * math.cos(ang)
        y = cym + radius_m * math.sin(ang)
        lon, lat = to_deg.transform(x, y)
        pts.append((lon, lat))
    return Polygon(pts)


def write_pie_size_legend(global_min_kw, global_max_kw):
    circle_rows = []
    label_rows = []

    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    center_lon = PIE_LEGEND_CENTER_LON
    center_x_m, top_y_m = to_m.transform(center_lon, PIE_LEGEND_TOP_LAT)

    prev_radius_m = None
    current_center_y_m = top_y_m

    for idx, gw in enumerate(PIE_LEGEND_VALUES_GW):
        total_kw = float(gw) * 1_000_000.0
        radius_m = scale_linear(total_kw, global_min_kw, global_max_kw, LEGEND_R_MIN_M, LEGEND_R_MAX_M)

        if idx == 0:
            current_center_y_m = top_y_m
        else:
            current_center_y_m = (
                current_center_y_m
                - prev_radius_m
                - radius_m
                - PIE_LEGEND_EXTRA_GAP_M
            )

        center_lon_item, center_lat_item = to_deg.transform(center_x_m, current_center_y_m)

        circle_rows.append({
            "legend_gw": float(gw),
            "legend_kw": total_kw,
            "radius_m": radius_m,
            "legend_label": f"{gw:g} GW",
            "geometry": make_circle_polygon_lonlat(center_lon_item, center_lat_item, radius_m),
        })

        label_rows.append({
            "kind": "item",
            "legend_gw": float(gw),
            "legend_kw": total_kw,
            "radius_m": radius_m,
            "legend_label": f"{gw:g} GW",
            "geometry": Point(center_lon_item + PIE_LEGEND_LABEL_DX_DEG, center_lat_item),
        })

        prev_radius_m = radius_m

    label_rows.append({
        "kind": "title",
        "legend_gw": 0.0,
        "legend_kw": 0.0,
        "radius_m": 0.0,
        "legend_label": UNIFIED_TITLE_TEXT["pie_size_legend"],
        "geometry": Point(PIE_LEGEND_CENTER_LON + 0.20, PIE_LEGEND_TITLE_LAT),
    })

    circles_gdf = gpd.GeoDataFrame(circle_rows, geometry="geometry", crs="EPSG:4326")
    labels_gdf = gpd.GeoDataFrame(label_rows, geometry="geometry", crs="EPSG:4326")

    circles_path = OUT_DIR / "de_pie_size_legend_circles.geojson"
    labels_path = OUT_DIR / "de_pie_size_legend_labels.geojson"

    circles_gdf.to_file(circles_path, driver="GeoJSON")
    labels_gdf.to_file(labels_path, driver="GeoJSON")

    print(f"[INFO] Wrote pie size legend circles -> {circles_path.name} ({len(circles_gdf)} features)")
    print(f"[INFO] Wrote pie size legend labels  -> {labels_path.name} ({len(labels_gdf)} features)")


def write_legend_frames():
    frame_rows = [
        {
            "frame_type": "energy_legend",
            "geometry": Polygon([
                (ENERGY_FRAME_XMIN, LEGEND_FRAME_YMIN),
                (ENERGY_FRAME_XMAX, LEGEND_FRAME_YMIN),
                (ENERGY_FRAME_XMAX, LEGEND_FRAME_YMAX),
                (ENERGY_FRAME_XMIN, LEGEND_FRAME_YMAX),
                (ENERGY_FRAME_XMIN, LEGEND_FRAME_YMIN),
            ]),
        },
        {
            "frame_type": "pie_size_legend",
            "geometry": Polygon([
                (PIE_FRAME_XMIN, LEGEND_FRAME_YMIN),
                (PIE_FRAME_XMAX, LEGEND_FRAME_YMIN),
                (PIE_FRAME_XMAX, LEGEND_FRAME_YMAX),
                (PIE_FRAME_XMIN, LEGEND_FRAME_YMAX),
                (PIE_FRAME_XMIN, LEGEND_FRAME_YMIN),
            ]),
        },
    ]

    frames_gdf = gpd.GeoDataFrame(frame_rows, geometry="geometry", crs="EPSG:4326")
    frames_path = OUT_DIR / "de_legend_frames.geojson"
    frames_gdf.to_file(frames_path, driver="GeoJSON")
    print(f"[INFO] Wrote legend frames -> {frames_path.name} ({len(frames_gdf)} features)")


# ------------------------------ MAIN ------------------------------
def main():
    print("\n[step2_3] Building yearly Landkreis pie INPUTS (AGS-based).")
    if not INPUT_ROOT.exists():
        raise RuntimeError(f"INPUT_ROOT not found: {INPUT_ROOT}")

    centers, state_by_ags = load_centers()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []

    dirs = [d.name for d in INPUT_ROOT.iterdir() if d.is_dir()]
    print(f"[INFO] Found {len(dirs)} state directories: {dirs}")

    for state_dir in sorted(INPUT_ROOT.iterdir()):
        if not state_dir.is_dir():
            continue

        print(f"\n---- STATE DIR: {state_dir.name} ----")

        for p in scan_geojsons(state_dir):
            try:
                g = gpd.read_file(p)
            except Exception as e:
                print(f"  [WARN] skipped {p.name}: {e}")
                continue

            if g.empty or "geometry" not in g.columns:
                continue

            g = g[g.geometry.notnull()]
            g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])]
            if g.empty:
                continue

            try:
                if "MultiPoint" in g.geometry.geom_type.unique():
                    g = g.explode(index_parts=False).reset_index(drop=True)
            except Exception:
                g = g.explode().reset_index(drop=True)

            filename = p.name

            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(
                    lambda v: energy_norm(v, filename)
                )
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(
                    lambda v: energy_norm(v, filename)
                )
            else:
                g["energy_norm"] = energy_norm(None, filename)

            power_col = None
            for c in [
                "power_kw",
                "Nettonennleistung",
                "Bruttoleistung",
                "Nennleistung",
                "installed_power_kw",
                "Leistung",
                "kw",
                "power",
            ]:
                if c in g.columns:
                    power_col = c
                    break
            if not power_col:
                continue

            g["_power"] = g[power_col].apply(parse_number)
            g = g[(g["_power"] > 0) & pd.notna(g["_power"])]
            if g.empty:
                continue

            years = [extract_year(r, filename) for _, r in g.iterrows()]
            bins = [year_to_bin(y) for y in years]
            g["year_bin_slug"] = [b[0] for b in bins]
            g["year_bin_label"] = [b[1] for b in bins]

            for _, r in g.iterrows():
                yslug = r["year_bin_slug"]
                ylbl = r["year_bin_label"]
                if yslug == "unknown":
                    continue

                ags5 = extract_ags5(r)
                if not ags5:
                    continue
                if ags5 not in centers:
                    continue

                state_slug = state_by_ags.get(ags5, "")
                if not state_slug:
                    continue

                cx, cy = centers[ags5]

                all_rows.append(
                    {
                        "state_slug": state_slug,
                        "kreis_key": ags5,
                        "energy_norm": r["energy_norm"],
                        "_power": float(r["_power"]),
                        "year_bin_slug": yslug,
                        "year_bin_label": ylbl,
                        "_x": cx,
                        "_y": cy,
                    }
                )

    if not all_rows:
        print("[FATAL] No usable yearly rows.")
        return

    df = pd.DataFrame(all_rows)
    df = df[df["year_bin_slug"] != "unknown"]
    if df.empty:
        print("[FATAL] All rows mapped to unknown year bin.")
        return

    # ---------------- AGGREGATE PERIOD (state, kreis, bin) ----------------
    period_by_kreis_bin = {}
    kreis_center = {}

    for (state_slug, kreis_key, bin_slug), grp in df.groupby(
        ["state_slug", "kreis_key", "year_bin_slug"]
    ):
        label = grp["year_bin_label"].iloc[0]

        parts = {f: 0.0 for f in PRIORITY.values()}
        parts[OTHERS] = 0.0

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY:
                parts[PRIORITY[cat]] += pkw
            else:
                parts[OTHERS] += pkw

        parts["total_kw"] = float(sum(parts.values()))
        parts["state_slug"] = state_slug
        parts["kreis_key"] = kreis_key
        parts["year_bin_slug"] = bin_slug
        parts["year_bin_label"] = label

        any_row = grp.iloc[0]
        parts["_x"] = float(any_row["_x"])
        parts["_y"] = float(any_row["_y"])

        period_by_kreis_bin[(state_slug, kreis_key, bin_slug)] = parts
        kreis_center.setdefault((state_slug, kreis_key), (parts["_x"], parts["_y"]))

    # ---------------- BUILD CUMULATIVE (state, kreis, bin) ----------------
    cumulative_by_bin = {}
    all_cumulative_totals = []

    def _empty_parts():
        d = {f: 0.0 for f in PRIORITY.values()}
        d[OTHERS] = 0.0
        return d

    all_kreise = sorted(kreis_center.keys(), key=lambda k: (k[0], k[1]))

    for state_slug, kreis_key in all_kreise:
        running = _empty_parts()
        cx, cy = kreis_center[(state_slug, kreis_key)]

        for bin_slug, bin_label, *_ in YEAR_BINS:
            period = period_by_kreis_bin.get((state_slug, kreis_key, bin_slug), None)
            if period is not None:
                for f in PRIORITY.values():
                    running[f] += float(period.get(f, 0.0) or 0.0)
                running[OTHERS] += float(period.get(OTHERS, 0.0) or 0.0)

            total_kw = float(sum(running.values()))

            row = {
                "pv_kw": running["pv_kw"],
                "wind_kw": running["wind_kw"],
                "hydro_kw": running["hydro_kw"],
                "battery_kw": running["battery_kw"],
                "biogas_kw": running["biogas_kw"],
                "others_kw": running["others_kw"],
                "total_kw": total_kw,
                "state_slug": state_slug,
                "kreis_key": kreis_key,
                "year_bin_slug": bin_slug,
                "year_bin_label": bin_label,
                "_x": cx,
                "_y": cy,
            }

            cumulative_by_bin.setdefault(bin_slug, []).append(row)
            all_cumulative_totals.append(total_kw)

    by_bin = cumulative_by_bin

    # ---------------- STATEWISE GLOBAL MIN/MAX (ALL YEARS) ----------------
    state_stats = {}
    for bin_slug, rows in by_bin.items():
        for t in rows:
            st = t.get("state_slug")
            if not st:
                continue
            val = float(t.get("total_kw", 0.0) or 0.0)
            kreis = t.get("kreis_key", "")
            yslug = t.get("year_bin_slug", "")

            if st not in state_stats:
                state_stats[st] = {
                    "min_total_kw": val,
                    "max_total_kw": val,
                    "min_kreis_key": kreis,
                    "max_kreis_key": kreis,
                    "min_year_bin": yslug,
                    "max_year_bin": yslug,
                }
            else:
                if val < state_stats[st]["min_total_kw"]:
                    state_stats[st]["min_total_kw"] = val
                    state_stats[st]["min_kreis_key"] = kreis
                    state_stats[st]["min_year_bin"] = yslug
                if val > state_stats[st]["max_total_kw"]:
                    state_stats[st]["max_total_kw"] = val
                    state_stats[st]["max_kreis_key"] = kreis
                    state_stats[st]["max_year_bin"] = yslug

    print("\n[STATEWISE-GLOBAL-SIZE] All years (ca. 1900–2026)")
    for st in sorted(state_stats.keys()):
        info = state_stats[st]
        print(
            f"  {st:15s}  vmin={info['min_total_kw']:12,.1f} kW"
            f"  (kreis={info['min_kreis_key']}, bin={info['min_year_bin']})"
        )
        print(
            f"                 vmax={info['max_total_kw']:12,.1f} kW"
            f"  (kreis={info['max_kreis_key']}, bin={info['max_year_bin']})"
        )
        print(f"                 radii → min={R_MIN_M:,.1f} m, max={R_MAX_M:,.1f} m")

    state_meta_path = OUT_DIR / "_STATEWISE_size_meta.json"
    state_meta_path.write_text(json.dumps(state_stats, indent=2), encoding="utf-8")

    for st, info in state_stats.items():
        st_dir = OUT_DIR / st
        st_dir.mkdir(parents=True, exist_ok=True)
        vmin = float(info["min_total_kw"])
        vmax = float(info["max_total_kw"])
        (st_dir / "_STATE_META.json").write_text(
            json.dumps([vmin, vmax], indent=2), encoding="utf-8"
        )

    # ----------------------------------------------------------
    # STEP C) Write PIE INPUT POINTS (CUMULATIVE) per 2-year bin
    # ----------------------------------------------------------
    for bin_slug, bin_label, *_ in YEAR_BINS:
        rows = by_bin.get(bin_slug, [])
        if not rows:
            print(f"[SKIP] No Landkreis rows for bin {bin_slug}")
            continue

        bin_dir = OUT_DIR / bin_slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        gdf = gpd.GeoDataFrame(
            rows,
            geometry=[Point(r["_x"], r["_y"]) for r in rows],
            crs="EPSG:4326",
        ).drop(columns=["_x", "_y"])

        out_all = bin_dir / f"de_landkreis_pies_{bin_slug}.geojson"
        gdf.to_file(out_all, driver="GeoJSON")
        print(f"[OK] Wrote {out_all.name} ({len(gdf)} rows)")

        for state_slug, sub in gdf.groupby("state_slug"):
            state_bin_dir = OUT_DIR / state_slug / bin_slug
            state_bin_dir.mkdir(parents=True, exist_ok=True)

            out_state = state_bin_dir / f"de_{state_slug}_landkreis_pies_{bin_slug}.geojson"
            sub.to_file(out_state, driver="GeoJSON")

            st_info = state_stats.get(state_slug, {})
            vmin = float(st_info.get("min_total_kw", 0.0) or 0.0)
            vmax = float(st_info.get("max_total_kw", 0.0) or 0.0)

            meta = {
                "state_slug": state_slug,
                "year_bin": bin_label,
                "year_bin_slug": bin_slug,
                "min_total_kw": vmin,
                "max_total_kw": vmax,
                "priority_fields": list(PRIORITY.values()),
                "others_field": OTHERS,
                "name_field": "kreis_key",
                "is_cumulative": True,
            }
            (state_bin_dir / f"landkreis_pie_style_meta_{bin_slug}.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

    # ----------------------------------------------------------
    # STEP D) Germany ROW chart + guides + frame
    #       + STATE column chart + frame
    # ----------------------------------------------------------
    STACK_ORDER = ["hydro_kw", "biogas_kw", "pv_kw", "wind_kw", "others_kw", "battery_kw"]

    # D1) PERIOD sums (Germany-wide)
    per_bin_energy_period = {}
    for slug, _label, *_ in YEAR_BINS:
        sums = {f: 0.0 for f in PART_FIELDS}
        found_any = False

        for (_st, _kreis, bin_slug), parts in period_by_kreis_bin.items():
            if bin_slug != slug:
                continue
            found_any = True
            for f in PART_FIELDS:
                sums[f] += float(parts.get(f, 0.0) or 0.0)

        if found_any:
            per_bin_energy_period[slug] = sums

    # D2) CUMULATIVE across bins (Germany-wide)
    yearly_totals = []
    bin_energy_totals = {}
    cumulative = {f: 0.0 for f in PART_FIELDS}

    for slug, _label, *_ in YEAR_BINS:
        if slug not in per_bin_energy_period:
            continue

        e_sums = per_bin_energy_period[slug]
        for f in PART_FIELDS:
            cumulative[f] += float(e_sums.get(f, 0.0) or 0.0)

        total_kw = float(sum(cumulative.values()))
        if total_kw <= 0:
            continue

        yearly_totals.append(
            {
                "year_bin_slug": slug,
                "year_bin_label": BIN_LABEL[slug],
                "total_kw": total_kw,
            }
        )
        bin_energy_totals[slug] = dict(cumulative)

    (OUT_DIR / "de_yearly_totals.json").write_text(
        json.dumps(yearly_totals, indent=2), encoding="utf-8"
    )

    # D3) ROW CHART geometry (cumulative) + guides + frame
    CHART_BASE_LON = -2.2
    CHART_BASE_LAT = 47.5
    MAX_BAR_WIDTH = 6.8
    BAR_HEIGHT_DEG = 0.15
    BAR_GAP_DEG = 0.05

    YEAR_LABEL_LON = CHART_BASE_LON - 0.8
    VALUE_LABEL_LON = 5.3
    GUIDE_END_LON = VALUE_LABEL_LON - 0.35

    chart_features = []
    guide_features = []

    vals = [info["total_kw"] for info in yearly_totals if float(info["total_kw"]) > 0.0]
    if vals:
        max_total = float(max(vals))
        yearly_totals_rev = list(reversed(yearly_totals))

        for idx, info in enumerate(yearly_totals_rev):
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            total = float(info["total_kw"])
            if total <= 0:
                continue

            energy_sums = bin_energy_totals.get(slug, None)
            if energy_sums is None:
                continue

            y0 = CHART_BASE_LAT + idx * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
            y1 = y0 + BAR_HEIGHT_DEG
            y_center = 0.5 * (y0 + y1)

            bar_ratio = total / max_total if max_total > 0 else 0.0
            bar_ratio = max(0.0, min(1.0, bar_ratio))
            bar_width_total = bar_ratio * MAX_BAR_WIDTH

            x_base = CHART_BASE_LON

            for key in STACK_ORDER:
                seg_val = float(energy_sums.get(key, 0.0) or 0.0)
                if seg_val <= 0:
                    continue

                seg_ratio = seg_val / total if total > 0 else 0.0
                seg_ratio = max(0.0, min(1.0, seg_ratio))
                seg_width = seg_ratio * bar_width_total
                if seg_width <= 0:
                    continue

                x1 = x_base + seg_width
                poly = Polygon(
                    [
                        (x_base, y0),
                        (x1, y0),
                        (x1, y1),
                        (x_base, y1),
                        (x_base, y0),
                    ]
                )

                chart_features.append(
                    {
                        "year_bin_slug": slug,
                        "year_bin_label": label,
                        "energy_type": key,
                        "energy_kw": seg_val,
                        "total_kw": total,
                        "label_anchor": 0,
                        "value_anchor": 0,
                        "geometry": poly,
                    }
                )
                x_base = x1

            start_x = x_base + 0.05
            end_x = GUIDE_END_LON
            if start_x < end_x:
                guide_features.append(
                    {
                        "year_bin_slug": slug,
                        "year_bin_label": label,
                        "kind": "guide",
                        "geometry": LineString([(start_x, y_center), (end_x, y_center)]),
                    }
                )

            chart_features.append(
                {
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": "others_kw",
                    "energy_kw": 0.0,
                    "total_kw": total,
                    "label_anchor": 1,
                    "value_anchor": 0,
                    "geometry": Point(YEAR_LABEL_LON, y_center),
                }
            )

            chart_features.append(
                {
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": "others_kw",
                    "energy_kw": 0.0,
                    "total_kw": total,
                    "label_anchor": 0,
                    "value_anchor": 1,
                    "geometry": Point(VALUE_LABEL_LON, y_center),
                }
            )

        title_y = CHART_BASE_LAT + (len(yearly_totals_rev) + 1) * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
        title_x = CHART_BASE_LON + MAX_BAR_WIDTH / 2.0

        chart_features.append(
            {
                "year_bin_slug": "title",
                "year_bin_label": UNIFIED_TITLE_TEXT["row_chart"],
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": 0.0,
                "label_anchor": 0,
                "value_anchor": 0,
                "geometry": Point(title_x, title_y),
            }
        )

        chart_features.append(
            {
                "year_bin_slug": "unit",
                "year_bin_label": "GW",
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": 0.0,
                "label_anchor": 0,
                "value_anchor": 0,
                "geometry": Point(VALUE_LABEL_LON, title_y),
            }
        )

        HEADING_X_MAIN = 9.7
        HEADING_Y_MAIN = 55.1
        HEADING_X_SUB = 13.0
        HEADING_Y_SUB = 54.9

        for info in yearly_totals:
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            cum_total_kw = float(info["total_kw"])

            chart_features.append(
                {
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": "heading_main",
                    "energy_kw": 0.0,
                    "total_kw": cum_total_kw,
                    "label_anchor": 0,
                    "value_anchor": 1,
                    "geometry": Point(HEADING_X_MAIN, HEADING_Y_MAIN),
                }
            )

            chart_features.append(
                {
                    "year_bin_slug": slug,
                    "year_bin_label": "Installed Power (Period): n/a",
                    "energy_type": "heading_sub",
                    "energy_kw": 0.0,
                    "total_kw": cum_total_kw,
                    "label_anchor": 0,
                    "value_anchor": 1,
                    "geometry": Point(HEADING_X_SUB, HEADING_Y_SUB),
                }
            )

        chart_gdf = gpd.GeoDataFrame(chart_features, geometry="geometry", crs="EPSG:4326")
        chart_gdf.to_file(OUT_DIR / "de_yearly_totals_chart.geojson", driver="GeoJSON")

        if guide_features:
            guides_gdf = gpd.GeoDataFrame(guide_features, geometry="geometry", crs="EPSG:4326")
            guides_gdf.to_file(OUT_DIR / "de_yearly_totals_chart_guides.geojson", driver="GeoJSON")

        frame_left = YEAR_LABEL_LON - 0.2
        frame_right = VALUE_LABEL_LON + 0.8
        frame_bottom = CHART_BASE_LAT - 0.25
        frame_top = CHART_BASE_LAT + (len(yearly_totals_rev)) * (BAR_HEIGHT_DEG + BAR_GAP_DEG) + 0.35

        frame_poly = Polygon(
            [
                (frame_left, frame_bottom),
                (frame_right, frame_bottom),
                (frame_right, frame_top),
                (frame_left, frame_top),
                (frame_left, frame_bottom),
            ]
        )

        frame_gdf = gpd.GeoDataFrame(
            [{"kind": "frame", "geometry": frame_poly}],
            geometry="geometry",
            crs="EPSG:4326",
        )
        frame_gdf.to_file(OUT_DIR / "de_yearly_totals_chart_frame.geojson", driver="GeoJSON")

    # D4) STATE STACKED COLUMN CHART (16 columns, cumulative totals per bin) + frame
    STATE_COL_X0 = 16.2
    STATE_COL_BASE_Y = 47.6
    STATE_COL_MAX_H = 6.2
    STATE_COL_W = 0.26
    STATE_COL_GAP = 0.10

    STATE_COL_LABEL_Y = STATE_COL_BASE_Y - 0.30
    STATE_COL_VALUE_Y_PAD = 0.08

    STATE_COL_TITLE_X = 18.7
    STATE_COL_TITLE_Y = 54.2

    state_bin_rows = {}
    for bin_slug, rows in by_bin.items():
        for r in rows:
            st = r.get("state_slug", "")
            if not st:
                continue
            state_bin_rows.setdefault((st, bin_slug), []).append(r)

    max_state_total = 0.0
    for (_st, _bin_slug), rows in state_bin_rows.items():
        sums = {f: 0.0 for f in PART_FIELDS}
        for r in rows:
            for f in PART_FIELDS:
                sums[f] += float(r.get(f, 0.0) or 0.0)
        max_state_total = max(max_state_total, float(sum(sums.values())))

    state_bar_features = []
    state_lbl_features = []

    if max_state_total > 0.0:
        for slug, bin_label, *_ in YEAR_BINS:
            per_state_totals = []
            for st in STATE_SLUG_TO_NUMBER.keys():
                rows = state_bin_rows.get((st, slug), [])
                sums = {f: 0.0 for f in PART_FIELDS}
                for r in rows:
                    for f in PART_FIELDS:
                        sums[f] += float(r.get(f, 0.0) or 0.0)
                total_kw = float(sum(sums.values()))
                per_state_totals.append((st, sums, total_kw))

            for st, sums, total_kw in per_state_totals:
                sn_int = int(STATE_SLUG_TO_NUMBER.get(st, 0) or 0)
                if sn_int <= 0:
                    continue

                state_abbrev = STATE_SLUG_TO_ABBREV.get(st, "")

                ratio_total = max(0.0, min(1.0, total_kw / max_state_total))
                col_h = ratio_total * STATE_COL_MAX_H

                x_left = STATE_COL_X0 + (sn_int - 1) * (STATE_COL_W + STATE_COL_GAP)
                x_right = x_left + STATE_COL_W
                x_center = 0.5 * (x_left + x_right)

                y_base = STATE_COL_BASE_Y
                y_top = y_base + col_h

                y_cursor = y_base
                for key in STACK_ORDER:
                    part_kw = float(sums.get(key, 0.0) or 0.0)
                    if total_kw <= 0 or part_kw <= 0:
                        continue

                    seg_ratio = max(0.0, min(1.0, part_kw / total_kw))
                    seg_h = seg_ratio * col_h
                    if seg_h <= 0:
                        continue

                    poly = Polygon(
                        [
                            (x_left, y_cursor),
                            (x_right, y_cursor),
                            (x_right, y_cursor + seg_h),
                            (x_left, y_cursor + seg_h),
                            (x_left, y_cursor),
                        ]
                    )

                    state_bar_features.append(
                        {
                            "year_bin_slug": slug,
                            "year_bin_label": bin_label,
                            "state_number": sn_int,
                            "state_abbrev": state_abbrev,
                            "energy_type": key,
                            "total_kw": total_kw,
                            "geometry": poly,
                        }
                    )
                    y_cursor += seg_h

                state_lbl_features.append(
                    {
                        "year_bin_slug": slug,
                        "year_bin_label": bin_label,
                        "state_number": sn_int,
                        "state_abbrev": state_abbrev,
                        "kind": "state_label",
                        "total_kw": total_kw,
                        "geometry": Point(x_center, STATE_COL_LABEL_Y),
                    }
                )

                state_lbl_features.append(
                    {
                        "year_bin_slug": slug,
                        "year_bin_label": bin_label,
                        "state_number": sn_int,
                        "state_abbrev": state_abbrev,
                        "kind": "value_label",
                        "total_kw": total_kw,
                        "geometry": Point(x_center, y_top + STATE_COL_VALUE_Y_PAD),
                    }
                )

        state_lbl_features.append(
            {
                "year_bin_slug": "state_title",
                "year_bin_label": UNIFIED_TITLE_TEXT["column_chart"],
                "state_number": 0,
                "state_abbrev": "",
                "kind": "title",
                "total_kw": 0.0,
                "geometry": Point(STATE_COL_TITLE_X, STATE_COL_TITLE_Y),
            }
        )

        bars_gdf = gpd.GeoDataFrame(state_bar_features, geometry="geometry", crs="EPSG:4326")
        labels_gdf = gpd.GeoDataFrame(state_lbl_features, geometry="geometry", crs="EPSG:4326")

        bars_gdf.to_file(OUT_DIR / "de_state_totals_columnChart_bars.geojson", driver="GeoJSON")
        labels_gdf.to_file(OUT_DIR / "de_state_totals_columnChart_labels.geojson", driver="GeoJSON")

        col_left = STATE_COL_X0 - 0.2
        col_right = STATE_COL_X0 + 15 * (STATE_COL_W + STATE_COL_GAP) + STATE_COL_W + 0.2
        col_bottom = STATE_COL_LABEL_Y - 0.25
        col_top = STATE_COL_BASE_Y + STATE_COL_MAX_H + 0.6

        col_frame = Polygon(
            [
                (col_left, col_bottom),
                (col_right, col_bottom),
                (col_right, col_top),
                (col_left, col_top),
                (col_left, col_bottom),
            ]
        )

        col_frame_gdf = gpd.GeoDataFrame(
            [{"kind": "frame", "geometry": col_frame}],
            geometry="geometry",
            crs="EPSG:4326",
        )
        col_frame_gdf.to_file(OUT_DIR / "de_state_totals_columnChart_frame.geojson", driver="GeoJSON")

    # ---------------- ENERGY LEGEND + PIE SIZE LEGEND + FRAMES ----------------
    if all_cumulative_totals:
        global_min_kw = float(min(all_cumulative_totals))
        global_max_kw = float(max(all_cumulative_totals))

        legend_rows = [
            ("pv_kw", "Photovoltaics"),
            ("wind_kw", "Onshore Wind Energy"),
            ("hydro_kw", "Hydropower"),
            ("biogas_kw", "Biogas"),
            ("battery_kw", "Battery"),
            ("others_kw", "Others"),
        ]

        legend_feats = []
        for idx, (etype, text) in enumerate(legend_rows):
            y = LEG_TOP_LAT + idx * LEG_ROW_STEP
            legend_feats.append(
                {
                    "energy_type": etype,
                    "legend_label": text,
                    "geometry": Point(LEG_BASE_LON, y),
                }
            )

        legend_feats.append(
            {
                "energy_type": "legend_title",
                "legend_label": UNIFIED_TITLE_TEXT["energy_legend"],
                "geometry": Point(ENERGY_FRAME_XMIN + 0.20, LEGEND_TITLE_LAT),
            }
        )

        legend_gdf = gpd.GeoDataFrame(legend_feats, geometry="geometry", crs="EPSG:4326")
        legend_gdf.to_file(OUT_DIR / "de_energy_legend_points.geojson", driver="GeoJSON")

        write_pie_size_legend(global_min_kw, global_max_kw)
        write_legend_frames()


if __name__ == "__main__":
    main()