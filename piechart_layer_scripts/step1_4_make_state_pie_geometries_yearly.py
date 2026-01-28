# Filename: step1_4_make_state_pie_geometries_yearly.py
# Purpose : Read state pie INPUT points from step1_3 and generate real pie polygons
#           for each year bin, using global or per-bin scaling.

from pathlib import Path
import math
import json
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

BASE = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies_yearly")
GLOBAL_META = BASE / "_GLOBAL_style_meta.json"

# ---- sizing ----
GLOBAL_SIZING = True          # True → all-over-the-years (use GLOBAL_META); False → per-bin
R_MIN_M = 20000.0
R_MAX_M = 80000.0
GAP_M   = 2500.0
MAX_NUDGE_ITER = 120
CENTERS_ARE_FIXED = True      # centers already fixed in step1_3

PARTS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]
PALETTE_RGB = {
    "pv_kw":      (255,212,  0),
    "battery_kw": (126, 87,194),
    "wind_kw":    (173,216,230),
    "hydro_kw":   ( 30, 58,138),
    "biogas_kw":  ( 46,125, 50),
    "others_kw":  (158,158,158),
}

def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:
        return (omin + omax) / 2.0
    t = (val - vmin) / (vmax - vmin)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return omin + t * (omax - omin)

def ring_pts(cxy, r, th1, th2, n=48):
    cx, cy = cxy
    return [(cx + r*math.cos(th1 + (th2-th1)*i/n),
             cy + r*math.sin(th1 + (th2-th1)*i/n)) for i in range(n+1)]

def make_pie(center_m, radius_m, ordered_pairs):
    total = sum(v for _, v in ordered_pairs if v and v > 0)
    if total <= 0:
        return [], None
    slices, shares, ang = [], [], 0.0
    for key, v in ordered_pairs:
        share = (v/total) if v and v > 0 else 0.0
        dth = share * 2*math.pi
        t1, t2 = ang, ang + dth
        ang = t2
        if share > 0:
            arc = ring_pts(center_m, radius_m, t1, t2)
            poly = Polygon([center_m] + arc + [center_m])
            slices.append((key, share, poly))
        shares.append((key, share))
    anchor_key = max(shares, key=lambda kv: kv[1])[0] if shares else None
    return slices, anchor_key

def repulse_centers(centers):
    for _ in range(MAX_NUDGE_ITER):
        moved = False
        for i in range(len(centers)):
            for j in range(i+1, len(centers)):
                pi, pj = centers[i], centers[j]
                dx, dy = pj['x']-pi['x'], pj['y']-pi['y']
                d = math.hypot(dx, dy)
                need = pi['r'] + pj['r'] + GAP_M
                if d == 0.0:
                    ang = (i+1) * 2*math.pi / (len(centers)+1)
                    dx, dy, d = math.cos(ang), math.sin(ang), 1.0
                if d < need:
                    push = (need - d) / 2.0
                    ux, uy = dx/d, dy/d
                    pi['x'] -= ux*push
                    pi['y'] -= uy*push
                    pj['x'] += ux*push
                    pj['y'] += uy*push
                    moved = True
        if not moved:
            break

def pies_from_points(gdf_points, vmin, vmax, out_path: Path):
    if gdf_points.empty:
        return 0
    if gdf_points.crs is None or gdf_points.crs.to_epsg() != 4326:
        gdf_points = gdf_points.set_crs("EPSG:4326", allow_override=True)

    to_m   = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    centers, rows = [], []
    for _, r in gdf_points.iterrows():
        cx, cy = float(r.geometry.x), float(r.geometry.y)
        cxm, cym = to_m.transform(cx, cy)
        total = float(r.get("total_kw", 0.0))
        rad   = scale_linear(total, vmin, vmax, R_MIN_M, R_MAX_M)
        centers.append({'x': cxm, 'y': cym, 'r': rad})
        rows.append(r)

    if not CENTERS_ARE_FIXED:
        repulse_centers(centers)

    out_rows = []
    for r, c in zip(rows, centers):
        parts = [(k, float(r.get(k, 0.0)) or 0.0) for k in PARTS]
        slices_m, anchor_key = make_pie((c['x'], c['y']), c['r'], parts)

        sn_raw = r.get("state_number", None)
        state_num = None
        if sn_raw is not None:
            try:
                state_num = int(sn_raw)
            except Exception:
                state_num = None

        for k, share, poly_m in slices_m:
            poly_deg = Polygon([to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords])
            R, G, B = PALETTE_RGB[k]
            out_rows.append({
                "name":         r.get("state_name", r.get("name", "")),
                "state_number": state_num,
                "energy_type":  k,
                "power_kw":     float(dict(parts).get(k, 0.0)),
                "total_kw":     float(r.get("total_kw", 0.0)),
                "power_gw":     float(dict(parts).get(k, 0.0)) / 1_000_000.0,
                "total_gw":     float(r.get("total_kw", 0.0)) / 1_000_000.0,
                "share":        float(share),
                "radius_m":     float(c['r']),
                "label_anchor": 1 if (anchor_key == k) else 0,
                "year_bin":     r.get("year_bin_label", r.get("year_bin", "")),
                "year_bin_slug": r.get("year_bin_slug", ""),
                "color_r":      R,
                "color_g":      G,
                "color_b":      B,
                "geometry":     poly_deg
            })

    out = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(out_path, driver="GeoJSON")
    return len(out)

def main():
    global_min, global_max = None, None
    if GLOBAL_SIZING and GLOBAL_META.exists():
        gm = json.loads(GLOBAL_META.read_text(encoding="utf-8"))
        global_min, global_max = float(gm["min_total_kw"]), float(gm["max_total_kw"])
        print(f"[GLOBAL SCALE] Using meta: min={global_min:.2f}, max={global_max:.2f}")
    elif GLOBAL_SIZING:
        totals = []
        for bin_dir in sorted([p for p in BASE.iterdir() if p.is_dir()]):
            pts = bin_dir / f"de_state_pies_{bin_dir.name}.geojson"
            if pts.exists():
                g = gpd.read_file(pts)
                if len(g):
                    totals += list(g["total_kw"].astype(float))
        if totals:
            global_min, global_max = float(min(totals)), float(max(totals))
            print(f"[GLOBAL SCALE] Computed: min={global_min:.2f}, max={global_max:.2f}")

    for bin_dir in sorted([p for p in BASE.iterdir() if p.is_dir()]):
        pts  = bin_dir / f"de_state_pies_{bin_dir.name}.geojson"
        meta = bin_dir / f"state_pie_style_meta_{bin_dir.name}.json"
        if not pts.exists() or not meta.exists():
            print(f"[SKIP] Missing inputs for bin {bin_dir.name}")
            continue

        meta_obj = json.loads(meta.read_text(encoding="utf-8"))
        vmin = float(meta_obj.get("min_total_kw", 0.0))
        vmax = float(meta_obj.get("max_total_kw", 1.0))
        if vmax <= vmin:
            vmax = vmin + 1.0

        if GLOBAL_SIZING and (global_min is not None) and (global_max is not None):
            vmin, vmax = global_min, global_max
            print(f"[USING SCALE] {bin_dir.name}: GLOBAL vmin={vmin:.2f}, vmax={vmax:.2f}")
        else:
            print(f"[USING SCALE] {bin_dir.name}: BIN vmin={vmin:.2f}, vmax={vmax:.2f}")

        g_points = gpd.read_file(pts)
        out_geojson = bin_dir / f"de_state_pie_{bin_dir.name}.geojson"
        n = pies_from_points(g_points, vmin, vmax, out_geojson)
        print(f"[OK] {bin_dir.name} -> features={n}  -> {out_geojson.name}")

    print("[DONE] step1_4 complete.")

if __name__ == "__main__":
    main()
