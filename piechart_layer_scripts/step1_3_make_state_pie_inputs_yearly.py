
# Filename: step1_3_make_state_pie_inputs_yearly.py
# Purpose : Build STATE pie INPUT POINTS per 2-year bin (16 states per bin).
#           - Centers are fixed using step1_2 polygon pies → fallback step1_1 point pies.
#           - Writes per-bin meta AND global meta (all-years min/max) for sizing.
#           - Creates:
#               * HUD layer with state numbers (1–16) in 2 columns in Poland.
#               * Germany-wide stacked column chart (per 2-year bin, colored by energy type).
#
# UPDATE (CUMULATIVE STATE PIES):
#   - For each state, per-bin values are now CUMULATIVE over time:
#       bin_k_value = sum(period_value up to bin_k)
#   - Pie slices (shares) are therefore computed against cumulative totals:
#       share = (cumulative_part_kw / cumulative_total_kw)
#   - Radius scaling uses cumulative total_kw, so each state grows monotonically over bins.
#   - Germany-wide row chart keeps using PERIOD contributions for stacking,
#     then is made cumulative across bins (as before).

from pathlib import Path
import os
import re
import json
import unicodedata

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, LineString

# ---------- PATHS ----------
INPUT_ROOT = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_4_checks")
OUT_BASE   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly")
BASE_FIXED = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies")  # step1_1 & step1_2
GLOBAL_META = OUT_BASE / "_GLOBAL_style_meta.json"

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
BIN_INDEX = {slug: i for i, (slug, *_ ) in enumerate(YEAR_BINS)}
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

# ---------- STATE NAME NORMALIZATION ----------
STATE_SLUG_TO_OFFICIAL = {
    "baden-wuerttemberg": "Baden-Württemberg",
    "bayern": "Bayern",
    "berlin": "Berlin",
    "brandenburg": "Brandenburg",
    "bremen": "Bremen",
    "hamburg": "Hamburg",
    "hessen": "Hessen",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "niedersachsen": "Niedersachsen",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rheinland-pfalz": "Rheinland-Pfalz",
    "saarland": "Saarland",
    "sachsen": "Sachsen",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "schleswig-holstein": "Schleswig-Holstein",
    "thueringen": "Thüringen",
    "thüringen": "Thüringen",
    "thuringen": "Thüringen",
}

STATE_NAME_TO_NUMBER = {
    "Baden-Württemberg":      1,
    "Bayern":                 2,
    "Berlin":                 3,
    "Brandenburg":            4,
    "Bremen":                 5,
    "Hamburg":                6,
    "Hessen":                 7,
    "Mecklenburg-Vorpommern": 8,
    "Niedersachsen":          9,
    "Nordrhein-Westfalen":    10,
    "Rheinland-Pfalz":        11,
    "Saarland":               12,
    "Sachsen":                13,
    "Sachsen-Anhalt":         14,
    "Schleswig-Holstein":     15,
    "Thüringen":              16,
}

OFFICIAL_TO_SLUG = {}
for slug, official in STATE_SLUG_TO_OFFICIAL.items():
    OFFICIAL_TO_SLUG.setdefault(official, slug)

# ---------- HELPERS ----------
def normalize_text(s):
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


def load_state_centers():
    """
    Returns {state_name -> (lon, lat)} using:
      1) BASE_FIXED/de_state_pie.geojson   (step1_2 polygons)
      2) BASE_FIXED/de_state_pies.geojson  (step1_1 points)
    """
    centers = {}

    # 1) repulsed polygons
    poly_path = BASE_FIXED / "de_state_pie.geojson"
    if poly_path.exists():
        g = gpd.read_file(poly_path)
        if g.crs is None:
            g = g.set_crs("EPSG:4326", allow_override=True)
        tmp = {}
        for _, r in g.iterrows():
            nm = str(r.get("name", r.get("state_name", ""))).strip() or str(r.get("state", "")).strip()
            geom = r.geometry
            if geom is not None and geom.geom_type == "Polygon":
                x0, y0 = list(geom.exterior.coords)[0]
                if nm:
                    tmp.setdefault(nm, []).append((float(x0), float(y0)))
        for nm, pts in tmp.items():
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            centers[nm] = (sum(xs) / len(xs), sum(ys) / len(ys))
        if centers:
            return centers

    # 2) point centers
    pts_path = BASE_FIXED / "de_state_pies.geojson"
    if pts_path.exists():
        g = gpd.read_file(pts_path)
        if g.crs is None:
            g = g.set_crs("EPSG:4326", allow_override=True)
        name_field = "state_name" if "state_name" in g.columns else "name"
        for _, r in g.iterrows():
            nm = str(r.get(name_field, "")).strip()
            if nm:
                centers[nm] = (float(r.geometry.x), float(r.geometry.y))

    return centers


def empty_parts_dict():
    d = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
    d[OTHERS_FIELD] = 0.0
    return d


def add_parts_inplace(dst, src):
    for k, v in src.items():
        dst[k] = float(dst.get(k, 0.0) or 0.0) + float(v or 0.0)


# ---------- MAIN ----------
def main():
    OUT_BASE.mkdir(parents=True, exist_ok=True)

    baseline = load_state_centers()
    if not baseline:
        print("[WARN] No baseline centers found in step1_1/step1_2. Falling back to per-bin means.")

    frames = []
    state_dirs = [d for d in INPUT_ROOT.iterdir() if d.is_dir()]
    if not state_dirs:
        raise RuntimeError(f"No state folders under {INPUT_ROOT}")

    # ---- Parse all state GeoJSONs → one big table ----
    for st_dir in state_dirs:
        raw_name = st_dir.name
        slug_guess = normalize_text(raw_name)

        found_slug = None
        for slug in STATE_SLUG_TO_OFFICIAL.keys():
            if slug_guess == slug or slug_guess.endswith(slug):
                found_slug = slug
                break
        if found_slug is None:
            found_slug = slug_guess

        state_name = STATE_SLUG_TO_OFFICIAL.get(found_slug, raw_name)

        for p in scan_geojsons(st_dir):
            try:
                g = gpd.read_file(p)
                if g.empty or "geometry" not in g.columns:
                    continue

                g = g[~g.geometry.is_empty & g.geometry.notnull()].copy()
                g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])]
                if g.empty:
                    continue

                # explode MultiPoint
                try:
                    if "MultiPoint" in list(g.geometry.geom_type.unique()):
                        g = g.explode(index_parts=False).reset_index(drop=True)
                except TypeError:
                    g = g.explode().reset_index(drop=True)

                # energy normalization
                if "energy_source_label" in g.columns:
                    g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
                elif "Energietraeger" in g.columns:
                    g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
                else:
                    g["energy_norm"] = normalize_energy(None, p.name)

                # power column
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

                # year / bin
                years = [extract_year(r, p.name) for _, r in g.iterrows()]
                g["_year"] = years
                bins = [year_to_bin(y) for y in g["_year"]]
                g["year_bin_slug"] = [b[0] for b in bins]
                g["year_bin_label"] = [b[1] for b in bins]

                g["state_name"] = state_name
                g["state_slug"] = found_slug

                frames.append(
                    g[["state_name", "state_slug", "energy_norm", "_power",
                        "_year", "year_bin_slug", "year_bin_label", "geometry"]]
                )

            except Exception as e:
                print(f"[WARN] Skipped {p}: {e}")

    if not frames:
        raise RuntimeError("No usable features after parsing.")

    df = pd.concat(frames, ignore_index=True)
    if not INCLUDE_UNKNOWN:
        df = df[df["year_bin_slug"] != "unknown"]

    print("[CHECK] year_bin_slug counts:")
    print(df["year_bin_slug"].value_counts(dropna=False))

    missing_year = df["_year"].isna().sum()
    print(f"[CHECK] rows with _year=None: {missing_year}")

    # ----------------------------------------------------------
    #   STEP A) PERIOD aggregation per (state, bin)  (non-cum)
    # ----------------------------------------------------------
    # We keep this because Germany-wide stacked chart needs PERIOD contributions.
    period_by_state_bin = {}   # (state_name, bin_slug) -> parts dict
    center_by_state = {}       # state_name -> (x, y) fixed center + ids

    for (sname, yslug), grp in df.groupby(["state_name", "year_bin_slug"], dropna=False):
        parts = empty_parts_dict()

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                parts[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                parts[OTHERS_FIELD] += pkw

        period_by_state_bin[(sname, yslug)] = parts

        # Center assignment (fixed per state, not per bin)
        if sname not in center_by_state:
            if sname in baseline:
                ax, ay = baseline[sname]
            else:
                xs = grp.geometry.x.astype(float)
                ys = grp.geometry.y.astype(float)
                ax, ay = float(xs.mean()), float(ys.mean())

            num = STATE_NAME_TO_NUMBER.get(sname)
            state_num = int(num) if num is not None else None
            state_slug = grp["state_slug"].iloc[0]

            center_by_state[sname] = {
                "_x": ax,
                "_y": ay,
                "state_number": state_num,
                "state_slug": state_slug,
            }

    # ----------------------------------------------------------
    #   STEP B) Build CUMULATIVE per (state, bin)
    # ----------------------------------------------------------
    # For each state, walk bins in chronological order and accumulate parts.
    cumulative_by_bin = {}   # bin_slug -> list of per-state rows (cumulative)
    global_totals = []       # all cumulative total_kw for GLOBAL sizing meta

    # Determine all states we have
    all_states = sorted(center_by_state.keys(), key=lambda n: (STATE_NAME_TO_NUMBER.get(n, 999), n))

    for sname in all_states:
        running = empty_parts_dict()

        for bin_slug, bin_label, *_ in YEAR_BINS:
            period_parts = period_by_state_bin.get((sname, bin_slug), empty_parts_dict())
            add_parts_inplace(running, period_parts)

            total_kw = float(sum(running.values()))
            # If a state has no power at all up to this bin, you can keep it (0) or skip.
            # We keep it, but step1_4 will naturally produce no slices if total<=0.
            row = {
                "pv_kw": running["pv_kw"],
                "wind_kw": running["wind_kw"],
                "hydro_kw": running["hydro_kw"],
                "battery_kw": running["battery_kw"],
                "biogas_kw": running["biogas_kw"],
                "others_kw": running["others_kw"],
                "total_kw": total_kw,

                "state_name": sname,
                "state_slug": center_by_state[sname]["state_slug"],
                "state_number": center_by_state[sname]["state_number"],
                "year_bin_slug": bin_slug,
                "year_bin_label": bin_label,

                "_x": center_by_state[sname]["_x"],
                "_y": center_by_state[sname]["_y"],
            }

            cumulative_by_bin.setdefault(bin_slug, []).append(row)
            global_totals.append(total_kw)

    # ----------------------------------------------------------
    #   STEP C) Write per-bin point outputs (CUMULATIVE)
    # ----------------------------------------------------------
    all_bin_stats = []

    for slug, label, *_ in YEAR_BINS:
        rows = cumulative_by_bin.get(slug, [])
        if not rows:
            print(f"[SKIP] No rows for bin {slug}")
            continue

        bin_dir = OUT_BASE / slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        gdf = gpd.GeoDataFrame(
            rows,
            geometry=[Point(t["_x"], t["_y"]) for t in rows],
            crs="EPSG:4326",
        )
        gdf = gdf.drop(columns=["_x", "_y"])
        out_pts = bin_dir / f"de_state_pies_{slug}.geojson"
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
            "is_cumulative": True,
        }
        (bin_dir / f"state_pie_style_meta_{slug}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"[BIN SCALE] {slug}: vmin={vmin:.2f}, vmax={vmax:.2f}, states={len(gdf)}  -> {out_pts.name}")
        all_bin_stats.append((slug, vmin, vmax, len(gdf)))


    # ----------------------------------------------------------
    #   STEP D) Germany-wide totals per bin:
    #     - PERIOD stack (per-bin contribution)
    #     - then CUMULATIVE across bins (for the row chart)
    #   PLUS:
    #     - ROW chart geometries (POLYGONS + POINTS) -> de_yearly_totals_chart.geojson
    #     - ROW chart guide lines (LINESTRINGS)      -> de_yearly_totals_chart_guides.geojson
    #     - STATE column chart split output:
    #         * bars   (POLYGONS only) -> de_state_totals_columnChart_bars.geojson
    #         * labels (POINTS only)   -> de_state_totals_columnChart_labels.geojson
    # ----------------------------------------------------------

    PART_FIELDS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]

    # -------------------------------------------------------------------
    # D1) PERIOD sums (Germany-wide): sum period_by_state_bin over states
    # -------------------------------------------------------------------
    per_bin_energy_period = {}  # slug -> {energy_kw sums in THIS period}
    for slug, _label, *_ in YEAR_BINS:
        sums = {f: 0.0 for f in PART_FIELDS}
        found_any = False

        for sname in all_states:
            parts = period_by_state_bin.get((sname, slug), None)
            if parts is None:
                continue
            found_any = True
            for f in PART_FIELDS:
                sums[f] += float(parts.get(f, 0.0) or 0.0)

        if found_any:
            per_bin_energy_period[slug] = sums

    # -------------------------------------------------------------------
    # D2) CUMULATIVE across bins (Germany-wide) -> yearly_totals + bin_energy_totals
    # -------------------------------------------------------------------
    yearly_totals = []         # list of bins with cumulative totals (for labeling / sorting)
    bin_energy_totals = {}     # slug -> {energy cumulative sums}

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

        yearly_totals.append({
            "year_bin_slug": slug,
            "year_bin_label": BIN_LABEL[slug],
            "total_kw": total_kw,  # cumulative total for DE chart
        })

        # store the cumulative energy composition for this slug
        bin_energy_totals[slug] = dict(cumulative)

    # Write yearly totals JSON (cumulative)
    if yearly_totals:
        totals_json = OUT_BASE / "de_yearly_totals.json"
        totals_json.write_text(
            json.dumps(yearly_totals, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[INFO] Wrote yearly totals JSON (cumulative) -> {totals_json.name}")
    else:
        print("[WARN] yearly_totals is empty -> row chart will be skipped.")

    # -------------------------------------------------------------------
    # D3) ROW CHART geometry (cumulative) + GUIDE LINES
    # -------------------------------------------------------------------
    # Germany approx extent: 5.5–15.5E, 47–55.5N
    CHART_BASE_LON = -2.2    # left edge of the bars (further west)
    CHART_BASE_LAT = 47.5    # bottom (for the lowest year bar)
    MAX_BAR_WIDTH  = 6.8     # how far it extends east in degrees
    BAR_HEIGHT_DEG = 0.15    # height of each bar
    BAR_GAP_DEG    = 0.05    # gap between bars

    # fixed X positions
    YEAR_LABEL_LON  = CHART_BASE_LON - 0.8  # year labels
    VALUE_LABEL_LON = 5.3                   # numbers column
    GUIDE_END_LON   = VALUE_LABEL_LON - 0.35  # stop before the numbers

    # stack order for drawing (visual preference)
    STACK_ORDER = ["hydro_kw", "biogas_kw", "pv_kw", "wind_kw", "others_kw", "battery_kw"]

    # prepare features
    chart_features = []   # polygons + points
    guide_features = []   # lines only

    vals = [info["total_kw"] for info in yearly_totals if float(info["total_kw"]) > 0.0]
    if vals:
        max_total = float(max(vals))

        # We draw from TOP to BOTTOM: newest on top (reverse list),
        # but y-position is computed with idx so they stack nicely.
        yearly_totals_rev = list(reversed(yearly_totals))

        for idx, info in enumerate(yearly_totals_rev):
            slug  = info["year_bin_slug"]
            label = info["year_bin_label"]
            total = float(info["total_kw"])
            if total <= 0:
                continue

            energy_sums = bin_energy_totals.get(slug, None)
            if energy_sums is None:
                continue

            # y-position (bottom-up)
            y0 = CHART_BASE_LAT + idx * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
            y1 = y0 + BAR_HEIGHT_DEG
            y_center = 0.5 * (y0 + y1)

            # compute total bar width (scaled by max_total)
            bar_ratio = total / max_total if max_total > 0 else 0.0
            bar_ratio = max(0.0, min(1.0, bar_ratio))
            bar_width_total = bar_ratio * MAX_BAR_WIDTH

            x_base = CHART_BASE_LON

            # ---- stacked bar segments (POLYGONS) ----
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

                poly = Polygon([
                    (x_base, y0),
                    (x1,    y0),
                    (x1,    y1),
                    (x_base, y1),
                    (x_base, y0)
                ])

                chart_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "energy_type": key,
                    "energy_kw": seg_val,
                    "total_kw": total,
                    "label_anchor": 0,
                    "value_anchor": 0,
                    "geometry": poly,
                })

                x_base = x1  # advance

            # ---- GUIDE LINE: from bar end -> numbers column (LINESTRING) ----
            start_x = x_base + 0.05
            end_x = GUIDE_END_LON
            if start_x < end_x:
                guide_line = LineString([(start_x, y_center), (end_x, y_center)])
                guide_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "kind": "guide",
                    "geometry": guide_line,
                })

            # ---- YEAR LABEL POINT ----
            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 1,
                "value_anchor": 0,
                "geometry": Point(YEAR_LABEL_LON, y_center),
            })

            # ---- VALUE LABEL POINT (numbers only; unit handled elsewhere in QGIS style) ----
            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "others_kw",
                "energy_kw": 0.0,
                "total_kw": total,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(VALUE_LABEL_LON, y_center),
            })

        # ---- CHART TITLE POINT (add ONCE, outside the loop) ----
        title_y = CHART_BASE_LAT + (len(yearly_totals_rev) + 1) * (BAR_HEIGHT_DEG + BAR_GAP_DEG)
        title_x = CHART_BASE_LON + MAX_BAR_WIDTH / 2.0

        chart_features.append({
            "year_bin_slug": "title",
            "year_bin_label": "Cumulative Installed Power (2-Year Periods)",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": Point(title_x, title_y),
        })

        # ---- UNIT POINT (optional; keep if your style uses it) ----
        # If you decided to remove this and put GW inside title in style,
        # you can delete this block safely.
        chart_features.append({
            "year_bin_slug": "unit",
            "year_bin_label": "GW",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": Point(VALUE_LABEL_LON, title_y),
        })

        # ---- YEAR HEADINGS (top of Germany) ----
        HEADING_X_MAIN = 9.3
        HEADING_Y_MAIN = 54.9
        HEADING_X_SUB  = 11.8
        HEADING_Y_SUB  = 54.8

        for info in yearly_totals:
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            cum_total_kw = float(info["total_kw"])
            cum_total_gw = cum_total_kw / 1_000_000.0

            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": label,
                "energy_type": "heading_main",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_MAIN, HEADING_Y_MAIN),
            })

            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": f"Installed Power (Period): n/a",  # keep your period logic elsewhere if needed
                "energy_type": "heading_sub",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_SUB, HEADING_Y_SUB),
            })

        # write row chart GeoJSON
        chart_gdf = gpd.GeoDataFrame(chart_features, geometry="geometry", crs="EPSG:4326")
        chart_path = OUT_BASE / "de_yearly_totals_chart.geojson"
        chart_gdf.to_file(chart_path, driver="GeoJSON")
        print(f"[INFO] Wrote cumulative yearly total ROW chart -> {chart_path.name} ({len(chart_gdf)} features)")

        # write guide lines GeoJSON
        if guide_features:
            guides_gdf = gpd.GeoDataFrame(guide_features, geometry="geometry", crs="EPSG:4326")
            guides_path = OUT_BASE / "de_yearly_totals_chart_guides.geojson"
            guides_gdf.to_file(guides_path, driver="GeoJSON")
            print(f"[INFO] Wrote row chart guide lines -> {guides_path.name} ({len(guides_gdf)} lines)")
        else:
            print("[WARN] No guide lines created (guide_features empty).")

    else:
        print("[WARN] No valid totals for row chart (vals empty). Row chart skipped.")


    # -------------------------------------------------------------------
    # D4) STATE STACKED COLUMN CHART (16 columns, cumulative totals per bin)
    #     Split output: BARS (polygons) + LABELS (points)
    # -------------------------------------------------------------------
    # Geometry settings (you can tweak later)
    STATE_COL_X0 = 16.2
    STATE_COL_BASE_Y = 47.6
    STATE_COL_MAX_H = 6.2
    STATE_COL_W = 0.26
    STATE_COL_GAP = 0.10

    STATE_COL_LABEL_Y = STATE_COL_BASE_Y - 0.30
    STATE_COL_VALUE_Y_PAD = 0.08

    STATE_COL_TITLE_X = 18.7
    STATE_COL_TITLE_Y = 54.2

    state_bar_features = []   # polygons only
    state_lbl_features = []   # points only

    # max cumulative total among all states+bins for consistent scaling
    max_state_total = 0.0
    for slug, _label, *_ in YEAR_BINS:
        for row in cumulative_by_bin.get(slug, []):
            max_state_total = max(max_state_total, float(row.get("total_kw", 0.0) or 0.0))

    if max_state_total <= 0.0:
        print("[WARN] STATE column chart skipped: max_state_total <= 0")
    else:
        def _state_sort_key(r):
            try:
                return int(r.get("state_number", 999))
            except Exception:
                return 999

        # For each bin, build 16 columns
        for slug, bin_label, *_ in YEAR_BINS:
            rows = sorted(cumulative_by_bin.get(slug, []), key=_state_sort_key)
            if not rows:
                continue

            for r in rows:
                sn = r.get("state_number")
                if sn is None:
                    continue
                try:
                    sn_int = int(sn)
                except Exception:
                    continue

                total_kw = float(r.get("total_kw", 0.0) or 0.0)
                ratio_total = max(0.0, min(1.0, total_kw / max_state_total))
                col_h = ratio_total * STATE_COL_MAX_H

                x_left = STATE_COL_X0 + (sn_int - 1) * (STATE_COL_W + STATE_COL_GAP)
                x_right = x_left + STATE_COL_W
                x_center = 0.5 * (x_left + x_right)

                y_base = STATE_COL_BASE_Y
                y_top = y_base + col_h

                # ----- stacked segments (POLYGONS) -----
                y_cursor = y_base
                for key in STACK_ORDER:
                    part_kw = float(r.get(key, 0.0) or 0.0)
                    if total_kw <= 0 or part_kw <= 0:
                        continue

                    seg_ratio = max(0.0, min(1.0, part_kw / total_kw))
                    seg_h = seg_ratio * col_h
                    if seg_h <= 0:
                        continue

                    poly = Polygon([
                        (x_left,  y_cursor),
                        (x_right, y_cursor),
                        (x_right, y_cursor + seg_h),
                        (x_left,  y_cursor + seg_h),
                        (x_left,  y_cursor),
                    ])

                    state_bar_features.append({
                        "year_bin_slug": slug,
                        "year_bin_label": bin_label,
                        "state_number": sn_int,
                        "energy_type": key,  # MUST match PALETTE keys in QGIS style
                        "total_kw": total_kw,
                        "geometry": poly,
                    })

                    y_cursor += seg_h

                # ----- labels (POINTS) -----
                state_lbl_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": bin_label,
                    "state_number": sn_int,
                    "kind": "state_label",
                    "total_kw": total_kw,
                    "geometry": Point(x_center, STATE_COL_LABEL_Y),
                })

                state_lbl_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": bin_label,
                    "state_number": sn_int,
                    "kind": "value_label",
                    "total_kw": total_kw,
                    "geometry": Point(x_center, y_top + STATE_COL_VALUE_Y_PAD),
                })

        # Title point (add ONCE)
        state_lbl_features.append({
            "year_bin_slug": "state_title",
            "year_bin_label": "Cumulative Installed Power by State (GW)",
            "state_number": 0,
            "kind": "title",
            "total_kw": 0.0,
            "geometry": Point(STATE_COL_TITLE_X, STATE_COL_TITLE_Y),
        })

        # Write two GeoJSON outputs
        state_col_bars_path = OUT_BASE / "de_state_totals_columnChart_bars.geojson"
        state_col_labels_path = OUT_BASE / "de_state_totals_columnChart_labels.geojson"

        bars_gdf = gpd.GeoDataFrame(state_bar_features, geometry="geometry", crs="EPSG:4326")
        labels_gdf = gpd.GeoDataFrame(state_lbl_features, geometry="geometry", crs="EPSG:4326")

        bars_gdf.to_file(state_col_bars_path, driver="GeoJSON")
        labels_gdf.to_file(state_col_labels_path, driver="GeoJSON")

        print(f"[INFO] Wrote STATE column chart BARS   -> {state_col_bars_path.name} ({len(bars_gdf)} features)")
        print(f"[INFO] Wrote STATE column chart LABELS -> {state_col_labels_path.name} ({len(labels_gdf)} features)")



    # ----------------------------------------------------------
    #   STEP E) GLOBAL meta for all-years sizing of pies + HUD
    # ----------------------------------------------------------
    if global_totals:
        gmin = float(min(global_totals))
        gmax = float(max(global_totals))
        GLOBAL_META.write_text(
            json.dumps({"min_total_kw": gmin, "max_total_kw": gmax}, indent=2),
            encoding="utf-8",
        )
        print(f"[GLOBAL SCALE] min={gmin:.2f}, max={gmax:.2f}  -> {GLOBAL_META.name}")

        # # ---- ROW-ALIGNED HUD STATE NAMES ----
        # HUD_X = 17.0
        # HUD_BASE_Y = 54.0
        # HUD_ROW_STEP = -0.40

        # static_rows = []
        # sorted_states = sorted(STATE_NAME_TO_NUMBER.items(), key=lambda kv: kv[1])

        # for idx, (sname, num) in enumerate(sorted_states):
        #     y = HUD_BASE_Y + idx * HUD_ROW_STEP
        #     x = HUD_X
        #     slug = OFFICIAL_TO_SLUG.get(sname, normalize_text(sname))

        #     static_rows.append({
        #         "state_name": sname,
        #         "state_slug": slug,
        #         "state_number": int(num),
        #         "geometry": Point(x, y),
        #     })

        # static_gdf = gpd.GeoDataFrame(static_rows, geometry="geometry", crs="EPSG:4326")
        # static_path = OUT_BASE / "de_state_numbers_fixed.geojson"
        # static_gdf.to_file(static_path, driver="GeoJSON")
        # print(f"[INFO] Wrote HUD state-number layer (row aligned) with {len(static_gdf)} states -> {static_path.name}")

        # ---- ENERGY TYPE LEGEND (top-left, fixed positions) ----
        LEG_BASE_LON   = -2.2
        LEG_LABEL_LON  = 4
        LEG_TOP_LAT    = 54.9
        LEG_ROW_STEP   = -0.2

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
        legend_path = OUT_BASE / "de_energy_legend_points.geojson"
        legend_gdf.to_file(legend_path, driver="GeoJSON")
        print(f"[INFO] Wrote energy legend layer -> {legend_path.name}")

    print("[DONE] step1_3 complete.")


if __name__ == "__main__":
    main()
