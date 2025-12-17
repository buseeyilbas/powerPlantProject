# Filename: step3_4_make_landkreis_pie_geometries_yearly.py
# Purpose:
#   Convert step3_3 yearly INPUT POINTS into actual pie-slice POLYGONS.
#   Difference vs step2_4:
#     - SIZING IS NATIONWIDE (GLOBAL): same vmin/vmax for ALL states + ALL bins
#       taken from step3_3 OUT_DIR/_GLOBAL_size_meta.json
#
# Inputs (from step3_3):
#   OUT_DIR/<bin_slug>/de_landkreis_pies_<bin_slug>.geojson                     (ALL Germany)
#   OUT_DIR/<state_slug>/<bin_slug>/de_<state_slug>_landkreis_pies_<bin_slug>.geojson
#   OUT_DIR/_GLOBAL_size_meta.json
#
# Outputs:
#   OUT_DIR/<bin_slug>/de_landkreis_pie_<bin_slug>.geojson                      (ALL Germany)
#   OUT_DIR/<state_slug>/<bin_slug>/de_<state_slug>_landkreis_pie_<bin_slug>.geojson

from pathlib import Path
import math
import json
import os

import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

# ---------------- PATHS ----------------

BASE_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly"
)

GLOBAL_META_PATH = BASE_DIR / "_GLOBAL_size_meta.json"

# ---------------- SIZING (METERS) ----------------
# (Actual min/max total_kw come from GLOBAL_META_PATH)

R_MIN_M = 10000.0
R_MAX_M = 50000.0

# ---------------- OVERLAP AVOIDANCE ----------------

GAP_M = 2000.0
MAX_NUDGE_ITER = 120

# ---------------- PALETTE ----------------

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
    t = (val - vmin) / (vmax - vmin)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return omin + t * (omax - omin)


def ring_pts(cxy, r, th1, th2, n=48):
    cx, cy = cxy
    out = []
    for i in range(n + 1):
        th = th1 + (th2 - th1) * (i / n)
        out.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return out


def make_pie(center_m, radius_m, ordered_pairs):
    total = sum(v for _, v in ordered_pairs if v and v > 0)
    if total <= 0:
        return [], None
    slices = []
    shares = []
    ang = 0.0
    for k, v in ordered_pairs:
        share = (v / total) if v and v > 0 else 0.0
        dth = share * 2 * math.pi
        t1, t2 = ang, ang + dth
        ang = t2
        if share > 0:
            arc = ring_pts(center_m, radius_m, t1, t2)
            poly = Polygon([center_m] + arc + [center_m])
            slices.append((k, share, poly))
        shares.append((k, share))
    anchor_key = max(shares, key=lambda kv: kv[1])[0] if shares else None
    return slices, anchor_key


def repulse_centers(centers):
    for _ in range(MAX_NUDGE_ITER):
        moved = False
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                pi, pj = centers[i], centers[j]
                dx = pj["x"] - pi["x"]
                dy = pj["y"] - pi["y"]
                d = math.hypot(dx, dy)
                need = pi["r"] + pj["r"] + GAP_M
                if d == 0.0:
                    ang = (i + 1) * 2 * math.pi / (len(centers) + 1)
                    dx, dy = math.cos(ang), math.sin(ang)
                    d = 1.0
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


def safe_to_file(gdf: gpd.GeoDataFrame, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        gdf.to_file(out_path, driver="GeoJSON")
        return out_path
    except PermissionError:
        alt = out_path.with_name(out_path.stem + "_NEW" + out_path.suffix)
        gdf.to_file(alt, driver="GeoJSON")
        print(f"[WARN] File locked, wrote instead: {alt.name}")
        print("       Close the layer/file in QGIS/Explorer and rerun to overwrite the original.")
        return alt


def make_pies_for_points(g: gpd.GeoDataFrame, vmin: float, vmax: float, out_path: Path) -> int:
    if g.empty:
        safe_to_file(gpd.GeoDataFrame([], geometry="geometry", crs="EPSG:4326"), out_path)
        return 0

    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.set_crs("EPSG:4326", allow_override=True)

    to_m = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    centers = []
    rows = []
    for _, r in g.iterrows():
        cx, cy = float(r.geometry.x), float(r.geometry.y)
        cxm, cym = to_m.transform(cx, cy)
        total = float(r.get("total_kw", 0.0) or 0.0)
        rad = scale_linear(total, vmin, vmax, R_MIN_M, R_MAX_M)
        centers.append({"x": cxm, "y": cym, "r": rad})
        rows.append(r)

    repulse_centers(centers)

    out_rows = []
    for r, c in zip(rows, centers):
        parts = [(f, float(r.get(f, 0.0) or 0.0)) for f in PART_FIELDS]
        slices_m, anchor_key = make_pie((c["x"], c["y"]), c["r"], parts)

        for k, share, poly_m in slices_m:
            poly_deg = Polygon([to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords])
            rr, gg, bb = COLORS[k]
            out_rows.append(
                {
                    "state_slug": r.get("state_slug", ""),
                    "kreis_key": r.get("kreis_key", ""),
                    "kreis_name": r.get("kreis_name", ""),
                    "year_bin_slug": r.get("year_bin_slug", ""),
                    "year_bin_label": r.get("year_bin_label", ""),
                    "energy_type": k,
                    "power_kw": float(dict(parts).get(k, 0.0)),
                    "share": float(share),
                    "total_kw": float(r.get("total_kw", 0.0) or 0.0),
                    "radius_m": float(c["r"]),
                    "label_anchor": 1 if (anchor_key == k) else 0,
                    "color_r": rr,
                    "color_g": gg,
                    "color_b": bb,
                    "geometry": poly_deg,
                }
            )

    out_gdf = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    safe_to_file(out_gdf, out_path)
    return len(out_gdf)


def iter_bins():
    # bins are directories named like "2017_2018" etc
    for d in sorted(BASE_DIR.iterdir()):
        if d.is_dir() and re.match(r"^(pre_1990|\d{4}_\d{4})$", d.name):
            yield d.name


def main():
    print("\n[step3_4] Building yearly Landkreis pie GEOMETRIES (GLOBAL sizing).")

    if not GLOBAL_META_PATH.exists():
        raise RuntimeError(f"Missing GLOBAL meta: {GLOBAL_META_PATH} (run step3_3 first)")

    meta = json.loads(GLOBAL_META_PATH.read_text(encoding="utf-8"))
    vmin = float(meta.get("min_total_kw", 0.0))
    vmax = float(meta.get("max_total_kw", 1.0))
    if vmax <= vmin:
        vmax = vmin + 1.0

    # keep script constants in sync with meta if present
    global R_MIN_M, R_MAX_M
    R_MIN_M = float(meta.get("r_min_m", R_MIN_M))
    R_MAX_M = float(meta.get("r_max_m", R_MAX_M))

    print(
        f"[GLOBAL SIZING] vmin={vmin:,.1f} kW, vmax={vmax:,.1f} kW  "
        f"(radii: {R_MIN_M:,.0f}..{R_MAX_M:,.0f} m)"
    )

    # Discover bins from input points that step3_3 created:
    bin_dirs = sorted([d for d in BASE_DIR.iterdir() if d.is_dir() and (BASE_DIR / d.name / f"de_landkreis_pies_{d.name}.geojson").exists()])
    if not bin_dirs:
        raise RuntimeError(f"No per-bin inputs found under {BASE_DIR}. Run step3_3 first.")

    for bin_dir in bin_dirs:
        bin_slug = bin_dir.name
        in_all = bin_dir / f"de_landkreis_pies_{bin_slug}.geojson"
        if not in_all.exists():
            continue

        # 1) ALL Germany (global repulsion, global sizing)
        g_all = gpd.read_file(in_all)
        out_all = bin_dir / f"de_landkreis_pie_{bin_slug}.geojson"
        n_all = make_pies_for_points(g_all, vmin, vmax, out_all)

        # 2) Per-state (state-local repulsion, but SAME global sizing)
        counts = {}
        state_inputs = sorted((BASE_DIR).glob(f"*/{bin_slug}/de_*_landkreis_pies_{bin_slug}.geojson"))
        for in_state in state_inputs:
            # in_state is BASE_DIR/<state_slug>/<bin_slug>/de_<state_slug>_landkreis_pies_<bin_slug>.geojson
            state_slug = in_state.parent.parent.name  # <state_slug>
            g_state = gpd.read_file(in_state)
            out_state = in_state.parent / f"de_{state_slug}_landkreis_pie_{bin_slug}.geojson"
            n_state = make_pies_for_points(g_state, vmin, vmax, out_state)
            counts[state_slug] = n_state

        print(f"\n[OK] {bin_slug} → ALL ({n_all})")
        for st, n in sorted(counts.items()):
            print(f"      └─ {st}: {n}")

    print("\n[DONE] step3_4 complete.")


if __name__ == "__main__":
    main()
