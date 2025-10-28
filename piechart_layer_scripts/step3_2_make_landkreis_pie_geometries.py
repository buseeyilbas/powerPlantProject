# make_landkreis_pie_geometries.py
# Nationwide Landkreis pie polygons (single layer) with radius-aware repulsion (QGIS-friendly)

from pathlib import Path
import math, json
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

# ---------------- PATHS ----------------
BASE = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts")
IN_FILE   = BASE / "de_landkreis_pies.geojson"          # point + totals (from make_landkreis_pie_inputs.py)
META_FILE = BASE / "landkreis_pie_style_meta.json"      # optional (min/max), else computed
OUT_FILE  = BASE / "de_landkreis_pie.geojson"           # ONE layer, each slice = one feature
# --------------------------------------

# ---- Boyutlandırma (lineer yarıçap) ----
R_MIN_M = 10000.0     # en küçük pie yarıçapı (metre)
R_MAX_M = 50000.0    # en büyük pie yarıçapı (metre)

# ---- Çakışma önleme ayarları ----
GAP_M          = 2000.0   # iki pie arasında bırakılacak ekstra boşluk
MAX_NUDGE_ITER = 120      # itme iterasyon sayısı

# ---- Enerji alanları sabit sırası ----
PARTS = ["pv_kw", "wind_kw", "hydro_kw", "battery_kw", "biogas_kw", "others_kw"]

# ---- Renkleri istersen stil tarafında kullanırsın (zorunlu değil) ----
PALETTE_RGB = {
    "pv_kw":      (255,212,  0),
    "battery_kw": (126, 87,194),
    "wind_kw":    (173,216,230),
    "hydro_kw":   ( 30, 58,138),
    "biogas_kw":  ( 46,125, 50),
    "others_kw":  (158,158,158),
}

def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:   # kenar durum
        return (omin + omax) / 2.0
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
    if total <= 0:
        return [], None
    slices, shares = [], []
    ang = 0.0
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
    """
    centers: [{'x':float, 'y':float, 'r':float}]  # EPSG:3857 metre
    Koşul: dist >= r_i + r_j + GAP_M
    """
    for _ in range(MAX_NUDGE_ITER):
        moved = False
        for i in range(len(centers)):
            for j in range(i+1, len(centers)):
                pi, pj = centers[i], centers[j]
                dx = pj['x'] - pi['x']
                dy = pj['y'] - pi['y']
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
        if not moved:
            break

def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing input: {IN_FILE}")

    g = gpd.read_file(IN_FILE)
    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.set_crs("EPSG:4326", allow_override=True)

    # min/max total_kw (ülke geneli)
    if META_FILE.exists():
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        vmin = float(meta.get("min_total_kw", float(g["total_kw"].min())))
        vmax = float(meta.get("max_total_kw", float(g["total_kw"].max())))
    else:
        vmin = float(g["total_kw"].min()) if len(g) else 0.0
        vmax = float(g["total_kw"].max()) if len(g) else 1.0
    if vmax <= vmin: vmax = vmin + 1.0

    to_m   = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    # merkez + yarıçap listesi
    centers, rows = [], []
    for _, r in g.iterrows():
        cx, cy = float(r.geometry.x), float(r.geometry.y)
        cxm, cym = to_m.transform(cx, cy)
        total = float(r.get("total_kw", 0.0))
        rad   = scale_linear(total, vmin, vmax, R_MIN_M, R_MAX_M)
        centers.append({'x': cxm, 'y': cym, 'r': rad})
        rows.append(r)

    # çakışma önleme
    repulse_centers(centers)

    # dilimleri üret
    out_rows = []
    for r, c in zip(rows, centers):
        parts = [(k, float(r.get(k, 0.0)) or 0.0) for k in PARTS]
        slices_m, anchor_key = make_pie((c['x'], c['y']), c['r'], parts)
        for k, share, poly_m in slices_m:
            poly_deg = Polygon([to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords])
            rRGB, gRGB, bRGB = PALETTE_RGB[k]
            out_rows.append({
                # isim alanı (hangi isim varsa onu taşı)
                "name":       r.get("name", r.get("kreis_name", r.get("landkreis", ""))),
                "energy_type": k,
                "power_kw":    float(dict(parts).get(k, 0.0)),
                "share":       float(share),
                "total_kw":    float(r.get("total_kw", 0.0)),
                "radius_m":    float(c['r']),
                "label_anchor": 1 if (anchor_key == k) else 0,
                "color_r": rRGB, "color_g": gRGB, "color_b": bRGB,
                "geometry": poly_deg
            })

    out = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT_FILE, driver="GeoJSON")
    print(f"[OK] wrote {OUT_FILE} (features={len(out)})")

if __name__ == "__main__":
    main()
