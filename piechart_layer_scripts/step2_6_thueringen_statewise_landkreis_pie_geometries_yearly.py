# Filename: step2_6_thueringen_statewise_landkreis_pie_geometries_yearly.py
# Purpose:
#   Thüringen-only version of step2_4_make_statewise_landkreis_pie_geometries_yearly.py
#   - Reads Thüringen landkreis pie INPUT points (from step2_5 output)
#   - Uses THUERINGEN global sizing meta
#   - Writes per-bin Thüringen pie polygons into each bin folder
#
# Notes:
# - Centers are already fixed in the input points, so no repulsion is applied.
# - Radius range is intentionally kept at the user-adjusted values.
# - This file only builds pie geometries. It does not create legends, charts, or labels.

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
# Keep these exactly aligned with the user-adjusted legend sizing in step2_5.
R_MIN_M = 9000.0
R_MAX_M = 20000.0

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


def ring_pts(center_xy, radius_m, theta_1, theta_2, n=48):
    cx, cy = center_xy
    delta_theta = theta_2 - theta_1
    return [
        (
            cx + radius_m * math.cos(theta_1 + delta_theta * i / n),
            cy + radius_m * math.sin(theta_1 + delta_theta * i / n),
        )
        for i in range(n + 1)
    ]


def make_pie(center_m, radius_m, ordered_pairs):
    total = sum(v for _, v in ordered_pairs if v and v > 0)
    if total <= 0:
        return [], None

    slices = []
    shares = []
    angle = 0.0
    order_id = 0

    for key, value in ordered_pairs:
        share = (value / total) if value and value > 0 else 0.0
        delta_theta = share * 2.0 * math.pi
        theta_1, theta_2 = angle, angle + delta_theta
        angle = theta_2

        if share > 0:
            arc = ring_pts(center_m, radius_m, theta_1, theta_2)
            poly = Polygon([center_m] + arc + [center_m])
            slices.append(
                {
                    "energy_key": key,
                    "share": share,
                    "poly_m": poly,
                    "order_id": order_id,
                }
            )

        shares.append((key, share))
        order_id += 1

    anchor_key = max(shares, key=lambda kv: kv[1])[0] if shares else None
    return slices, anchor_key


def repulse_centers(centers):
    # Kept for parity with other geometry scripts; not used when CENTERS_ARE_FIXED=True.
    for _ in range(MAX_NUDGE_ITER):
        moved = False
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                pi, pj = centers[i], centers[j]
                dx, dy = pj["x"] - pi["x"], pj["y"] - pi["y"]
                dist = math.hypot(dx, dy)
                need = pi["r"] + pj["r"] + GAP_M

                if dist == 0.0:
                    angle = (i + 1) * 2.0 * math.pi / (len(centers) + 1)
                    dx, dy, dist = math.cos(angle), math.sin(angle), 1.0

                if dist < need:
                    push = (need - dist) / 2.0
                    ux, uy = dx / dist, dy / dist
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

    # Backward / forward compatibility for Landkreis key field
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

    # Safety regroup
    group_cols = ["kreis_key", "year_bin_slug", "year_bin_label"]
    grouped_rows = []

    for key, sub in g_raw.groupby(group_cols, dropna=False):
        kreis_key, yslug, ylbl = key
        geom = sub.geometry.iloc[0]

        parts_sum = {}
        for f in PART_FIELDS:
            parts_sum[f] = float(sub[f].fillna(0).sum()) if f in sub.columns else 0.0
        total_kw = sum(parts_sum.values())

        row = {
            "kreis_key": kreis_key,
            "kreis_slug": sub["kreis_slug"].iloc[0] if "kreis_slug" in sub.columns else str(kreis_key),
            "kreis_name": sub["kreis_name"].iloc[0] if "kreis_name" in sub.columns else str(kreis_key),
            "kreis_number": int(sub["kreis_number"].iloc[0]) if "kreis_number" in sub.columns and str(sub["kreis_number"].iloc[0]).strip() else 0,
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

    for _, row in g.iterrows():
        cx = float(row.geometry.x)
        cy = float(row.geometry.y)
        mx, my = to_m.transform(cx, cy)

        total_kw = float(row.get("total_kw", 0.0) or 0.0)
        if total_kw <= 0:
            continue

        radius_m = scale_linear(total_kw, vmin, vmax, R_MIN_M, R_MAX_M)

        centers.append({"x": mx, "y": my, "r": radius_m})
        rows.append(row)

    if not CENTERS_ARE_FIXED:
        repulse_centers(centers)

    out_rows = []

    for row, center in zip(rows, centers):
        total_kw = float(row.get("total_kw", 0.0) or 0.0)
        radius_m = float(center["r"])

        parts = [(f, float(row.get(f, 0.0) or 0.0)) for f in PART_FIELDS]
        slices_m, anchor_key = make_pie((center["x"], center["y"]), radius_m, parts)

        for s in slices_m:
            key = s["energy_key"]
            share = float(s["share"])
            poly_m = s["poly_m"]
            order_id = int(s["order_id"])

            coords_deg = [to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords]
            poly_deg = Polygon(coords_deg)

            red, green, blue = COLORS[key]

            out_rows.append(
                {
                    "name": row.get("kreis_name", row.get("kreis_key", "")),
                    "kreis_name": row.get("kreis_name", ""),
                    "kreis_key": row.get("kreis_key", ""),
                    "kreis_slug": row.get("kreis_slug", ""),
                    "kreis_number": int(row.get("kreis_number", 0) or 0),
                    "energy_type": key,
                    "power_kw": float(dict(parts).get(key, 0.0)),
                    "power_mw": float(dict(parts).get(key, 0.0)) / 1000.0,
                    "share": share,
                    "total_kw": total_kw,
                    "total_mw": total_kw / 1000.0,
                    "radius_m": radius_m,
                    "order_id": order_id,
                    "label_anchor": 1 if (anchor_key == key) else 0,
                    "year_bin": row.get("year_bin_label", ""),
                    "year_bin_slug": row.get("year_bin_slug", ""),
                    "color_r": red,
                    "color_g": green,
                    "color_b": blue,
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
        print(f"ERROR: {GLOBAL_META.name} not found. Run step2_5 first.")
        return

    gm = json.loads(GLOBAL_META.read_text(encoding="utf-8"))
    vmin = float(gm["min_total_kw"])
    vmax = float(gm["max_total_kw"])

    print("[INFO] step2_6: building Thüringen landkreis pies (single-state sizing).")
    print(f"[INFO] Using GLOBAL sizing: vmin={vmin:,.2f} kW, vmax={vmax:,.2f} kW")
    print(f"[INFO] Radius range: min={R_MIN_M:,.1f} m, max={R_MAX_M:,.1f} m")

    for bin_slug in YEAR_BINS:
        process_one_bin(bin_slug, vmin, vmax)

    print("\n[DONE] step2_6 complete.")


if __name__ == "__main__":
    main()