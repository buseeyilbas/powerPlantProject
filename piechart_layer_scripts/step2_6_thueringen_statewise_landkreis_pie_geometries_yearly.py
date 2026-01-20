# Filename: step2_6_thueringen_statewise_landkreis_pie_geometries_yearly.py
# Purpose:
#   Thüringen-only version of step2_4_make_statewise_landkreis_pie_geometries_yearly.py
#   - Reads Thüringen landkreis pie INPUT points (from your Thüringen-only step2_5 output)
#   - Uses THUERINGEN global sizing meta (or per-bin meta if you prefer)
#   - Writes per-bin Thüringen pie polygons into each bin folder
#
# Notes:
# - This mirrors the structure of step1_6 (Thüringen state pies) and step2_4 (DE landkreis pies).
# - Centers are already fixed in the input (points), so we don't do repulsion.

from pathlib import Path
import math
import json

import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer


# ------------------------------ PATHS ------------------------------
BASE_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_statewise_landkreis_pies_yearly"
)

# Input files are expected at: BASE_DIR/<bin_slug>/thueringen_landkreis_pies_<bin_slug>.geojson
# Output files will be written to: BASE_DIR/<bin_slug>/thueringen_landkreis_pie_<bin_slug>.geojson
IN_DIR = BASE_DIR
OUT_DIR = BASE_DIR

GLOBAL_META = BASE_DIR / "_THUERINGEN_GLOBAL_style_meta.json"


# ------------------------------ YEAR BINS ------------------------------
YEAR_BINS = [
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


# ------------------------------ SIZING ------------------------------
R_MIN_M = 9000.0
R_MAX_M = 20000.0

# Optional: if Thüringen is too dense, lower R_MAX_M (e.g., 30000) or increase this:
GAP_M = 2200.0
MAX_NUDGE_ITER = 120
CENTERS_ARE_FIXED = True


# ------------------------------ COLORS / PARTS ------------------------------
COLORS = {
    "pv_kw": (255, 255, 0),
    "battery_kw": (148, 87, 235),
    "wind_kw": (173, 216, 230),
    "hydro_kw": (0, 0, 255),
    "biogas_kw": (0, 190, 0),
    "others_kw": (158, 158, 158),
}

PART_FIELDS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]


# ------------------------------ HELPERS ------------------------------
def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:
        return (omin + omax) / 2.0
    t = max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))
    return omin + t * (omax - omin)


def ring_pts(cxy, r, th1, th2, n=48):
    cx, cy = cxy
    dth = th2 - th1
    return [
        (cx + r * math.cos(th1 + dth * i / n), cy + r * math.sin(th1 + dth * i / n))
        for i in range(n + 1)
    ]


def make_pie(center_m, radius_m, ordered_pairs):
    total = sum(v for _, v in ordered_pairs if v and v > 0)
    if total <= 0:
        return [], None

    slices = []
    shares = []
    ang = 0.0
    order_id = 0

    for k, v in ordered_pairs:
        share = (v / total) if v and v > 0 else 0.0
        dth = share * 2 * math.pi
        t1, t2 = ang, ang + dth
        ang = t2

        if share > 0:
            arc = ring_pts(center_m, radius_m, t1, t2)
            poly = Polygon([center_m] + arc + [center_m])
            slices.append(
                {"energy_key": k, "share": share, "poly_m": poly, "order_id": order_id}
            )
        shares.append((k, share))
        order_id += 1

    anchor_key = max(shares, key=lambda kv: kv[1])[0] if shares else None
    return slices, anchor_key


def repulse_centers(centers):
    # kept for parity with step2_4; not used if CENTERS_ARE_FIXED=True
    for _ in range(MAX_NUDGE_ITER):
        moved = False
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                pi, pj = centers[i], centers[j]
                dx, dy = pj["x"] - pi["x"], pj["y"] - pi["y"]
                d = math.hypot(dx, dy)
                need = pi["r"] + pj["r"] + GAP_M
                if d == 0.0:
                    ang = (i + 1) * 2 * math.pi / (len(centers) + 1)
                    dx, dy, d = math.cos(ang), math.sin(ang), 1.0
                if d < need:
                    push = (need - d) / 2.0
                    ux, uy = dx / d, dy / d
                    pi["x"] -= ux * push
                    pi["y"] -= uy * push
                    pj["x"] += ux * push
                    pj["y"] += uy * push
                    moved = True
        if not moved:
            break


def process_one_bin(bin_slug: str, vmin: float, vmax: float):
    bin_dir = IN_DIR / bin_slug
    infile = bin_dir / f"thueringen_landkreis_pies_{bin_slug}.geojson"
    if not infile.exists():
        print(f"[SKIP] bin '{bin_slug}': input not found: {infile.name}")
        return

    g_raw = gpd.read_file(infile)
    # --- Backward/forward compatibility for Landkreis key column ---
    # Older pipeline uses: kreis_key
    # New Thüringen pipeline uses: kreis_slug (or sometimes landkreis_slug)
    if "kreis_key" not in g_raw.columns:
        if "kreis_slug" in g_raw.columns:
            g_raw["kreis_key"] = g_raw["kreis_slug"].astype(str)
        elif "landkreis_slug" in g_raw.columns:
            g_raw["kreis_key"] = g_raw["landkreis_slug"].astype(str)
        else:
            raise KeyError(
                "Missing Landkreis identifier column. Expected 'kreis_key' or 'kreis_slug' or 'landkreis_slug'."
            )


    if g_raw.empty:
        print(f"[SKIP] bin '{bin_slug}': input is empty.")
        return

    if g_raw.crs is None or g_raw.crs.to_epsg() != 4326:
        g_raw = g_raw.set_crs("EPSG:4326", allow_override=True)

    # Safety regroup (kreis_key, year_bin_slug)
    group_cols = ["kreis_key", "year_bin_slug", "year_bin_label"]
    grouped_rows = []
    for key, sub in g_raw.groupby(group_cols, dropna=False):
        kreis, yslug, ylbl = key
        geom = sub.geometry.iloc[0]

        parts_sum = {}
        for f in PART_FIELDS:
            parts_sum[f] = float(sub[f].fillna(0).sum()) if f in sub.columns else 0.0
        total_kw = sum(parts_sum.values())

        row = {
            "kreis_key": kreis,
            "kreis_name": sub["kreis_name"].iloc[0] if "kreis_name" in sub.columns else str(kreis),
            "year_bin_slug": yslug,
            "year_bin_label": ylbl,
            "geometry": geom,
            "total_kw": total_kw,
        }
        row.update(parts_sum)
        grouped_rows.append(row)


    g = gpd.GeoDataFrame(grouped_rows, geometry="geometry", crs=g_raw.crs)
    print(f"\n[BIN] {bin_slug}  (raw={len(g_raw)}, grouped={len(g)})")

    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    centers = []
    rows = []
    for _, r in g.iterrows():
        cx = float(r.geometry.x)
        cy = float(r.geometry.y)
        mx, my = to_m.transform(cx, cy)

        total_kw = float(r.get("total_kw", 0.0))
        if total_kw <= 0:
            continue

        radius_m = scale_linear(total_kw, vmin, vmax, R_MIN_M, R_MAX_M)


        centers.append({"x": mx, "y": my, "r": radius_m})
        rows.append(r)

    if not CENTERS_ARE_FIXED:
        repulse_centers(centers)

    out_rows = []
    for r, c in zip(rows, centers):
        total_kw = float(r.get("total_kw", 0.0))
        radius_m = float(c["r"])

        parts = [(f, float(r.get(f, 0.0) or 0.0)) for f in PART_FIELDS]
        slices_m, anchor_key = make_pie((c["x"], c["y"]), radius_m, parts)

        for s in slices_m:
            key = s["energy_key"]
            share = float(s["share"])
            poly_m = s["poly_m"]
            order_id = int(s["order_id"])

            coords_deg = [to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords]
            poly_deg = Polygon(coords_deg)

            rRGB, gRGB, bRGB = COLORS[key]
            out_rows.append(
                {
                    "name": r.get("kreis_name", r.get("kreis_key", "")),
                    "kreis_name": r.get("kreis_name", ""),
                    "kreis_key": r.get("kreis_key", ""),
                    "energy_type": key,
                    "power_kw": float(dict(parts).get(key, 0.0)),
                    "share": share,
                    "total_kw": total_kw,
                    "radius_m": radius_m,
                    "order_id": order_id,
                    "label_anchor": 1 if (anchor_key == key) else 0,
                    "year_bin": r.get("year_bin_label", ""),
                    "year_bin_slug": r.get("year_bin_slug", ""),
                    "color_r": rRGB,
                    "color_g": gRGB,
                    "color_b": bRGB,
                    "geometry": poly_deg,
                }
            )

    if not out_rows:
        print(f"  [WARN] No pies created for bin '{bin_slug}'")
        return

    out_gdf = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    outfile = bin_dir / f"thueringen_landkreis_pie_{bin_slug}.geojson"
    out_gdf.to_file(outfile, driver="GeoJSON")
    print(f"  [OK] wrote {outfile.name} (features={len(out_gdf)})")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not GLOBAL_META.exists():
        print(f"ERROR: {GLOBAL_META.name} not found. Run the Thüringen landkreis inputs step first.")
        return

    gm = json.loads(GLOBAL_META.read_text(encoding="utf-8"))
    vmin = float(gm["min_total_kw"])
    vmax = float(gm["max_total_kw"])

    print("[INFO] step2_6: building Thüringen landkreis pies (single-state sizing).")
    print(f"[INFO] Using GLOBAL sizing: vmin={vmin:,.2f} kW, vmax={vmax:,.2f} kW")

    for bin_slug in YEAR_BINS:
        process_one_bin(bin_slug, vmin, vmax)

    print("\n[DONE] step2_6 complete.")


if __name__ == "__main__":
    main()
