# Filename: step2_4_make_statewise_landkreis_pie_geometries_yearly.py
# PURPOSE: TRUE STATEWISE SIZING (ALL YEARS, AGS-based)
#
#   Input:
#       - BASE_DIR/<bin_slug>/de_landkreis_pies_<bin_slug>.geojson
#       - BASE_DIR/_STATEWISE_size_meta.json
#
#   Output:
#       - <bin_dir>/de_landkreis_pie_<bin_slug>.geojson          (all states, debug)
#       - BASE_DIR/de_<state_slug>_landkreis_pie_<bin_slug>.geojson   (per-state)

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
R_MIN_M = 10000.0
R_MAX_M = 35000.0

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
                {
                    "energy_key": k,
                    "share": share,
                    "poly_m": poly,
                    "order_id": order_id,
                }
            )
        shares.append((k, share))
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

    # extra safety: group again (state_slug, kreis_key, year_bin_slug)
    group_cols = ["state_slug", "kreis_key", "year_bin_slug", "year_bin_label"]
    grouped_rows = []
    for key, sub in g_raw.groupby(group_cols, dropna=False):
        st, kreis, yslug, ylbl = key
        geom = sub.geometry.iloc[0]

        parts_sum = {}
        for f in PART_FIELDS:
            if f in sub.columns:
                parts_sum[f] = float(sub[f].fillna(0).sum())
            else:
                parts_sum[f] = 0.0
        total_kw = sum(parts_sum.values())

        row = {
            "state_slug": st,
            "kreis_key": kreis,
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

    global_rows = []
    per_state_rows = {}

    for _, r in g.iterrows():
        state_slug = r.get("state_slug")
        if not state_slug or state_slug not in state_meta:
            print(
                f"  [WARN] Missing state meta for feature: state_slug={state_slug}, kreis={r.get('kreis_key','')}"
            )
            continue

        meta = state_meta[state_slug]
        vmin = float(meta["min_total_kw"])
        vmax = float(meta["max_total_kw"])

        cx = float(r.geometry.x)
        cy = float(r.geometry.y)
        mx, my = to_m.transform(cx, cy)

        total_kw = float(r.get("total_kw", 0.0))
        radius_m = scale_linear(total_kw, vmin, vmax, R_MIN_M, R_MAX_M)

        if vmax > vmin:
            raw_scale = (total_kw - vmin) / (vmax - vmin)
            scale = max(0.0, min(1.0, raw_scale))
        else:
            scale = 0.5

        print(
            f"    - {state_slug:12s} | {r.get('kreis_key',''):12s} "
            f"total_kw={total_kw:12,.1f} kW → radius={radius_m:10,.1f} m (scale={scale:.3f})"
        )

        parts = [(f, float(r.get(f, 0.0) or 0.0)) for f in PART_FIELDS]
        slices_m, anchor_key = make_pie((mx, my), radius_m, parts)

        for s in slices_m:
            key = s["energy_key"]
            share = s["share"]
            poly_m = s["poly_m"]
            order_id = s["order_id"]

            coords_deg = [to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords]
            poly_deg = Polygon(coords_deg)
            rRGB, gRGB, bRGB = COLORS[key]

            row = {
                "name": r.get("kreis_key", ""),
                "state_slug": state_slug,
                "energy_type": key,
                "power_kw": float(dict(parts).get(key, 0.0)),
                "share": float(share),
                "total_kw": total_kw,
                "radius_m": float(radius_m),
                "order_id": int(order_id),
                "label_anchor": 1 if (anchor_key == key) else 0,
                "year_bin": r.get("year_bin_label", ""),
                "year_bin_slug": r.get("year_bin_slug", ""),
                "color_r": rRGB,
                "color_g": gRGB,
                "color_b": bRGB,
                "geometry": poly_deg,
            }

            global_rows.append(row)
            per_state_rows.setdefault(state_slug, []).append(row)

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
        print(
            f"      [OK] wrote per-state pies: {st_outfile} (features={len(st_gdf)})"
        )


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
