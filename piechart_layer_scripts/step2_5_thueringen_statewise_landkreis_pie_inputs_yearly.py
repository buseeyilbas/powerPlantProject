# Filename: step2_5_thueringen_statewise_landkreis_pie_inputs_yearly.py
# Purpose : Build THUERINGEN yearly Landkreis pie INPUT POINTS per 2-year bin (Landkreis-level).
#           - Aggregates PERIOD power by (Landkreis, year-bin) and splits by energy type.
#           - Converts PERIOD -> CUMULATIVE across bins (so pies grow over time).
#           - Uses fixed Landkreis centers from step0 output (thueringen_landkreis_centers.geojson).
#           - IMPORTANT: Assigns Landkreis using:
#               (1) row attribute candidates (Landkreis / NAME_2 / ...)
#               (2) polygon fallback (GADM L2) for missing/dirty Landkreis fields
#           - IMPORTANT: Drops rows that do not map to a known Thüringen Landkreis center.
#             This is the canonical filter you MUST mirror in the state pipeline if you want consistent power.
#           - Writes:
#               * Per-bin CUMULATIVE pie INPUT points (one point per Landkreis per bin)
#               * Global meta (all-bins min/max) for sizing
#               * Thüringen cumulative ROW chart (stacked by energy type) + headings
#               * ROW chart guide lines (separate GeoJSON)
#               * ROW chart frame (separate GeoJSON)
#               * Energy type legend points
#
# Notes:
# - MW is used for labeling (values are stored as kW, styles convert to MW).
# - Coordinates for charts/headings are intentionally coarse (tune later in QGIS for Thüringen zoom).
# - All comments and filenames are in English.

from __future__ import annotations

from pathlib import Path
import os
import re
import json
import unicodedata
from typing import Dict, Tuple, Optional, Iterable, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, LineString


# ---------- PATHS ----------
# IMPORTANT: This MUST point to Thüringen-only 4-check output folder (plant points).
INPUT_ROOT = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_4_checks\thueringen")

# Output folder for yearly Landkreis pie inputs + chart/legend layers
OUT_BASE = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_statewise_landkreis_pies_yearly")

# step0 output (Landkreis centers)
CENTERS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_landkreis_centers\thueringen_landkreis_centers.geojson"
)

# GADM L2 for polygon fallback assignment (Thüringen Landkreise polygons)
GADM_L2_PATH = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json")

# Global style meta used by the QGIS style script (all-years sizing)
GLOBAL_META = OUT_BASE / "_THUERINGEN_GLOBAL_style_meta.json"


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
YEAR_SLUG_ORDER = [slug for (slug, _label, _y1, _y2) in YEAR_BINS]
INCLUDE_UNKNOWN = False  # if False: drop rows whose year/bin is unknown


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

PART_FIELDS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]
STACK_ORDER = ["hydro_kw", "biogas_kw", "pv_kw", "wind_kw", "others_kw", "battery_kw"]


# ---------- THUERINGEN CONSTANTS ----------
STATE_NAME = "Thüringen"
STATE_SLUG = "thueringen"
STATE_NUMBER = 16


# ---------- HELPERS ----------
def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def parse_number(val) -> Optional[float]:
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


def scan_geojsons(folder: Path) -> Iterable[Path]:
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(".geojson"):
                yield Path(root) / fn


def normalize_energy(val, filename_hint="") -> str:
    if val is not None:
        s = str(val).strip()
        if s in ENERGY_CODE_TO_LABEL:
            return ENERGY_CODE_TO_LABEL[s]

        sn = norm(s)
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

    fn = norm(filename_hint)
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


def extract_year(row, filename_hint="") -> Optional[int]:
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


def year_to_bin(y: Optional[int]) -> Tuple[str, str]:
    if y is None:
        return ("unknown", "Unknown / NA")
    for slug, label, start, end in YEAR_BINS:
        if (start is None or y >= start) and (end is None or y <= end):
            return (slug, label)
    return ("unknown", "Unknown / NA")


def ensure_point_geometries(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if g.empty:
        return g
    if g.geometry is None:
        return g.iloc[0:0].copy()
    g = g[g.geometry.notna()].copy()
    if g.empty:
        return g
    g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])].copy()
    if g.empty:
        return g
    return g


def load_thueringen_centers() -> Tuple[
    Dict[str, Tuple[float, float]],
    Dict[str, str],
    Dict[str, int],
]:
    """
    Load Thüringen Landkreis centers from step0 output.

    Returns
    -------
    centers: kreis_slug -> (lon, lat)
    slug_to_name: kreis_slug -> kreis_name
    """
    if not CENTERS_PATH.exists():
        raise FileNotFoundError(f"[FATAL] Centers file not found: {CENTERS_PATH}")

    g = gpd.read_file(str(CENTERS_PATH))
    if g.empty:
        raise RuntimeError("[FATAL] Centers file is empty.")

    # Accept a few schema variants
    slug_col = None
    for c in ["kreis_slug", "kreis_key", "landkreis_slug", "slug"]:
        if c in g.columns:
            slug_col = c
            break
    if slug_col is None:
        raise RuntimeError("[FATAL] Centers file has no kreis_slug/kreis_key column.")

    name_col = None
    for c in ["kreis_name", "landkreis_name", "name"]:
        if c in g.columns:
            name_col = c
            break

    number_col = None
    for c in ["kreis_number", "landkreis_number", "number", "kreis_num", "lk_number"]:
        if c in g.columns:
            number_col = c
            break

    centers: Dict[str, Tuple[float, float]] = {}
    slug_to_name: Dict[str, str] = {}
    slug_to_number: Dict[str, int] = {}

    for _, r in g.iterrows():
        ks = str(r.get(slug_col, "")).strip()
        if not ks:
            continue
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == "Point":
            centers[ks] = (float(geom.x), float(geom.y))
        else:
            # fallback: centroid if needed
            c = geom.centroid
            centers[ks] = (float(c.x), float(c.y))

        if name_col:
            nm = r.get(name_col, None)
            if nm is not None:
                slug_to_name[ks] = str(nm)

        if number_col:
            try:
                slug_to_number[ks] = int(r.get(number_col))
            except Exception:
                pass

    if not centers:
        raise RuntimeError("[FATAL] No centers parsed from centers file.")

    return centers, slug_to_name, slug_to_number


def load_gadm_l2_thueringen_polys() -> gpd.GeoDataFrame:
    """
    Load GADM level-2 polygons for Germany and filter to Thüringen.
    Uses 'NAME_1'/'NAME_2' in GADM data.
    """
    if not GADM_L2_PATH.exists():
        raise FileNotFoundError(f"[FATAL] GADM L2 file not found: {GADM_L2_PATH}")

    g = gpd.read_file(str(GADM_L2_PATH))
    if g.empty:
        raise RuntimeError("[FATAL] GADM L2 file is empty.")

    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    # Thüringen can appear as "Thüringen" or "Thueringen"
    if "NAME_1" not in g.columns or "NAME_2" not in g.columns:
        raise RuntimeError("[FATAL] GADM L2 schema missing NAME_1/NAME_2.")

    g = g[g["NAME_1"].astype(str).apply(norm).isin({"thuringen", "thueringen"})].copy()
    if g.empty:
        raise RuntimeError("[FATAL] No Thüringen polygons found in GADM L2.")

    # Create kreis_slug
    g["kreis_slug"] = g["NAME_2"].astype(str).apply(norm)

    return g[["NAME_2", "kreis_slug", "geometry"]].copy()


def pick_first_nonempty(row, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in row and pd.notna(row[c]):
            s = str(row[c]).strip()
            if s and s.lower() not in {"nan", "none"}:
                return s
    return None


KREIS_FIELD_CANDIDATES = [
    "Landkreis", "landkreis",
    "kreis", "Kreis",
    "NAME_2", "name_2",
    "county",
    "ADM2", "adm2",
]


def assign_kreis_slug_with_fallback(gdf: gpd.GeoDataFrame, lk_poly: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign kreis_slug using:
      (1) attribute candidates
      (2) polygon spatial join fallback for missing/dirty cases
    """
    gdf = gdf.copy()

    # attribute-based
    raw_vals = []
    for _, r in gdf.iterrows():
        raw_vals.append(pick_first_nonempty(r, KREIS_FIELD_CANDIDATES))
    gdf["_kreis_raw"] = raw_vals
    gdf["_kreis_attr_slug"] = gdf["_kreis_raw"].apply(lambda v: norm(v) if v else "")

    # for those still empty -> spatial join
    need_fallback = gdf["_kreis_attr_slug"].eq("") | gdf["_kreis_attr_slug"].isna()
    if need_fallback.any():
        pts = gdf[need_fallback].copy()
        pts = pts[pts.geometry.notna()].copy()
        if not pts.empty:
            if pts.crs is None:
                pts = pts.set_crs("EPSG:4326", allow_override=True)
            if lk_poly.crs is None:
                lk_poly = lk_poly.set_crs("EPSG:4326", allow_override=True)

            joined = gpd.sjoin(
                pts,
                lk_poly[["kreis_slug", "geometry"]],
                how="left",
                predicate="within",
            )
            gdf.loc[joined.index, "_kreis_attr_slug"] = joined["kreis_slug"].fillna("").values

    gdf["kreis_slug"] = gdf["_kreis_attr_slug"].fillna("").astype(str)
    return gdf


# ---------- MAIN ----------
def main() -> None:
    OUT_BASE.mkdir(parents=True, exist_ok=True)

    centers, slug_to_name, slug_to_number = load_thueringen_centers()
    lk_poly = load_gadm_l2_thueringen_polys()

    # ---- Read all plant points ----
    frames: List[gpd.GeoDataFrame] = []

    for p in scan_geojsons(INPUT_ROOT):
        try:
            g = gpd.read_file(str(p))
            if g.empty:
                continue
            if g.crs is None:
                g = g.set_crs("EPSG:4326", allow_override=True)

            g = ensure_point_geometries(g)
            if g.empty:
                continue

            # Energy normalization
            if "energy_source_label" in g.columns:
                g["energy_norm"] = g["energy_source_label"].apply(lambda v: normalize_energy(v, p.name))
            elif "Energietraeger" in g.columns:
                g["energy_norm"] = g["Energietraeger"].apply(lambda v: normalize_energy(v, p.name))
            else:
                g["energy_norm"] = normalize_energy(None, p.name)

            # Power column detection
            power_col = None
            for c in [
                "power_kw", "Nettonennleistung", "Bruttoleistung", "Nennleistung",
                "Leistung", "installed_power_kw", "kw", "power"
            ]:
                if c in g.columns:
                    power_col = c
                    break
            if power_col is None:
                continue

            g["_power"] = g[power_col].apply(parse_number)
            g = g[(pd.notna(g["_power"])) & (g["_power"] > 0)].copy()
            if g.empty:
                continue

            # Year/bin
            g["_year"] = [extract_year(r, p.name) for _, r in g.iterrows()]
            bins = [year_to_bin(y) for y in g["_year"]]
            g["year_bin_slug"] = [b[0] for b in bins]
            g["year_bin_label"] = [b[1] for b in bins]

            g["state_name"] = STATE_NAME
            g["state_slug"] = STATE_SLUG

            frames.append(g)

        except Exception as e:
            print(f"[WARN] Skipped {p}: {e}")

    if not frames:
        raise RuntimeError("[FATAL] No usable features after parsing.")

    df = pd.concat(frames, ignore_index=True)
    if not INCLUDE_UNKNOWN:
        df = df[df["year_bin_slug"] != "unknown"].copy()

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # Assign Landkreis slug
    gdf = assign_kreis_slug_with_fallback(gdf, lk_poly)

    # Canonical filter: keep ONLY rows that map to known Thüringen centers
    before_n = len(gdf)
    before_sum = float(gdf["_power"].fillna(0).sum())

    gdf = gdf[gdf["kreis_slug"].isin(set(centers.keys()))].copy()

    after_n = len(gdf)
    after_sum = float(gdf["_power"].fillna(0).sum())

    if after_n == 0:
        raise RuntimeError("[FATAL] No usable yearly rows after Landkreis assignment + centers filtering.")

    print(f"[CHECK] rows kept after centers filter: {after_n}/{before_n} (dropped {before_n - after_n})")
    print(f"[CHECK] power sum kept: {after_sum:,.2f} kW  (dropped {before_sum - after_sum:,.2f} kW)")

    print("[CHECK] year_bin_slug counts:")
    print(gdf["year_bin_slug"].value_counts(dropna=False))

    # ----------------------------------------------------------
    # A) PERIOD sums per (kreis_slug, year_bin_slug)
    # ----------------------------------------------------------
    period_by_kreis_bin: Dict[Tuple[str, str], dict] = {}

    for (yslug, kreis_slug), grp in gdf.groupby(["year_bin_slug", "kreis_slug"], dropna=False):
        parts = {f: 0.0 for f in PART_FIELDS}
        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                parts[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                parts[OTHERS_FIELD] += pkw

        parts["total_kw"] = float(sum(parts[f] for f in PART_FIELDS))
        period_by_kreis_bin[(kreis_slug, yslug)] = parts

    # ----------------------------------------------------------
    # B) CUMULATIVE per Landkreis across bins -> per_bin_rows_cum
    #    (This is the key fix: pies grow over time)
    # ----------------------------------------------------------
    per_bin_rows: Dict[str, List[dict]] = {}
    global_totals: List[float] = []

    # deterministic kreis order for stable output (nice for debugging)
    kreis_list = sorted(list(centers.keys()))

    cumulative_by_kreis: Dict[str, dict] = {
        ks: {f: 0.0 for f in PART_FIELDS}
        for ks in kreis_list
    }

    for slug, _label, *_ in YEAR_BINS:
        rows_out: List[dict] = []

        for ks in kreis_list:
            inc = period_by_kreis_bin.get((ks, slug))
            if inc:
                for f in PART_FIELDS:
                    cumulative_by_kreis[ks][f] += float(inc.get(f, 0.0) or 0.0)

            total_kw = float(sum(cumulative_by_kreis[ks][f] for f in PART_FIELDS))
            if total_kw <= 0:
                continue

            cx, cy = centers[ks]

            row = {
                "state_name": STATE_NAME,
                "state_slug": STATE_SLUG,
                "state_number": STATE_NUMBER,

                # IMPORTANT: keep BOTH keys for step2_6 compatibility
                "kreis_slug": ks,
                "kreis_key": ks,
                "kreis_name": slug_to_name.get(ks, ks),

                "year_bin_slug": slug,
                "year_bin_label": BIN_LABEL[slug],

                "_x": float(cx),
                "_y": float(cy),

                **{f: float(cumulative_by_kreis[ks][f]) for f in PART_FIELDS},
                "total_kw": total_kw,
            }

            rows_out.append(row)
            global_totals.append(total_kw)

        if rows_out:
            per_bin_rows[slug] = rows_out

    # ---- Global sizing meta (based on CUMULATIVE totals) ----
    if global_totals:
        gmin = float(min(global_totals))
        gmax = float(max(global_totals))
        GLOBAL_META.write_text(
            json.dumps({"min_total_kw": gmin, "max_total_kw": gmax}, indent=2),
            encoding="utf-8",
        )
        print(
            f"[GLOBAL SCALE] Thüringen landkreis pies (CUM): min={gmin:,.2f} kW, max={gmax:,.2f} kW -> {GLOBAL_META.name}"
        )

    # ---- Write per-bin CUMULATIVE input points ----
    for slug, _, *_ in YEAR_BINS:
        rows = per_bin_rows.get(slug, [])
        if not rows:
            continue

        bin_dir = OUT_BASE / slug
        bin_dir.mkdir(parents=True, exist_ok=True)

        out_path = bin_dir / f"thueringen_landkreis_pies_{slug}.geojson"
        out_gdf = gpd.GeoDataFrame(
            rows,
            geometry=[Point(r["_x"], r["_y"]) for r in rows],
            crs="EPSG:4326",
        ).drop(columns=["_x", "_y"])

        out_gdf.to_file(out_path, driver="GeoJSON")
        print(f"[BIN INPUT CUM] wrote {out_path.name} (features={len(out_gdf)})")

    # ----------------------------------------------------------
    # C) Thüringen totals per bin (CUMULATIVE already) + ROW chart + guides + frame + headings
    # ----------------------------------------------------------
    yearly_totals: List[dict] = []
    bin_energy_totals: Dict[str, dict] = {}

    for slug, _label, *_ in YEAR_BINS:
        rows = per_bin_rows.get(slug, [])
        if not rows:
            continue

        sums = {f: 0.0 for f in PART_FIELDS}
        for r in rows:
            for f in PART_FIELDS:
                sums[f] += float(r.get(f, 0.0) or 0.0)

        total_kw = float(sum(sums.values()))
        if total_kw <= 0:
            continue

        yearly_totals.append({
            "year_bin_slug": slug,
            "year_bin_label": BIN_LABEL[slug],
            "total_kw": total_kw,
        })
        bin_energy_totals[slug] = sums

    if yearly_totals:
        totals_json = OUT_BASE / "thueringen_landkreis_yearly_totals.json"
        totals_json.write_text(
            json.dumps(yearly_totals, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[INFO] Wrote yearly totals JSON (cumulative) -> {totals_json.name}")

        # ---- ROW CHART (horizontal cumulative chart) ----
        # (Keep these coarse; you can tune in QGIS later.)
        CHART_BASE_LON = 8.5
        CHART_BASE_LAT = 50.25
        MAX_BAR_WIDTH  = 1.1
        BAR_HEIGHT_DEG = 0.035
        BAR_GAP_DEG    = 0.012

        YEAR_LABEL_LON  = CHART_BASE_LON - 0.12
        VALUE_LABEL_LON = 9.75

        # guides should stop before the numbers column
        GUIDE_END_LON = VALUE_LABEL_LON - 0.10

        vals = [info["total_kw"] for info in yearly_totals if info["total_kw"] > 0]
        max_total = float(max(vals)) if vals else 0.0

        chart_features: List[dict] = []
        guide_features: List[dict] = []

        # reversed => oldest at top or bottom? (same pattern as your other scripts)
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

            # stacked segments
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

            # GUIDE LINE (bar end -> numbers column)
            start_x = x_base + 0.01
            end_x = GUIDE_END_LON
            if start_x < end_x:
                guide_features.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "kind": "guide",
                    "geometry": LineString([(start_x, y_center), (end_x, y_center)])
                })

            # Year label point
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

            # Value label point
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

        # Title row y
        title_y = CHART_BASE_LAT + (len(yearly_totals) + 1) * (BAR_HEIGHT_DEG + BAR_GAP_DEG)

        # Title point (no unit inside title)
        chart_features.append({
            "year_bin_slug": "title",
            "year_bin_label": "Thüringen - Cumulative Installed Power",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": Point(CHART_BASE_LON + MAX_BAR_WIDTH / 2.0, title_y)
        })

        # Unit point aligned with numbers column, same row as title (step1_3 style)
        chart_features.append({
            "year_bin_slug": "unit",
            "year_bin_label": "MW",
            "energy_type": "others_kw",
            "energy_kw": 0.0,
            "total_kw": 0.0,
            "label_anchor": 0,
            "value_anchor": 0,
            "geometry": Point(VALUE_LABEL_LON, title_y)
        })

        # ---- Headings (coarse, per bin group) ----
        HEADING_X_MAIN = 10.8
        HEADING_Y_MAIN = 51.7
        HEADING_X_SUB  = 11.4
        HEADING_Y_SUB  = 51.6

        for info in yearly_totals:
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            cum_total_kw = float(info["total_kw"])
            cum_total_mw = cum_total_kw / 1000.0

            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": f"{label}",
                "energy_type": "heading_main",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_MAIN, HEADING_Y_MAIN),
            })
            chart_features.append({
                "year_bin_slug": slug,
                "year_bin_label": f"Installed Power: {cum_total_mw:,.1f} MW",
                "energy_type": "heading_sub",
                "energy_kw": 0.0,
                "total_kw": cum_total_kw,
                "label_anchor": 0,
                "value_anchor": 1,
                "geometry": Point(HEADING_X_SUB, HEADING_Y_SUB),
            })

        # ---- Write chart polygons+points ----
        chart_gdf = gpd.GeoDataFrame(chart_features, geometry="geometry", crs="EPSG:4326")
        chart_path = OUT_BASE / "thueringen_landkreis_yearly_totals_chart.geojson"
        chart_gdf.to_file(chart_path, driver="GeoJSON")
        print(f"[INFO] Wrote Thüringen landkreis cumulative ROW chart -> {chart_path.name} ({len(chart_gdf)} features)")

        # ---- Write guides (separate file) ----
        if guide_features:
            guides_gdf = gpd.GeoDataFrame(guide_features, geometry="geometry", crs="EPSG:4326")
            guides_path = OUT_BASE / "thueringen_landkreis_yearly_totals_chart_guides.geojson"
            guides_gdf.to_file(guides_path, driver="GeoJSON")
            print(f"[INFO] Wrote Thüringen row chart guide lines -> {guides_path.name} ({len(guides_gdf)} lines)")

        # ---- Frame (single rectangle, separate file) ----
        # Include year labels on the left + number column on the right
        frame_left   = YEAR_LABEL_LON - 0.10
        frame_right  = VALUE_LABEL_LON + 0.10
        frame_bottom = CHART_BASE_LAT - 0.02
        frame_top    = title_y + 0.05

        frame_poly = Polygon([
            (frame_left,  frame_bottom),
            (frame_right, frame_bottom),
            (frame_right, frame_top),
            (frame_left,  frame_top),
            (frame_left,  frame_bottom),
        ])

        frame_gdf = gpd.GeoDataFrame(
            [{"kind": "frame", "chart": "row", "unit": "MW"}],
            geometry=[frame_poly],
            crs="EPSG:4326",
        )
        frame_path = OUT_BASE / "thueringen_landkreis_yearly_totals_chart_frame.geojson"
        frame_gdf.to_file(frame_path, driver="GeoJSON")
        print(f"[INFO] Wrote Thüringen row chart frame -> {frame_path.name}")

        
        # ---- COLUMN CHART (23 Landkreis, stacked, cumulative) ----
        # Tune these in QGIS if needed; these are just sane defaults.
        COL_BASE_LON = 12.80
        COL_BASE_LAT = 50.25
        COL_W        = 0.060
        COL_GAP      = 0.025
        COL_MAX_H    = 1.00

        LABEL_DY     = 0.030   # below baseline
        VALUE_DY     = 0.020   # above bar top

        # Determine deterministic Landkreis order for 23 columns
        kreis_slugs = sorted(list(centers.keys()))
        if slug_to_number:
            kreis_slugs = sorted(
                kreis_slugs,
                key=lambda s: (slug_to_number.get(s, 999), s),
            )

        max_kreis_total_kw = float(max(global_totals)) if global_totals else 1.0
        col_meta_path = OUT_BASE / "thu_landkreis_totals_columnChart_meta.json"
        col_meta_path.write_text(
            json.dumps({"max_kreis_total_kw": max_kreis_total_kw}, indent=2),
            encoding="utf-8",
        )

        
        bars_rows: List[dict] = []
        label_rows: List[dict] = []

        TITLE_SLUG = "landkreis_title"

        label_rows.append({
            "year_bin_slug": TITLE_SLUG,
            "year_bin_label": "Thüringen - Cumulative Installed Power by Landkreis(MW)",
            "kind": "title",
            "landkreis_slug": "",
            "landkreis_number": 0,
            "total_kw": 0.0,
            "geometry": Point(COL_BASE_LON + 0.85, COL_BASE_LAT + COL_MAX_H + 0.05),
        })

        for info in yearly_totals:
            slug = info["year_bin_slug"]
            label = info["year_bin_label"]
            rows = per_bin_rows.get(slug, [])
            if not rows:
                continue

            # index rows by kreis
            by_kreis = {r["kreis_slug"]: r for r in rows if r.get("kreis_slug")}

            for idx, ks in enumerate(kreis_slugs):
                r = by_kreis.get(ks)
                if r is None:
                    continue

                total_kw = float(r.get("total_kw", 0.0) or 0.0)
                if total_kw <= 0:
                    continue

                lk_no = int(slug_to_number.get(ks, idx + 1))
                x0 = COL_BASE_LON + idx * (COL_W + COL_GAP)
                x1 = x0 + COL_W
                y  = COL_BASE_LAT

                # stacked segments
                for f in STACK_ORDER:
                    v = float(r.get(f, 0.0) or 0.0)
                    if v <= 0:
                        continue

                    h = (v / max_kreis_total_kw) * COL_MAX_H
                    y1 = y + h

                    bars_rows.append({
                        "state_name": STATE_NAME,
                        "state_slug": STATE_SLUG,
                        "state_number": STATE_NUMBER,

                        "year_bin_slug": slug,
                        "year_bin_label": label,

                        "landkreis_slug": ks,
                        "landkreis_number": lk_no,
                        "energy_type": f,

                        "value_kw": v,
                        "total_kw": total_kw,

                        "geometry": Polygon([(x0, y), (x1, y), (x1, y1), (x0, y1)]),
                    })

                    y = y1

                cx = (x0 + x1) / 2.0

                # Landkreis number label
                label_rows.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "kind": "landkreis_label",
                    "landkreis_slug": ks,
                    "landkreis_number": lk_no,
                    "total_kw": total_kw,
                    "geometry": Point(cx, COL_BASE_LAT - LABEL_DY),
                })

                # value label (top)
                bar_h = (total_kw / max_kreis_total_kw) * COL_MAX_H
                label_rows.append({
                    "year_bin_slug": slug,
                    "year_bin_label": label,
                    "kind": "value_label",
                    "landkreis_slug": ks,
                    "landkreis_number": lk_no,
                    "total_kw": total_kw,
                    "geometry": Point(cx, COL_BASE_LAT + bar_h + VALUE_DY),
                })

        if bars_rows:
            bars_path = OUT_BASE / "thu_landkreis_totals_columnChart_bars.geojson"

            bars_gdf = gpd.GeoDataFrame(bars_rows, crs="EPSG:4326")
            bars_gdf = bars_gdf.set_geometry("geometry")

            bars_gdf.to_file(bars_path, driver="GeoJSON")
            print(f"[COLUMN BARS] wrote {bars_path.name} (features={len(bars_gdf)})")

        if label_rows:
            labels_path = OUT_BASE / "thu_landkreis_totals_columnChart_labels.geojson"

            labels_gdf = gpd.GeoDataFrame(label_rows, crs="EPSG:4326")
            labels_gdf = labels_gdf.set_geometry("geometry")

            labels_gdf.to_file(labels_path, driver="GeoJSON")
            print(f"[COLUMN LABELS] wrote {labels_path.name} (features={len(labels_gdf)})")


        # ---- COLUMN CHART FRAME (single rectangle, separate file) ----
        total_width = len(kreis_slugs) * COL_W + (len(kreis_slugs) - 1) * COL_GAP

        col_frame_left = COL_BASE_LON - 0.08
        col_frame_right = COL_BASE_LON + total_width + 0.08
        col_frame_bottom = COL_BASE_LAT - 0.08   # includes x labels
        col_frame_top = COL_BASE_LAT + COL_MAX_H + 0.12  # includes title

        col_frame_poly = Polygon([
            (col_frame_left, col_frame_bottom),
            (col_frame_right, col_frame_bottom),
            (col_frame_right, col_frame_top),
            (col_frame_left, col_frame_top),
            (col_frame_left, col_frame_bottom),
        ])

        col_frame_gdf = gpd.GeoDataFrame(
            [{"kind": "frame", "chart": "column", "unit": "MW"}],
            geometry=[col_frame_poly],
            crs="EPSG:4326",
        )
        col_frame_path = OUT_BASE / "thu_landkreis_totals_columnChart_frame.geojson"
        col_frame_gdf.to_file(col_frame_path, driver="GeoJSON")
        print(f"[INFO] Wrote Thüringen column chart frame -> {col_frame_path.name}")

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
            "energy_type": etype,
            "legend_label": text,
            "geometry": Point(LEG_BASE_LON, y),
        })

    legend_gdf = gpd.GeoDataFrame(legend_feats, geometry="geometry", crs="EPSG:4326")
    legend_path = OUT_BASE / "thueringen_landkreis_energy_legend_points.geojson"
    legend_gdf.to_file(legend_path, driver="GeoJSON")
    print(f"[INFO] Wrote Thüringen energy legend layer -> {legend_path.name}")

    print("[DONE] step2_5 complete.")


if __name__ == "__main__":
    main()