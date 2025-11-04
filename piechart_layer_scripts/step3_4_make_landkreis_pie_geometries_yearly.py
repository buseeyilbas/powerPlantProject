# Filename: step3_4_make_landkreis_pie_geometries_yearly.py
# Purpose : Build Landkreis pie POLYGONS per YEAR BIN, inside <bin>/<state>/ folders.
# Inputs  : <BASE>/<bin>/<state>/de_<state>_landkreis_pies_<bin>.geojson
#           <BASE>/<bin>/landkreis_pie_style_meta_<bin>.json (for per-bin scaling)
# Outputs : <BASE>/<bin>/<state>/de_<state>_landkreis_pie_<bin>.geojson

from pathlib import Path
import math, json
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

BASE = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly")

# scaling per bin
R_MIN_M = 10000.0
R_MAX_M = 50000.0
GAP_M   = 2000.0
MAX_NUDGE_ITER = 120

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
    if vmax <= vmin: return (omin + omax) / 2.0
    t = (val - vmin) / (vmax - vmin)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return omin + t * (omax - omin)

def ring_pts(cxy, r, th1, th2, n=48):
    cx, cy = cxy
    out = []
    for i in range(n+1):
        th = th1 + (th2 - th1) * (i / n)
        out.append((cx + r*math.cos(th), cy + r*math.sin(th)))
    return out

def make_pie(center_m, radius_m, ordered_pairs):
    total = sum(v for _, v in ordered_pairs if v and v > 0)
    if total <= 0: return [], None
    slices, shares, ang = [], [], 0.0
    for key, v in ordered_pairs:
        share = (v/total) if v and v > 0 else 0.0
        dth = share * 2*math.pi
        t1, t2 = ang, ang + dth; ang = t2
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
                dx = pj['x'] - pi['x']; dy = pj['y'] - pi['y']
                d  = math.hypot(dx, dy)
                need = pi['r'] + pj['r'] + GAP_M
                if d == 0.0:
                    ang = (i+1) * 2*math.pi / (len(centers)+1)
                    dx, dy, d = math.cos(ang), math.sin(ang), 1.0
                if d < need:
                    push = (need - d) / 2.0
                    ux, uy = dx/d, dy/d
                    pi['x'] -= ux * push; pi['y'] -= uy * push
                    pj['x'] += ux * push; pj['y'] += uy * push
                    moved = True
        if not moved: break

def pies_from_points(gdf_points, vmin, vmax, out_path: Path):
    if gdf_points.empty: return 0
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

    repulse_centers(centers)

    out_rows = []
    for r, c in zip(rows, centers):
        parts = [(k, float(r.get(k, 0.0)) or 0.0) for k in PARTS]
        slices_m, anchor_key = make_pie((c['x'], c['y']), c['r'], parts)
        for k, share, poly_m in slices_m:
            poly_deg = Polygon([to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords])
            R, G, B = PALETTE_RGB[k]
            out_rows.append({
                "name":        r.get("name", r.get("kreis_name", "")),
                "energy_type": k,
                "power_kw":    float(dict(parts).get(k, 0.0)),
                "share":       float(share),
                "total_kw":    float(r.get("total_kw", 0.0)),
                "radius_m":    float(c['r']),
                "label_anchor": 1 if (anchor_key == k) else 0,
                "year_bin":    r.get("year_bin_label", r.get("year_bin", "")),
                "year_bin_slug": r.get("year_bin_slug", ""),
                "color_r": R, "color_g": G, "color_b": B,
                "geometry":    poly_deg
            })

    out = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(out_path, driver="GeoJSON")
    return len(out)

def main():
    # Iterate bins (directories under BASE). Each bin has its meta + state folders with *points*.
    for bin_dir in sorted([p for p in BASE.iterdir() if p.is_dir()]):
        meta = bin_dir / f"landkreis_pie_style_meta_{bin_dir.name}.json"
        if not meta.exists():
            print(f"[SKIP] No meta for bin {bin_dir.name}")
            continue
        meta_obj = json.loads(meta.read_text(encoding="utf-8"))
        vmin = float(meta_obj.get("min_total_kw", 0.0))
        vmax = float(meta_obj.get("max_total_kw", 1.0))
        if vmax <= vmin: vmax = vmin + 1.0

        # For each state folder inside this bin
        state_dirs = [d for d in bin_dir.iterdir() if d.is_dir()]
        if not state_dirs:
            print(f"[WARN] No state folders under {bin_dir.name}")
            continue

        for st_dir in state_dirs:
            pts = list(st_dir.glob(f"de_{st_dir.name}_landkreis_pies_{bin_dir.name}.geojson"))
            if not pts:
                # try any matching file
                pts = list(st_dir.glob("de_*_landkreis_pies_*.geojson"))
            if not pts:
                print(f"[WARN] No points in {st_dir}")
                continue
            in_points = pts[0]
            out_geojson = st_dir / f"de_{st_dir.name}_landkreis_pie_{bin_dir.name}.geojson"
            n = pies_from_points(gpd.read_file(in_points), vmin, vmax, out_geojson)
            print(f"[OK] {bin_dir.name}/{st_dir.name} -> features={n}")

if __name__ == "__main__":
    main()
