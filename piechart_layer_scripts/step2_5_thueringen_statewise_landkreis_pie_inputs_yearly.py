# Filename: step2_5_thueringen_statewise_landkreis_pie_inputs_yearly.py
# Purpose : Build THUERINGEN yearly Landkreis pie INPUT POINTS per 2-year bin (Landkreis-level).
#           - Aggregates power by (Landkreis, year-bin) and splits by energy type.
#           - Uses fixed Landkreis centers from step0 output (thueringen_landkreis_centers.geojson).
#           - IMPORTANT: Assigns Landkreis using:
#               (1) row attribute candidates (Landkreis / NAME_2 / ...)
#               (2) polygon fallback (GADM L2) for missing/dirty Landkreis fields
#           - IMPORTANT: Drops rows that do not map to a known Thüringen Landkreis center.
#             This is the canonical filter you MUST mirror in the state pipeline if you want consistent power.
#           - Writes:
#               * Per-bin pie INPUT points (one point per Landkreis per bin)
#               * Global meta (all-years min/max) for sizing
#               * Thüringen cumulative row chart (stacked by energy type) + headings
#               * Energy type legend points
#
# Notes:
# - Coordinates for charts/headings are intentionally coarse (tune later in QGIS for Thüringen zoom).
# - All comments and filenames are in English (per your preference).

from __future__ import annotations

from pathlib import Path
import os
import re
import json
import unicodedata
from typing import Dict, Tuple, Optional, Iterable, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon


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


def load_thueringen_centers() -> Tuple[Dict[str, Tuple[float, float]], Dict[str, str]]:
    """
    Load Thüringen Landkreis centers from step0 output.

    Returns
    -------
    centers: dict[landkreis_slug] -> (lon, lat)
    slug_to_name: dict[landkreis_slug] -> landkreis_name
    """
    if not CENTERS_PATH.exists():
        raise RuntimeError(f"CENTERS_PATH not found: {CENTERS_PATH}")

    g = gpd.read_file(CENTERS_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    if "landkreis_slug" not in g.columns:
        raise RuntimeError("Centers file missing column: landkreis_slug")

    name_col = "landkreis_name" if "landkreis_name" in g.columns else None

    centers: Dict[str, Tuple[float, float]] = {}
    slug_to_name: Dict[str, str] = {}

    for _, r in g.iterrows():
        slug = str(r.get("landkreis_slug", "")).strip()
        if not slug:
            continue
        geom = r.geometry
        if geom is None or geom.is_empty or geom.geom_type != "Point":
            continue
        centers[slug] = (float(geom.x), float(geom.y))
        if name_col:
            slug_to_name[slug] = str(r.get(name_col, "")).strip() or slug
        else:
            slug_to_name[slug] = slug

    return centers, slug_to_name


def load_thueringen_landkreis_polygons() -> gpd.GeoDataFrame:
    """
    Load Thüringen Landkreis polygons from GADM L2 for polygon fallback assignment.
    Returns columns: landkreis_slug, geometry
    """
    if not GADM_L2_PATH.exists():
        raise RuntimeError(f"GADM_L2_PATH not found: {GADM_L2_PATH}")

    g = gpd.read_file(GADM_L2_PATH)
    if g.crs is None:
        g = g.set_crs("EPSG:4326", allow_override=True)

    if "NAME_1" not in g.columns or "NAME_2" not in g.columns:
        raise RuntimeError("GADM L2 is missing NAME_1/NAME_2 columns.")

    g = g[g["NAME_1"].astype(str).str.strip().str.lower().isin(["thüringen", "thueringen"])].copy()
    if g.empty:
        raise RuntimeError("No Thüringen polygons found in GADM L2.")

    g["landkreis_slug"] = g["NAME_2"].astype(str).apply(norm)
    return g[["landkreis_slug", "geometry"]].copy()


def pick_landkreis_from_row(row: pd.Series) -> Optional[str]:
    """
    Try to read Landkreis name/label from known column candidates.
    """
    candidates = ("Landkreis", "landkreis", "NAME_2", "kreis_name", "landkreis_name", "LandkreisName")
    for c in candidates:
        if c in row and pd.notna(row[c]):
            return str(row[c])
    return None


def ensure_point_geometries(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = g[~g.geometry.is_empty & g.geometry.notnull()].copy()
    g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])].copy()
    if g.empty:
        return g

    try:
        if "MultiPoint" in list(g.geometry.geom_type.unique()):
            g = g.explode(index_parts=False).reset_index(drop=True)
    except TypeError:
        g = g.explode().reset_index(drop=True)

    g = g[g.geometry.geom_type == "Point"].copy()
    return g


def assign_kreis_slug_with_fallback(
    pts: gpd.GeoDataFrame,
    lk_poly: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Assign kreis_slug to each point.
    Strategy:
      1) Use row attribute candidates if present.
      2) If missing/empty, use polygon lookup (within, then intersects).
    Output column: kreis_slug
    """
    pts = pts.copy()

    # 1) Attribute-based
    def attr_slug(r):
        v = pick_landkreis_from_row(r)
        return norm(v) if v else ""

    pts["kreis_slug"] = pts.apply(attr_slug, axis=1).fillna("").astype(str)

    missing = pts["kreis_slug"].eq("") | pts["kreis_slug"].isna()
    missing_n = int(missing.sum())
    if missing_n == 0:
        return pts

    missing_pts = pts[missing].copy()
    missing_pts = gpd.GeoDataFrame(missing_pts, geometry="geometry", crs="EPSG:4326")

    # within (strict)
    joined = gpd.sjoin(missing_pts, lk_poly, how="left", predicate="within")

    # intersects fallback for border cases
    still_missing = joined["landkreis_slug"].isna()
    if int(still_missing.sum()) > 0:
        joined2 = gpd.sjoin(
            joined[still_missing].drop(columns=["landkreis_slug", "index_right"], errors="ignore"),
            lk_poly,
            how="left",
            predicate="intersects",
        )
        joined.loc[still_missing, "landkreis_slug"] = joined2["landkreis_slug"].values

    # Write back
    fallback_series = joined["landkreis_slug"].fillna("").astype(str)
    pts.loc[missing, "kreis_slug"] = pts.loc[missing].index.map(lambda idx: fallback_series.to_dict().get(idx, ""))

    return pts

def build_landkreis_numbering_layers(
    lk_poly: gpd.GeoDataFrame,
    centers_slug_to_name: dict,
    out_base: Path,
    *,
    # Thüringen bbox (coarse) – sen zooma göre oynarsın
    list_x: float = 12.85,
    list_top_y: float = 51.75,
    list_step_y: float = -0.065,
    poly_label_size_hint: int = 12,
):
    """
    Create two GeoJSON layers:
      (1) Numbers inside Landkreis polygons (representative_point)
      (2) Right-side list of "N  LandkreisName" as points

    Outputs:
      - thueringen_landkreis_number_points.geojson
      - thueringen_landkreis_number_list_points.geojson
      - thueringen_landkreis_number_map.json (slug -> number + name)
    """

    # stable order
    slugs = sorted([str(s) for s in lk_poly["landkreis_slug"].dropna().unique().tolist()])
    slug_to_num = {slug: i + 1 for i, slug in enumerate(slugs)}

    # -------------- (1) Polygon interior label points --------------
    poly_points = []
    for _, r in lk_poly.iterrows():
        slug = str(r.get("landkreis_slug", "")).strip()
        if not slug or slug not in slug_to_num:
            continue

        geom = r.geometry
        if geom is None or geom.is_empty:
            continue

        # representative_point is guaranteed to be inside
        p = geom.representative_point()

        num = int(slug_to_num[slug])
        name = centers_slug_to_name.get(slug, slug)

        poly_points.append(
            {
                "landkreis_slug": slug,
                "landkreis_name": name,
                "num": num,
                "label": str(num),
                "font_size": poly_label_size_hint,
                "geometry": p,
            }
        )

    g_poly = gpd.GeoDataFrame(poly_points, geometry="geometry", crs="EPSG:4326")
    poly_out = out_base / "thueringen_landkreis_number_points.geojson"
    g_poly.to_file(poly_out, driver="GeoJSON")
    print(f"[INFO] Wrote Landkreis polygon numbers layer -> {poly_out.name} ({len(g_poly)} points)")

    # -------------- (2) Right-side list points --------------
    list_points = []
    y = list_top_y
    for slug in slugs:
        num = int(slug_to_num[slug])
        name = centers_slug_to_name.get(slug, slug)
        list_points.append(
            {
                "landkreis_slug": slug,
                "landkreis_name": name,
                "num": num,
                "label": f"{num}. {name}",
                "geometry": Point(list_x, y),
            }
        )
        y += list_step_y

    g_list = gpd.GeoDataFrame(list_points, geometry="geometry", crs="EPSG:4326")
    list_out = out_base / "thueringen_landkreis_number_list_points.geojson"
    g_list.to_file(list_out, driver="GeoJSON")
    print(f"[INFO] Wrote Landkreis right-side list layer -> {list_out.name} ({len(g_list)} points)")

    # mapping json (debug + reuse)
    mapping = {
        slug: {"num": int(slug_to_num[slug]), "name": centers_slug_to_name.get(slug, slug)}
        for slug in slugs
    }
    map_out = out_base / "thueringen_landkreis_number_map.json"
    map_out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] Wrote Landkreis number mapping -> {map_out.name}")


def main():
    print("\n[step2_5] Building Thüringen yearly Landkreis pie INPUTS (polygon fallback + center canonical filter).")

    OUT_BASE.mkdir(parents=True, exist_ok=True)

    if not INPUT_ROOT.exists():
        raise RuntimeError(f"INPUT_ROOT not found: {INPUT_ROOT}")

    centers, slug_to_name = load_thueringen_centers()
    print(f"[CENTERS] Loaded {len(centers)} Thüringen Landkreis centers from {CENTERS_PATH}")

    lk_poly = load_thueringen_landkreis_polygons()

    # ---- Landkreis numbering system (like step1_3 but for Thüringen Landkreise) ----
    # Numbers inside polygons + right-side list (to the right of Thüringen map)
    build_landkreis_numbering_layers(
        lk_poly=lk_poly,
        centers_slug_to_name=slug_to_name,
        out_base=OUT_BASE,
        list_x=13.1,      # right side (coarse) - adjust in QGIS
        list_top_y=51.7,  # top of list (coarse)
        list_step_y=-0.065 # row spacing
    )


    geojson_paths = list(scan_geojsons(INPUT_ROOT))
    if not geojson_paths:
        raise RuntimeError(f"No GeoJSON files found under {INPUT_ROOT}")

    frames: List[gpd.GeoDataFrame] = []

    # ---- Parse Thüringen GeoJSONs into one table ----
    for p in geojson_paths:
        try:
            g = gpd.read_file(p)
            if g.empty or "geometry" not in g.columns:
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

    # ---- Aggregate per (kreis_slug, year-bin) into pie input points ----
    per_bin_rows: Dict[str, List[dict]] = {}
    global_totals: List[float] = []

    for (yslug, kreis_slug), grp in gdf.groupby(["year_bin_slug", "kreis_slug"], dropna=False):
        label = str(grp["year_bin_label"].iloc[0])

        parts = {f: 0.0 for f in PRIORITY_FIELDNAMES.values()}
        others = 0.0

        for _, r in grp.iterrows():
            cat = r["energy_norm"]
            pkw = float(r["_power"])
            if cat in PRIORITY_FIELDNAMES:
                parts[PRIORITY_FIELDNAMES[cat]] += pkw
            else:
                others += pkw

        parts[OTHERS_FIELD] = others
        parts["total_kw"] = float(sum(parts.values()))

        cx, cy = centers[kreis_slug]

        row = {
            "state_name": STATE_NAME,
            "state_slug": STATE_SLUG,
            "state_number": STATE_NUMBER,

            # IMPORTANT: write BOTH keys to avoid later schema mismatches
            "kreis_slug": kreis_slug,
            "kreis_key": kreis_slug,   # for step2_6 compatibility
            "kreis_name": slug_to_name.get(kreis_slug, kreis_slug),

            "year_bin_slug": yslug,
            "year_bin_label": label,
            "_x": float(cx),
            "_y": float(cy),
            **parts,
        }

        per_bin_rows.setdefault(yslug, []).append(row)
        global_totals.append(parts["total_kw"])

    # ---- Global sizing meta ----
    if global_totals:
        gmin = float(min(global_totals))
        gmax = float(max(global_totals))
        GLOBAL_META.write_text(
            json.dumps({"min_total_kw": gmin, "max_total_kw": gmax}, indent=2),
            encoding="utf-8",
        )
        print(
            f"[GLOBAL SCALE] Thüringen landkreis pies: min={gmin:,.2f} kW, max={gmax:,.2f} kW -> {GLOBAL_META.name}"
        )

    # ---- Write per-bin input points ----
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
        print(f"[BIN INPUT] wrote {out_path.name} (features={len(out_gdf)})")

    # ---- Thüringen totals per year-bin (cumulative) + stacked row chart ----
    PART_FIELDS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]

    # 1) Per-bin (non-cumulative) totals
    per_bin_energy: Dict[str, dict] = {}
    for slug, _, *_ in YEAR_BINS:
        rows = per_bin_rows.get(slug, [])
        if not rows:
            continue
        sums = {f: 0.0 for f in PART_FIELDS}
        for r in rows:
            for f in PART_FIELDS:
                sums[f] += float(r.get(f, 0.0) or 0.0)
        per_bin_energy[slug] = sums

    # 2) Convert to cumulative
    yearly_totals = []
    bin_energy_totals = {}
    cumulative = {f: 0.0 for f in PART_FIELDS}

    for slug, _, *_ in YEAR_BINS:
        if slug not in per_bin_energy:
            continue
        for f in PART_FIELDS:
            cumulative[f] += float(per_bin_energy[slug].get(f, 0.0) or 0.0)

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
        totals_json = OUT_BASE / "thueringen_landkreis_yearly_totals.json"
        totals_json.write_text(
            json.dumps(yearly_totals, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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

        # Title point (for QGIS label rule)
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

        # Headings (coarse)
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
        chart_path = OUT_BASE / "thueringen_landkreis_yearly_totals_chart.geojson"
        chart_gdf.to_file(chart_path, driver="GeoJSON")
        print(f"[INFO] Wrote Thüringen landkreis cumulative ROW chart -> {chart_path.name} ({len(chart_gdf)} features)")

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
