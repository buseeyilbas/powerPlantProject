# Filename: step0_make_thueringen_landkreis_centers.py
# Purpose:
#   Create center points for ALL Thüringen Landkreise (GADM Level-2 polygons).
#   These centers will be used as fixed anchors for future Thüringen Landkreis piecharts.
#
# Output:
#   ...\data\geojson\pieCharts\thueringen_landkreis_centers\thueringen_landkreis_centers.geojson
#
# Notes:
# - Mirrors the style/logic of your landkreis center script:
#   metric CRS -> representative point -> if too close to border, shift inward by buffering.
# - All comments and filenames are in English (per your preference).

from pathlib import Path
import re
import unicodedata

import geopandas as gpd
from shapely.geometry import Point

# ================= CONFIG =================

DEBUG_PRINT = True

CRS_INPUT = "EPSG:4326"
CRS_METRIC = "EPSG:3035"
CRS_OUTPUT = "EPSG:4326"

# Inward shifting parameters (meters)
STEP_M = 3500.0
MAX_LOCAL_ITER = 50

# If the initial representative point is closer than this distance to the boundary -> shift inward
BORDER_THRESHOLD_M = 6000.0

# ---------- PATHS ----------
GADM_L2_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
)

OUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_landkreis_centers"
)
OUT_PATH = OUT_DIR / "thueringen_landkreis_centers.geojson"

# ---------- GADM FIELD NAMES ----------
STATE_FIELD = "NAME_1"
LK_FIELD = "NAME_2"
# Optional IDs (if present)
ID_FIELDS = ("GID_1", "GID_2", "HASC_2")

# Thüringen matching (accept common spellings)
THUERINGEN_ALIASES = {"thueringen", "thuringen", "thuringia"}


# ================= HELPERS =================

def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def is_thueringen_state(value) -> bool:
    n = norm(value)
    if n in THUERINGEN_ALIASES:
        return True
    return "thueringen" in n or "thuring" in n


def safe_name(value, fallback="unknown") -> str:
    s = str(value).strip() if value is not None else ""
    return s if s else fallback


def shift_inward(poly_m):
    """
    Repeatedly buffer inward and return a representative point of the shrunken polygon.
    Falls back to representative_point if buffering collapses geometry.
    """
    buf = poly_m
    for _ in range(MAX_LOCAL_ITER):
        buf = buf.buffer(-STEP_M)
        if buf.is_empty:
            break
        pt = buf.representative_point()
        if pt.within(poly_m):
            return pt
    return poly_m.representative_point()


def main():
    print("\n[step0] Building Thüringen Landkreis centers from GADM L2")

    if not GADM_L2_PATH.exists():
        raise RuntimeError(f"GADM L2 file not found: {GADM_L2_PATH}")

    g = gpd.read_file(GADM_L2_PATH)
    if g.crs is None:
        g = g.set_crs(CRS_INPUT, allow_override=True)

    if STATE_FIELD not in g.columns or LK_FIELD not in g.columns:
        raise RuntimeError(
            f"Expected fields missing in GADM L2: required '{STATE_FIELD}', '{LK_FIELD}'. "
            f"Available columns: {list(g.columns)}"
        )

    # Filter only Thüringen landkreise
    mask = g[STATE_FIELD].apply(is_thueringen_state)
    g_th = g[mask].copy()

    if g_th.empty:
        raise RuntimeError(
            "No Thüringen rows found in GADM L2. "
            "Check if NAME_1 contains 'Thüringen' in your gadm41_DEU_2.json."
        )

    # Work in metric CRS for distances/buffering
    g_th_m = g_th.to_crs(CRS_METRIC).copy()

    out_rows = []
    for _, r in g_th_m.iterrows():
        poly_m = r.geometry
        if poly_m is None or poly_m.is_empty:
            continue

        lk_name = safe_name(r.get(LK_FIELD), fallback="unknown")
        lk_slug = norm(lk_name)

        # Initial representative point (always inside polygon)
        pt_m = poly_m.representative_point()

        # Border proximity check
        dist_to_border = pt_m.distance(poly_m.boundary)
        if dist_to_border < BORDER_THRESHOLD_M:
            pt_m = shift_inward(poly_m)

        props = {
            "state_name": "Thüringen",
            "state_slug": "thueringen",
            "landkreis_name": lk_name,
            "landkreis_slug": lk_slug,
        }

        # Attach optional IDs if they exist
        for fid in ID_FIELDS:
            if fid in g_th_m.columns:
                props[fid.lower()] = safe_name(r.get(fid), fallback="")

        out_rows.append({**props, "geometry": Point(pt_m.x, pt_m.y)})

    if not out_rows:
        raise RuntimeError("No centers produced (all geometries empty?).")

    out_gdf = gpd.GeoDataFrame(out_rows, geometry="geometry", crs=CRS_METRIC).to_crs(CRS_OUTPUT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_gdf.to_file(OUT_PATH, driver="GeoJSON")

    print(f"[OK] Wrote {OUT_PATH}")
    print(f"[COUNT] Thüringen Landkreise centers: {len(out_gdf)}")

    if DEBUG_PRINT:
        # Print a quick preview
        preview = out_gdf[["landkreis_name", "landkreis_slug"]].head(10)
        print("[PREVIEW] First 10 landkreise:")
        for _, row in preview.iterrows():
            print(f" - {row['landkreis_name']} -> {row['landkreis_slug']}")


if __name__ == "__main__":
    main()
