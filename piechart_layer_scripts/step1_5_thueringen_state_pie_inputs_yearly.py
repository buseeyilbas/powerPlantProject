# Filename: step1_5_thueringen_state_pie_inputs_yearly.py
# Purpose : Build THUERINGEN state pie INPUT POINTS per 2-year bin (1 state per bin).
#           - Centers are fixed using BASE_FIXED (repulsed polygon pies) -> fallback point pies.
#           - Writes per-bin meta AND global meta (all-years min/max) for sizing.
#           - Creates:
#               * Thuringen-wide cumulative row chart (stacked by energy type) + headings.
#               * Energy type legend points (fixed positions).
#
# IMPORTANT (power consistency):
# - This script applies a CANONICAL FILTER identical in spirit to step2_5:
#   Keep only points that can be assigned to a Thüringen Landkreis (attr or polygon fallback)
#   AND whose kreis_slug exists in the step0 centers file.
# - This makes step1_5 totals consistent with summing landkreis totals from step2_5.

from pathlib import Path
import os
import re
import json
import unicodedata

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

# ---------- PATHS ----------
INPUT_ROOT = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_4_checks\thueringen")
OUT_BASE   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_state_pies_yearly")
BASE_FIXED = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_state_pies")
GLOBAL_META = OUT_BASE / "_GLOBAL_style_meta.json"

# step0 output (Thüringen Landkreis centers)
CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_landkreis_centers\thueringen_landkreis_centers.geojson"
)

# GADM L2 polygons (Landkreise)
GADM_L2_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
)

# ---------- YEAR BINS (2-year ranges) ----------
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
BIN_LABEL = {slug: label for (slug, label, *_ ) in YEAR_BINS}
INCLUDE_UNKNOWN = False

# ---------- ENERGY MAP / FIELDS ----------
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

PRIORITY_FIELDNAMES = {
    "Photovoltaik":                    "pv_kw",
    "Windenergie Onshore":             "wind_kw",
    "Wasserkraft":                     "hydro_kw",
    "Stromspeicher (Battery Storage)": "battery_kw",
    "Biogas":                          "biogas_kw",
}
OTHERS_FIELD = "others_kw"

# ---------- STATE CONSTANTS ----------
STATE_NAME = "Thüringen"
STATE_SLUG = "thueringen"
STATE_NUMBER = 16  # keep consistent with your nationwide numbering

# ---------- HELPERS ----------
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


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


def normalize_energy(val, filename_hint=""):
    # Try explicit fields first
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]
        sn = normalize_text(s)
        if "solar" in sn or "photovoltaik" in sn or sn == "pv":
            return "Photovoltaik"
        if "wind" in sn:
            return "Windenergie Onshore"
        if "wasser" in sn or "hydro" in sn:
            return "Wasserkraft"
        if "stromspeicher" in sn or "speicher" in sn or "battery" in sn:
            return "Stromspeicher (Battery Storage)"
        if "biogas" in sn or sn == "gas":
            return "Biogas"

    # Fallback: infer from filename
    fn = normalize_text(filename_hint)
    if "solar" in fn or "photovoltaik" in fn or "pv" in fn:
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


DATE_CANDIDATES = [
    "Inbetriebnahmedatum", "inbetriebnahmedatum", "Inbetriebnahme",
    "commissioning_date", "CommissioningDate",
    "Betriebsbeginn", "Baujahr", "year", "Year", "YEAR",
]


def extract_year(row, filename_hint=""):
    for col in DATE_CANDIDATES:
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

    m = re.search(r"(19|20)\d{2}", filename_hint)
    if m:
        y = int(m.group(0))
        if 1900 <= y <= 2100:
            return y
    return None


def year_to_bin(y):
    if y is None:
        return ("unknown", "Unknown / NA")
    for slug, label, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return (slug, label)
    return ("unknown", "Unknown / NA")


def scan_geojsons(folder: Path):
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


def load_thueringen_centers():
    """
    Load Thüringen Landkreis centers from step0 output.
    Returns: dict[landkreis_slug] -> (lon, lat)
    """
    if not CENTERS_PATH.exists():
        raise RuntimeError(f"CENTERS_PATH not found: {CENTERS_PATH}")

    g = gpd.read_file(CENTERS_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    if "landkreis_slug" not in g.columns:
        raise RuntimeError("Centers file missing column: landkreis_slug")

    centers = {}
    for _, r in g.iterrows():
        slug = str(r.get("landkreis_slug", "")).strip()
        geom = r.geometry
        if not slug or geom is None or geom.is_empty or geom.geom_type != "Point":
            continue
        centers[slug] = (float(geom.x), float(geom.y))

    return centers


def load_thueringen_center():
    """
    Returns (lon, lat) for Thüringen state pie using:
      1) BASE_FIXED/thueringen_state_pie.geojson    (repulsed polygon pies)
      2) BASE_FIXED/thueringen_state_pies.geojson   (point pies)
    Fallback: None
    """
    poly_path = BASE_FIXED / "thueringen_state_pie.geojson"
    if poly_path.exists():
        g = gpd.read_file(poly_path)
        if g.crs is None:
            g = g.set_crs("EPSG:4326", allow_override=True)

        pts = []
        for _, r in g.iterrows():
            geom = r.geometry
            if geom is not None and geom.geom_type == "Polygon":
                x0, y0 = list(geom.exterior.coords)[0]
                pts.append((float(x0), float(y0)))
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (sum(xs) / len(xs), sum(ys) / len(ys))

    pts_path = BASE_FIXED / "thueringen_state_pies.geojson"
    if pts_path.exists():
        g = gpd.read_file(pts_path)
        if g.crs is None:
            g = g.set_crs("EPSG:4326", allow_override=True)
        if not g.empty:
            geom = g.geometry.iloc[0]
            return (float(geom.x), float(geom.y))

    return None


def load_thueringen_landkreis_polygons():
    """
    Load Thüringen Landkreis polygons from GADM L2.
    Returns GeoDataFrame with columns: landkreis_name, landkreis_slug, geometry
    """
    if not GADM_L2_PATH.exists():
        raise RuntimeError(f"GADM L2 not found: {GADM_L2_PATH}")

    g = gpd.read_file(GADM_L2_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    if "NAME_1" not in g.columns or "NAME_2" not in g.columns:
        raise RuntimeError("GADM L2 is missing NAME_1/NAME_2 columns.")

    g = g[g["NAME_1"].astype(str).str.strip().str.lower().isin(["thüringen", "thueringen"])].copy()
    if g.empty:
        raise RuntimeError("No Thüringen polygons found in GADM L2.")

    g["landkreis_name"] = g["NAME_2"].astype(str)
    g["landkreis_slug"] = g["landkreis_name"].apply(normalize_text)

    return g[["landkreis_name", "landkreis_slug", "geometry"]].copy()


def pick_landkreis_from_row(row: pd.Series):
    """
    Try to read Landkreis from known column candidates in the plant points.
    """
    candidates = ("Landkreis", "landkreis", "NAME_2", "kreis_name", "landkreis_name", "LandkreisName")
    for c in candidates:
        if c in row and pd.notna(row[c]):
            return str(row[c])
    return None


def assign_kreis_slug_with_fallback(pts: gpd.GeoDataFrame, lk_poly: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign kreis_slug for each point:
      1) from row attribute (Landkreis / NAME_2 / ...)
      2) polygon fallback (GADM L2 Thüringen) using sjoin
    """
    pts = pts.copy()

    def attr_slug(r):
        v = pick_landkreis_from_row(r)
        return normalize_text(v) if v else ""

    pts["kreis_slug"] = pts.apply(attr_slug, axis=1).fillna("").astype(str)

    missing = pts["kreis_slug"].eq("") | pts["kreis_slug"].isna()
    if int(missing.sum()) == 0:
        return pts

    missing_pts = pts[missing].copy()
    missing_pts = gpd.GeoDataFrame(missing_pts, geometry="geometry", crs="EPSG:4326")

    # within (strict)
    joined = gpd.sjoin(missing_pts, lk_poly, how="left", predicate="within")

    # intersects fallback (border cases)
    still_missing = joined["landkreis_slug"].isna()
    if int(still_missing.sum()) > 0:
        joined2 = gpd.sjoin(
            joined[still_missing].drop(columns=["landkreis_slug", "index_right"], errors="ignore"),
            lk_poly,
            how="left",
            predicate="intersects",
        )
        joined.loc[still_missing, "landkreis_slug"] = joined2["landkreis_slug"].values

    fallback = joined["landkreis_slug"].fillna("").astype(str).to_dict()
    pts.loc[missing, "kreis_slug"] = pts.loc[missing].index.map(lambda idx: fallback.get(idx, ""))

    return pts


def main():
    OUT_BASE.mkdir(parents=True, exist_ok=True)

    baseline_center = load_thueringen_center()
    if baseline_center:
        print(f"[INFO] Loaded Thüringen fixed center from BASE_FIXED: {baseline_center}")
    else:
        print("[WARN] No fixed Thüringen center found in BASE_FIXED. Falling back to per-bin means.")

    frames = []

    has_subdirs = any(p.is_dir() for p in INPUT_ROOT.iterdir())
    if has_subdirs:
        geojson_paths = []
        for d in INPUT_ROOT.iterdir():
            if d.is_dir():
                geojson_paths.extend(list(scan_geojsons(d)))
    else:
        geojson_paths = list(scan_geojsons(INPUT_ROOT))

    if not geojson_paths:
        raise RuntimeError(f"No GeoJSON files found under {INPUT_ROOT}")

    # Columns we want to keep if present (for Landkreis attribute-based assignment)
    LK_CAND_COLS = ["Landkreis", "landkreis", "NAME_2", "kreis_name", "landkreis_name", "LandkreisName"]

    # ---- Parse all Thüringen GeoJSONs -> one big table ----
    for p in geojson_paths:
        try:
            g = gpd.read_file(p)
            if g.empty or "geometry" not in g.columns:
                continue

            g = g[~g.geometry.is_empty & g.geometry.notnull()].copy()
            g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])]
            if g.empty:
                continue

            # Explode MultiPoint
            try:
                if "MultiPoint" in list(g.geometry.geom_type.unique()):
                    g = g.explode(index_parts=False).reset_index(drop=True)
            except TypeError:
                g = g.explode().reset_index(drop=True)

            # Energy normalization
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            # Power column detection
            power_col = None
            for c in ["power_kw", "Nettonennleistung", "Bruttoleistung", "Nennleistung",
                      "Leistung", "installed_power_kw", "kw", "power"]:
                if c in g.columns:
                    power_col = c
                    break
            if power_col is None:
                print(f"[WARN] No power column in {p.name}; skipped.")
                continue

            g["_power"] = g[power_col].apply(parse_number)
            g = g[(pd.notna(g["_power"])) & (g["_power"] > 0)]
            if g.empty:
                continue

            # Year / bin
            years = [extract_year(r, p.name) for _, r in g.iterrows()]
            g["_year"] = years
            bins = [year_to_bin(y) for y in g["_year"]]
            g["year_bin_slug"] = [b[0] for b in bins]
            g["year_bin_label"] = [b[1] for b in bins]

            g["state_name"] = STATE_NAME
            g["state_slug"] = STATE_SLUG

            keep_cols = [
                "state_name", "state_slug", "energy_norm", "_power",
                "_year", "year_bin_slug", "year_bin_label", "geometry",
            ]
            keep_cols += [c for c in LK_CAND_COLS if c in g.columns]

            frames.append(g[keep_cols].copy())

        except Exception as e:
            print(f"[WARN] Skipped {p}: {e}")

    if not frames:
        raise RuntimeError("No usable features after parsing.")

    df = pd.concat(frames, ignore_index=True)
    if not INCLUDE_UNKNOWN:
        df = df[df["year_bin_slug"] != "unknown"]

    # ---- CANONICAL FILTER (match step2_5) ----
    centers = load_thueringen_centers()
    lk_poly = load_thueringen_landkreis_polygons()

    pts = gpd.GeoDataFrame(df.copy(), geometry="geometry", crs="EPSG:4326")
    pts = assign_kreis_slug_with_fallback(pts, lk_poly)

    before_n = len(pts)
    before_sum = float(pts["_power"].fillna(0).sum())

    pts = pts[pts["kreis_slug"].isin(set(centers.keys()))].copy()

    after_n = len(pts)
    after_sum = float(pts["_power"].fillna(0).sum())

    print(f"[CANONICAL 1_5] kept rows: {after_n}/{before_n} (dropped {before_n - after_n})")
    print(f"[CANONICAL 1_5] kept power: {after_sum:,.2f} kW (dropped {before_sum - after_sum:,.2f} kW)")

    df = pd.DataFrame(pts)

    print("[CHECK] year_bin_slug counts:")
    print(df["year_bin_slug"].value_counts(dropna=False))

    missing_year = df["_year"].isna().sum()
    print(f"[CHECK] rows with _year=None: {missing_year}")

    # ---- Aggregate per (year-bin) and assign center ----
    per_bin_rows = {}
    global_totals = []

    for yslug, grp in df.groupby("year_bin_slug", dropna=False):
        label = grp["year_bin_label"].iloc[0]

        totals = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                totals[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                others += pkw

        totals[OTHERS_FIELD] = others
        totals["total_kw"] = sum(totals.values())

        totals["state_name"] = STATE_NAME
        totals["state_slug"] = STATE_SLUG
        totals["year_bin_slug"] = yslug
        totals["year_bin_label"] = label
        totals["state_number"] = STATE_NUMBER

        # Pick center (state pie center)
        if baseline_center is not None:
            ax, ay = baseline_center
        else:
            xs = grp.geometry.x.astype(float)
            ys = grp.geometry.y.astype(float)
            ax, ay = float(xs.mean()), float(ys.mean())

        totals["_x"], totals["_y"] = ax, ay

        per_bin_rows.setdefault(yslug, []).append(totals)
        global_totals.append(totals["total_kw"])

    # ---- Write per-bin point outputs ----
    for slug, label, *_ in YEAR_BINS:
        rows = per_bin_rows.get(slug, [])
        if not rows:
            print(f"[SKIP] No rows for bin {slug}")
            continue

        bin_dir = OUT_BASE / slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        gdf = gpd.GeoDataFrame(
            rows,
            geometry=[Point(t["_x"], t["_y"]) for t in rows],
            crs="EPSG:4326",
        ).drop(columns=["_x", "_y"])

        out_pts = bin_dir / f"thueringen_state_pies_{slug}.geojson"
        gdf.to_file(out_pts, driver="GeoJSON")

        vmin = float(gdf["total_kw"].min())
        vmax = float(gdf["total_kw"].max())

        meta = {
            "min_total_kw": vmin,
            "max_total_kw": vmax,
            "priority_fields": list(PRIORITY_FIELDNAMES.values()),
            "others_field": OTHERS_FIELD,
            "name_field": "state_name",
            "year_bin": BIN_LABEL[slug],
        }
        (bin_dir / f"thueringen_state_pie_style_meta_{slug}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"[BIN SCALE] {slug}: vmin={vmin:.2f}, vmax={vmax:.2f}, points={len(gdf)} -> {out_pts.name}")

    # ---- Thüringen totals per year-bin (cumulative) + stacked row chart ----
    PART_FIELDS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]

    per_bin_energy = {}
    for slug, label, *_ in YEAR_BINS:
        rows = per_bin_rows.get(slug, [])
        if not rows:
            continue
        energy_sums = {f: 0.0 for f in PART_FIELDS}
        for r in rows:
            for f in PART_FIELDS:
                energy_sums[f] += float(r.get(f, 0.0) or 0.0)
        per_bin_energy[slug] = energy_sums

    yearly_totals = []
    bin_energy_totals = {}
    cumulative = {f: 0.0 for f in PART_FIELDS}

    for slug, label, *_ in YEAR_BINS:
        if slug not in per_bin_energy:
            continue
        e_sums = per_bin_energy[slug]
        for f in PART_FIELDS:
            cumulative[f] += float(e_sums.get(f, 0.0) or 0.0)

        total_kw = float(sum(cumulative.values()))
        if total_kw <= 0:
            continue

        yearly_totals.append({
            "year_bin_slug": slug,
            "year_bin_label": BIN_LABEL[slug],
            "total_kw": total_kw,
        })
        bin_energy_totals[slug] = dict(cumulative)

    if yearly_totals:
        totals_json = OUT_BASE / "thueringen_yearly_totals.json"
        totals_json.write_text(json.dumps(yearly_totals, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] Wrote yearly totals JSON (cumulative) -> {totals_json.name}")

        # ---- ROW CHART (horizontal cumulative chart) ----
        CHART_BASE_LON = 8.5
        CHART_BASE_LAT = 50.25
        MAX_BAR_WIDTH  = 1.1
        BAR_HEIGHT_DEG = 0.035
        BAR_GAP_DEG    = 0.012

        YEAR_LABEL_LON  = CHART_BASE_LON - 0.12
        VALUE_LABEL_LON = 9.75

        vals = [info["total_kw"] for info in yearly_totals if info["total_kw"] > 0]
        max_total = float(max(vals)) if vals else 0.0

        chart_features = []
        STACK_ORDER = ["hydro_kw", "biogas_kw", "pv_kw", "wind_kw", "others_kw", "battery_kw"]

        for idx, info in enumerate(reversed(yearly_totals)):
            slug  = info["year_bin_slug"]
            label = info["year_bin_label"]
            total = float(info["total_kw"])
            if total <= 0:
                continue

            energy_sums = bin_energy_totals[slug]

            y0 = CHART_BASE_LAT + idx * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
            y1 = y0 + BAR_HEIGHT_DEG
            y_center = 0.5 * (y0 + y1)
            x_base = CHART_BASE_LON

            bar_ratio = total / max_total if max_total > 0 else 0.0
            bar_ratio = max(0.0, min(1.0, bar_ratio))
            bar_width_total = bar_ratio * MAX_BAR_WIDTH

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
                poly = Polygon([(x_base, y0), (x1, y0), (x1, y1), (x_base, y1), (x_base, y0)])

                chart_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": key,
                    "energy_kw": seg_val,
                    "total_kw": total,
                    "label_anchor": 0,
                    "value_anchor": 0,
                    "geometry": poly
                })
                x_base = x1

            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 1,
                "value_anchor": 0,
                "geometry": Point(YEAR_LABEL_LON, y_center)
            })

            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(VALUE_LABEL_LON, y_center)
            })

        title_point = Point(
            CHART_BASE_LON + MAX_BAR_WIDTH / 2.0,
            CHART_BASE_LAT + (len(yearly_totals) + 1) * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
        )
        chart_features.append({
            "year_bin_slug": "title",
            "year_bin_label": "Thüringen - Cumulative Installed Power (MW)",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": title_point
        })

        HEADING_X_MAIN = 10.8
        HEADING_Y_MAIN = 51.7
        HEADING_X_SUB  = 11.4
        HEADING_Y_SUB  = 51.6

        heading_features = []
        for info in yearly_totals:
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            cum_total_kw = float(info["total_kw"])
            cum_total_mw = cum_total_kw / 1000.0

            heading_features.append({
                "year_bin_slug": slug,
                "year_bin_label": f"{label}",
                "energy_type": "heading_main",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_MAIN, HEADING_Y_MAIN),
            })
            heading_features.append({
                "year_bin_slug": slug,
                "year_bin_label": f"Cumulative Installed Power: {cum_total_mw:,.2f} MW",
                "energy_type": "heading_sub",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_SUB, HEADING_Y_SUB),
            })

        chart_features.extend(heading_features)

        chart_gdf = gpd.GeoDataFrame(chart_features, geometry="geometry", crs="EPSG:4326")
        chart_path = OUT_BASE / "thueringen_yearly_totals_chart.geojson"
        chart_gdf.to_file(chart_path, driver="GeoJSON")
        print(f"[INFO] Wrote Thüringen cumulative yearly total ROW chart -> {chart_path.name} ({len(chart_gdf)} features)")

    # ---- GLOBAL meta for all-years sizing ----
    if global_totals:
        gmin = float(min(global_totals))
        gmax = float(max(global_totals))
        GLOBAL_META.write_text(json.dumps({"min_total_kw": gmin, "max_total_kw": gmax}, indent=2), encoding="utf-8")
        print(f"[GLOBAL SCALE] min={gmin:.2f}, max={gmax:.2f} -> {GLOBAL_META.name}")

        # ---- ENERGY TYPE LEGEND (fixed positions) ----
        LEG_BASE_LON   = 8.5
        LEG_TOP_LAT    = 51.7
        LEG_ROW_STEP   = -0.05

        legend_rows = [
            ("pv_kw",      "Photovoltaics"),
            ("wind_kw",    "Onshore Wind Energy"),
            ("hydro_kw",   "Hydropower"),
            ("biogas_kw",  "Biogas"),
            ("battery_kw", "Battery"),
            ("others_kw",  "Others"),
        ]

        legend_feats = []
        for idx, (etype, text) in enumerate(legend_rows):
            y = LEG_TOP_LAT + idx * LEG_ROW_STEP
            legend_feats.append({
                "energy_type":  etype,
                "legend_label": text,
                "geometry":     Point(LEG_BASE_LON, y),
            })

        legend_gdf = gpd.GeoDataFrame(legend_feats, geometry="geometry", crs="EPSG:4326")
        legend_path = OUT_BASE / "thueringen_energy_legend_points.geojson"
        legend_gdf.to_file(legend_path, driver="GeoJSON")
        print(f"[INFO] Wrote energy legend layer -> {legend_path.name}")

    print("[DONE] step1_5 complete.")


if __name__ == "__main__":
    main()
