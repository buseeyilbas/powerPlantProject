# Filename: step2_4_make_statewise_landkreis_pie_geometries_yearly.py
# PURPOSE: TRUE STATEWISE SIZING (ALL YEARS, AGS-based)
#
# Input:
#   - BASE_DIR/<bin_slug>/de_landkreis_pies_<bin_slug>.geojson
#   - BASE_DIR/_STATEWISE_size_meta.json
#
# Output:
#   - <bin_dir>/de_landkreis_pie_<bin_slug>.geojson
#   - BASE_DIR/de_<state_slug>_landkreis_pie_<bin_slug>.geojson
#
# Notes:
#   - Keeps the user-defined landkreis radius range unchanged.
#   - Works with the updated step2_3 schema (including optional state_abbrev).
#   - Does not add any map labels by itself; it only writes pie polygons.

from pathlib import Path
import math
import json

import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

# ------------------------------ PATHS ------------------------------
BASE_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies_yearly"
)
IN_DIR = BASE_DIR
OUT_DIR = BASE_DIR

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
# Keep unchanged to stay aligned with the user's manual setup in step2_3.
R_MIN_M = 5000.0
R_MAX_M = 30000.0

COLORS = {
    "pv_kw": (255, 255, 0),
    "battery_kw": (148, 87, 235),
    "wind_kw": (173, 216, 230),
    "hydro_kw": (0, 0, 255),
    "biogas_kw": (0, 190, 0),
    "others_kw": (158, 158, 158),
}

PART_FIELDS = [
    "pv_kw",
    "wind_kw",
    "hydro_kw",
    "battery_kw",
    "biogas_kw",
    "others_kw",
]


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


def process_one_bin(bin_slug: str, state_meta: dict):
    bin_dir = IN_DIR / bin_slug
    infile = bin_dir / f"de_landkreis_pies_{bin_slug}.geojson"
    if not infile.exists():
        print(f"[SKIP] bin '{bin_slug}': input not found: {infile}")
        return

    g_raw = gpd.read_file(infile)
    if g_raw.empty:
        print(f"[SKIP] bin '{bin_slug}': input is empty.")
        return

    if g_raw.crs is None or g_raw.crs.to_epsg() != 4326:
        g_raw = g_raw.set_crs("EPSG:4326", allow_override=True)

    # Extra safety regroup
    group_cols = ["state_slug", "kreis_key", "year_bin_slug", "year_bin_label"]
    grouped_rows = []

    for key, sub in g_raw.groupby(group_cols, dropna=False):
        state_slug, kreis_key, year_bin_slug, year_bin_label = key
        geom = sub.geometry.iloc[0]

        parts_sum = {}
        for field in PART_FIELDS:
            if field in sub.columns:
                parts_sum[field] = float(sub[field].fillna(0).sum())
            else:
                parts_sum[field] = 0.0

        total_kw = sum(parts_sum.values())

        state_abbrev = ""
        if "state_abbrev" in sub.columns:
            state_abbrev = str(sub["state_abbrev"].iloc[0] or "").strip()

        row = {
            "state_slug": state_slug,
            "state_abbrev": state_abbrev,
            "kreis_key": kreis_key,
            "year_bin_slug": year_bin_slug,
            "year_bin_label": year_bin_label,
            "geometry": geom,
            "total_kw": total_kw,
        }
        row.update(parts_sum)
        grouped_rows.append(row)

    g = gpd.GeoDataFrame(grouped_rows, geometry="geometry", crs=g_raw.crs)
    print(f"\n[BIN] {bin_slug}  (raw={len(g_raw)}, grouped={len(g)})")

    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    global_rows = []
    per_state_rows = {}

    for _, row in g.iterrows():
        state_slug = row.get("state_slug")
        if not state_slug or state_slug not in state_meta:
            print(
                f"  [WARN] Missing state meta for feature: state_slug={state_slug}, kreis={row.get('kreis_key', '')}"
            )
            continue

        meta = state_meta[state_slug]
        vmin = float(meta["min_total_kw"])
        vmax = float(meta["max_total_kw"])

        cx = float(row.geometry.x)
        cy = float(row.geometry.y)
        mx, my = to_m.transform(cx, cy)

        total_kw = float(row.get("total_kw", 0.0) or 0.0)
        radius_m = scale_linear(total_kw, vmin, vmax, R_MIN_M, R_MAX_M)

        if vmax > vmin:
            raw_scale = (total_kw - vmin) / (vmax - vmin)
            scale = max(0.0, min(1.0, raw_scale))
        else:
            scale = 0.5

        print(
            f"    - {state_slug:20s} | {row.get('kreis_key', ''):12s} "
            f"total_kw={total_kw:12,.1f} kW → radius={radius_m:10,.1f} m (scale={scale:.3f})"
        )

        parts = [(field, float(row.get(field, 0.0) or 0.0)) for field in PART_FIELDS]
        slices_m, anchor_key = make_pie((mx, my), radius_m, parts)
        state_abbrev = str(row.get("state_abbrev", "") or "").strip()

        for s in slices_m:
            key = s["energy_key"]
            share = s["share"]
            poly_m = s["poly_m"]
            order_id = s["order_id"]

            coords_deg = [to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords]
            poly_deg = Polygon(coords_deg)
            red, green, blue = COLORS[key]

            part_power_kw = float(dict(parts).get(key, 0.0) or 0.0)

            out_row = {
                "name": row.get("kreis_key", ""),
                "state_slug": state_slug,
                "state_abbrev": state_abbrev,
                "energy_type": key,
                "power_kw": part_power_kw,
                "power_gw": part_power_kw / 1_000_000.0,
                "total_kw": total_kw,
                "total_gw": total_kw / 1_000_000.0,
                "share": float(share),
                "radius_m": float(radius_m),
                "order_id": int(order_id),
                "label_anchor": 1 if (anchor_key == key) else 0,
                "year_bin": row.get("year_bin_label", ""),
                "year_bin_slug": row.get("year_bin_slug", ""),
                "color_r": red,
                "color_g": green,
                "color_b": blue,
                "geometry": poly_deg,
            }

            global_rows.append(out_row)
            per_state_rows.setdefault(state_slug, []).append(out_row)

    if not global_rows:
        print(f"  [WARN] No pies created for bin '{bin_slug}'")
        return

    out_gdf = gpd.GeoDataFrame(global_rows, geometry="geometry", crs="EPSG:4326")
    outfile = bin_dir / f"de_landkreis_pie_{bin_slug}.geojson"
    out_gdf.to_file(outfile, driver="GeoJSON")
    print(f"  [OK] wrote {outfile} (features={len(out_gdf)})")

    for state_slug, rows in per_state_rows.items():
        st_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
        st_outfile = OUT_DIR / f"de_{state_slug}_landkreis_pie_{bin_slug}.geojson"
        st_gdf.to_file(st_outfile, driver="GeoJSON")
        print(f"      [OK] wrote per-state pies: {st_outfile} (features={len(st_gdf)})")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    meta_path = BASE_DIR / "_STATEWISE_size_meta.json"
    if not meta_path.exists():
        print("ERROR: _STATEWISE_size_meta.json not found. Run step2_3 first.")
        return

    state_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    print("[INFO] step2_4: building landkreis pies with TRUE STATEWISE sizing.")
    print(f"[INFO] States found in meta: {', '.join(sorted(state_meta.keys()))}")

    for bin_slug in YEAR_BINS:
        process_one_bin(bin_slug, state_meta)

    print("\n[DONE] step2_4 complete.")


if __name__ == "__main__":
    main()