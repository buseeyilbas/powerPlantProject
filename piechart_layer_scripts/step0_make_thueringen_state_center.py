# Filename: step0_make_thueringen_state_center.py
# Purpose:
#   Build an authoritative Thüringen state center using GADM Level-1 polygon.
#   The output is a single Point feature inside the Thüringen polygon, shifted inward
#   if it is too close to the border (for nicer pie-chart placement).
#
# Output:
#   ...\data\geojson\pieCharts\thueringen_state_pies\thueringen_state_pies.geojson
#
# Notes:
# - This mirrors the style of step0_for2and3_make_landkreis_centers.py (metric CRS + inward shifting).
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
STEP_M = 4500.0
MAX_LOCAL_ITER = 50

# If center is closer than this distance to polygon boundary -> shift inward
BORDER_THRESHOLD_M = 7000.0

# ---------- PATHS ----------
GADM_L1_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_1.json"
)

OUT_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_state_pies"
)
OUT_PATH = OUT_DIR / "thueringen_state_pies.geojson"

# If GADM has multiple name fields, we will try these
NAME_FIELDS = ("NAME_1", "VARNAME_1", "NL_NAME_1", "ENGTYPE_1", "TYPE_1")


# ================= HELPERS =================

def norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def is_thueringen_row(row) -> bool:
    # Accept common variants
    candidates = []
    for k in NAME_FIELDS:
        if k in row and row[k]:
            candidates.append(str(row[k]))
    text = " ".join(candidates)
    n = norm(text)
    return n in {"thueringen", "thuringen", "thuringia"} or "thueringen" in n or "thuring" in n


def shift_inward(poly_m):
    """
    Repeatedly buffer inward and return a representative point of the shrunken polygon.
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


# ================= MAIN =================

def main():
    print("\n[step0] Building Thüringen state center from GADM L1 polygon")

    if not GADM_L1_PATH.exists():
        raise RuntimeError(f"GADM L1 file not found: {GADM_L1_PATH}")

    g = gpd.read_file(GADM_L1_PATH)
    if g.crs is None:
        g = g.set_crs(CRS_INPUT, allow_override=True)

    # Filter Thüringen polygon
    mask = g.apply(is_thueringen_row, axis=1)
    g_th = g[mask].copy()

    if g_th.empty:
        # As a fallback, try a direct match on NAME_1 if present
        if "NAME_1" in g.columns:
            g_th = g[g["NAME_1"].astype(str).str.contains("Th", case=False, na=False)].copy()

    if g_th.empty:
        raise RuntimeError("Could not find Thüringen in GADM L1. Check the attribute fields in gadm41_DEU_1.json.")

    # If multiple matches (rare), take the largest area in metric CRS
    g_th_m = g_th.to_crs(CRS_METRIC)
    g_th_m["area"] = g_th_m.geometry.area
    g_th_m = g_th_m.sort_values("area", ascending=False).head(1)

    poly_m = g_th_m.geometry.iloc[0]

    # Start with representative point
    pt_m = poly_m.representative_point()

    # Border proximity check
    dist_to_border = pt_m.distance(poly_m.boundary)
    if dist_to_border < BORDER_THRESHOLD_M:
        if DEBUG_PRINT:
            print(f"[BORDER PULL] dist_to_border={int(dist_to_border)} m < {int(BORDER_THRESHOLD_M)} m, shifting inward...")
        pt_m = shift_inward(poly_m)

    # Back to EPSG:4326
    pt_gdf = gpd.GeoDataFrame(
        [
            {
                "state_name": "Thüringen",
                "state_slug": "thueringen",
                "state_number": 16,
                "geometry": Point(pt_m.x, pt_m.y),
            }
        ],
        geometry="geometry",
        crs=CRS_METRIC,
    ).to_crs(CRS_OUTPUT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pt_gdf.to_file(OUT_PATH, driver="GeoJSON")

    print(f"[OK] Wrote {OUT_PATH} (1 center point)")
    if DEBUG_PRINT:
        p = pt_gdf.geometry.iloc[0]
        print(f"[CENTER EPSG:4326] lon={p.x:.6f}, lat={p.y:.6f}")


if __name__ == "__main__":
    main()
