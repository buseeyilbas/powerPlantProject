"""
Statewise Landkreis pie polygons (single layer per state) + overlap avoidance.

Input :  C:\...\data\geojson\pieCharts\statewise_landkreis_pies\de_XXX_landkreis_pies.geojson
Output:  C:\...\data\geojson\pieCharts\statewise_landkreis_pies\de_XXX_landkreis_pie.geojson
         (tek katman, her dilim ayrı feature; label_anchor ile tek dilimde etiket)

Çakışma önleme:
- Merkezler EPSG:3857'e projeksiyon yapılıyor.
- Mesafe < r_i + r_j + GAP_M ise ikisi hattı boyunca yarı-yarıya itiliyor.
- MAX_NUDGE_ITER kadar tekrarlanıyor (küçük itmeler; geometriyi çok bozmuyor).

QGIS ipucu:
- Layer Properties → Rendering → Control feature rendering order:
  expression:  "radius_m"  (ascending)  → küçükler üstte kalsın.
"""

from pathlib import Path
import math, json
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

# ---------------- PATHS ----------------
BASE_DIR   = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts")
IN_DIR     = BASE_DIR / "statewise_landkreis_pies"
OUT_DIR    = BASE_DIR / "statewise_landkreis_pies"
# --------------------------------------

# ---- Boyutlandırma (lineer yarıçap) ----
# NOT: Statewise ölçek = her state dosyasındaki min/max 'total_kw'
R_MIN_M = 10000.0     # yakınlaşınca çok küçük olmasın diye taban yarıçap
R_MAX_M = 30000.0    # state içindeki en büyük toplam güce karşılık gelen yarıçap

# ---- Çakışma önleme ayarları ----
GAP_M          = 2000.0   # iki pie birbirine en az bu kadar "boşluk" bıraksın
MAX_NUDGE_ITER = 120       # itme iterasyon sayısı (yeterli, çok büyütmeyin)

# ---- Palet ----
COLORS = {
    "pv_kw":      (255, 255,   0),
    "battery_kw": (148,  87, 235),
    "wind_kw":    (173, 216, 230),
    "hydro_kw":   (  0,   0, 255),
    "biogas_kw":  (  0, 190,   0),
    "others_kw":  (158, 158, 158),
}

def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:
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
    for k, v in ordered_pairs:
        share = (v/total) if v and v > 0 else 0.0
        dth = share * 2*math.pi
        t1, t2 = ang, ang + dth
        ang = t2
        if share > 0:
            arc = ring_pts(center_m, radius_m, t1, t2)
            poly = Polygon([center_m] + arc + [center_m])
            slices.append((k, share, poly))
        shares.append((k, share))
    # en büyük dilimi etiketle
    anchor_key = max(shares, key=lambda kv: kv[1])[0] if shares else None
    return slices, anchor_key

def repulse_centers(centers):
    """
    centers: list of dicts
      {'x':float, 'y':float, 'r':float}  # EPSG:3857 metre cinsinden
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
                    # rasgele küçük açıyla ayır
                    ang = (i+1) * 2*math.pi / (len(centers)+1)
                    dx, dy = math.cos(ang), math.sin(ang)
                    d = 1.0
                if d < need:
                    # kısa kalanı iki merkeze yarı yarıya dağıt
                    push = (need - d) / 2.0
                    ux, uy = dx/d, dy/d
                    pi['x'] -= ux * push; pi['y'] -= uy * push
                    pj['x'] += ux * push; pj['y'] += uy * push
                    moved = True
        if not moved:
            break

def process_one_state(infile: Path):
    state_slug = infile.stem.replace("_landkreis_pies", "")
    g = gpd.read_file(infile)
    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.set_crs("EPSG:4326", allow_override=True)

    # state içi min/max (statewise scaling)
    vmin = float(g["total_kw"].min()) if len(g) else 0.0
    vmax = float(g["total_kw"].max()) if len(g) else 1.0
    if vmax <= vmin: vmax = vmin + 1.0

    to_m   = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    # merkezleri ve yarıçapları hazırla
    centers = []
    rows = []
    for _, r in g.iterrows():
        cx, cy = float(r.geometry.x), float(r.geometry.y)
        cxm, cym = to_m.transform(cx, cy)
        total = float(r.get("total_kw", 0.0))
        rad   = scale_linear(total, vmin, vmax, R_MIN_M, R_MAX_M)
        centers.append({'x': cxm, 'y': cym, 'r': rad})
        rows.append(r)

    # çakışma giderme
    repulse_centers(centers)

    # dilimleri üret
    out_rows = []
    for (r, c) in zip(rows, centers):
        # enerji kalemleri sabit sırada
        parts = [("pv_kw", float(r.get("pv_kw", 0.0))),
                 ("wind_kw", float(r.get("wind_kw", 0.0))),
                 ("hydro_kw", float(r.get("hydro_kw", 0.0))),
                 ("battery_kw", float(r.get("battery_kw", 0.0))),
                 ("biogas_kw", float(r.get("biogas_kw", 0.0))),
                 ("others_kw", float(r.get("others_kw", 0.0)))]
        slices_m, anchor_key = make_pie((c['x'], c['y']), c['r'], parts)
        for k, share, poly_m in slices_m:
            poly_deg = Polygon([to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords])
            rRGB, gRGB, bRGB = COLORS[k]
            out_rows.append({
                "state_name": r.get("state_name"),
                "name":       r.get("name", r.get("kreis_name", r.get("landkreis_name", ""))),
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
    outfile = OUT_DIR / f"{state_slug}_landkreis_pie.geojson"
    out.to_file(outfile, driver="GeoJSON")
    print(f"[OK] wrote {outfile.name} (features={len(out)})")

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(IN_DIR.glob("de_*_landkreis_pies.geojson"))
    if not files:
        raise RuntimeError(f"No input found under: {IN_DIR}")

    for f in files:
        process_one_state(f)

if __name__ == "__main__":
    main()
