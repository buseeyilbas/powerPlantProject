# Filename: step3_2_make_landkreis_pie_geometries.py
# Purpose:
#   Convert NATIONWIDE-scaled Landkreis pie INPUT POINTS (from step3_1)
#   into actual pie-slice polygons PER STATE,
#   using the SAME logic as step2_2.
#
# Key difference to step2_2:
#   - radius scaling (vmin/vmax) is computed NATIONWIDE
#   - geometry generation is still PER STATE (no single nationwide file)

from pathlib import Path
import math, json

import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import Transformer

# ---------------- PATHS ----------------

BASE_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies"
)

IN_FILE = BASE_DIR / "de_landkreis_pies.geojson"
META_FILE = BASE_DIR / "landkreis_pie_style_meta.json"

OUT_DIR = BASE_DIR

# ---------------- SIZING ----------------

R_MIN_M = 10000.0
R_MAX_M = 50000.0

# ---------------- OVERLAP AVOIDANCE ----------------

GAP_M = 2000.0
MAX_NUDGE_ITER = 120

# ---------------- ENERGY PARTS ----------------

PART_FIELDS = [
    "pv_kw",
    "wind_kw",
    "hydro_kw",
    "battery_kw",
    "biogas_kw",
    "others_kw",
]

COLORS = {
    "pv_kw":      (255, 212,   0),
    "battery_kw": (126,  87, 194),
    "wind_kw":    (173, 216, 230),
    "hydro_kw":   ( 30,  58, 138),
    "biogas_kw":  ( 46, 125,  50),
    "others_kw":  (158, 158, 158),
}

# ---------------- HELPERS ----------------

def scale_linear(val, vmin, vmax, omin, omax):
    if vmax <= vmin:
        return (omin + omax) / 2.0
    t = (val - vmin) / (vmax - vmin)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return omin + t * (omax - omin)


def ring_pts(center, r, th1, th2, n=48):
    cx, cy = center
    out = []
    for i in range(n + 1):
        th = th1 + (th2 - th1) * (i / n)
        out.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return out


def make_pie(center_m, radius_m, parts):
    total = sum(v for _, v in parts if v and v > 0)
    if total <= 0:
        return [], None

    slices = []
    shares = []
    ang = 0.0

    for k, v in parts:
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


def process_one_state(g_state, vmin, vmax, state_slug):
    to_m   = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    to_deg = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    centers = []
    rows = []

    for _, r in g_state.iterrows():
        cx, cy = float(r.geometry.x), float(r.geometry.y)
        cxm, cym = to_m.transform(cx, cy)
        total = float(r.get("total_kw", 0.0))
        rad = scale_linear(total, vmin, vmax, R_MIN_M, R_MAX_M)
        centers.append({"x": cxm, "y": cym, "r": rad})
        rows.append(r)

    repulse_centers(centers)

    out_rows = []
    for r, c in zip(rows, centers):
        parts = [(f, float(r.get(f, 0.0))) for f in PART_FIELDS]
        slices_m, anchor_key = make_pie((c["x"], c["y"]), c["r"], parts)

        for k, share, poly_m in slices_m:
            poly_deg = Polygon(
                [to_deg.transform(x, y) for (x, y) in poly_m.exterior.coords]
            )
            R, G, B = COLORS[k]
            out_rows.append(
                {
                    "state_slug": state_slug,
                    "name": r.get("kreis_name"),
                    "energy_type": k,
                    "power_kw": float(dict(parts).get(k, 0.0)),
                    "share": float(share),
                    "total_kw": float(r.get("total_kw", 0.0)),
                    "radius_m": float(c["r"]),
                    "label_anchor": 1 if anchor_key == k else 0,
                    "color_r": R,
                    "color_g": G,
                    "color_b": B,
                    "geometry": poly_deg,
                }
            )

    out = gpd.GeoDataFrame(out_rows, geometry="geometry", crs="EPSG:4326")
    out_path = OUT_DIR / state_slug / f"de_{state_slug}_landkreis_pie.geojson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(out_path, driver="GeoJSON")
    print(f"[OK] wrote {out_path}")


# ---------------- MAIN ----------------

def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing input: {IN_FILE}")

    gdf = gpd.read_file(IN_FILE)

    # --- nationwide scaling ---
    if META_FILE.exists():
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        vmin = float(meta.get("min_total_kw", gdf["total_kw"].min()))
        vmax = float(meta.get("max_total_kw", gdf["total_kw"].max()))
    else:
        vmin = float(gdf["total_kw"].min())
        vmax = float(gdf["total_kw"].max())

    if vmax <= vmin:
        vmax = vmin + 1.0

    # --- process per state (2_2 style) ---
    for slug, sub in gdf[gdf["state_slug"] != ""].groupby("state_slug"):
        process_one_state(sub, vmin, vmax, slug)


if __name__ == "__main__":
    main()
