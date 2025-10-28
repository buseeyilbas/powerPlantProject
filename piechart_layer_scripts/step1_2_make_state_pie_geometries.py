

import json, math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

# ---------------- Settings ----------------
BASE = Path(r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts")
IN_FILE  = BASE / "de_state_pies.geojson"
META_FILE = BASE / "state_pie_style_meta.json"
OUT_FILE = BASE / "de_state_pie.geojson"

# linear radius scaling (meters)
MIN_RADIUS_M = 15000.0
MAX_RADIUS_M = 35000.0

# collision avoidance (set DO_REPEL=False to disable)
DO_REPEL = True
MIN_SEPARATION_KM = 35.0   # target min center-to-center distance
MAX_REPEL_ITER    = 60     # max iterations
MAX_STEP_KM       = 2.0    # max push per iteration

# pie construction
NVERT_ARC = 36  # vertices along each arc slice (smoothness)

# energy fields (order defines slice order)
FIELDS = ["pv_kw", "battery_kw", "wind_kw", "hydro_kw", "biogas_kw", "others_kw"]
NAME_FIELD_CANDIDATES = ["state_name", "name", "bundesland", "Bundesland"]
# ------------------------------------------


def meters_per_deg(lat_deg: float):
    """Return (m_per_deg_lon, m_per_deg_lat) at given latitude."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_deg))
    return m_per_deg_lon, m_per_deg_lat


def circle_point(lon0, lat0, radius_m, theta_rad):
    m_per_deg_lon, m_per_deg_lat = meters_per_deg(lat0)
    dlon = (radius_m * math.cos(theta_rad)) / m_per_deg_lon
    dlat = (radius_m * math.sin(theta_rad)) / m_per_deg_lat
    return (lon0 + dlon, lat0 + dlat)


def slice_polygon(lon0, lat0, r_m, ang0, ang1, n=NVERT_ARC):
    """Create a wedge polygon from ang0 to ang1 (radians)."""
    if ang1 < ang0:
        ang0, ang1 = ang1, ang0
    pts = [(lon0, lat0)]
    if n < 2:
        n = 2
    for k in range(n + 1):
        t = ang0 + (ang1 - ang0) * (k / n)
        pts.append(circle_point(lon0, lat0, r_m, t))
    pts.append((lon0, lat0))
    return Polygon(pts)


def linear_radius(total_kw, vmin, vmax):
    if vmax <= vmin:
        return (MIN_RADIUS_M + MAX_RADIUS_M) * 0.5
    t = (total_kw - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    return MIN_RADIUS_M + t * (MAX_RADIUS_M - MIN_RADIUS_M)


def repel_centers(xy_list):
    """
    Simple repulsion so centers are at least MIN_SEPARATION_KM apart.
    xy_list: list of [lon, lat] in WGS84.
    """
    if not DO_REPEL or len(xy_list) < 2:
        return xy_list

    pts = [[float(x), float(y)] for x, y in xy_list]

    for _ in range(MAX_REPEL_ITER):
        moved = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                xi, yi = pts[i]
                xj, yj = pts[j]
                lat_mid = (yi + yj) * 0.5
                m_lon, m_lat = meters_per_deg(lat_mid)
                dx_m = (xj - xi) * m_lon
                dy_m = (yj - yi) * m_lat
                dist_km = math.hypot(dx_m, dy_m) / 1000.0
                if dist_km < 1e-6:
                    # identical; push by small random-ish angle
                    ang = 2 * math.pi * (i + 1) / (len(pts) + 1)
                    step_km = min(MAX_STEP_KM, MIN_SEPARATION_KM * 0.5)
                    dlon = (step_km * math.cos(ang) * 1000.0) / m_lon
                    dlat = (step_km * math.sin(ang) * 1000.0) / m_lat
                    pts[j][0] += dlon
                    pts[j][1] += dlat
                    moved = True
                    continue
                if dist_km < MIN_SEPARATION_KM:
                    shortfall = MIN_SEPARATION_KM - dist_km
                    step_km = min(MAX_STEP_KM, shortfall * 0.5)
                    ux = dx_m / (dist_km * 1000.0)
                    uy = dy_m / (dist_km * 1000.0)
                    # move away along the line connecting centers
                    dlon = (ux * step_km * 1000.0) / m_lon
                    dlat = (uy * step_km * 1000.0) / m_lat
                    pts[i][0] -= dlon
                    pts[i][1] -= dlat
                    pts[j][0] += dlon
                    pts[j][1] += dlat
                    moved = True
        if not moved:
            break
    return pts


def main():
    if not IN_FILE.exists():
        raise FileNotFoundError(f"Missing input: {IN_FILE}")

    g = gpd.read_file(IN_FILE)
    if g.crs is None:
        g.set_crs(epsg=4326, inplace=True)

    # figure out name field
    name_field = next((c for c in NAME_FIELD_CANDIDATES if c in g.columns), None)
    if not name_field:
        name_field = "name"

    # min/max for linear scaling
    if META_FILE.exists():
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        vmin = float(meta.get("min_total_kw", float(g["total_kw"].min())))
        vmax = float(meta.get("max_total_kw", float(g["total_kw"].max())))
    else:
        vmin = float(g["total_kw"].min())
        vmax = float(g["total_kw"].max())

    # prepare centers and optional repulsion
    centers = list(zip(g.geometry.x.astype(float), g.geometry.y.astype(float)))
    centers = repel_centers(centers)

    records = []
    for (lon, lat), (_, row) in zip(centers, g.iterrows()):
        total = float(row.get("total_kw", 0.0)) or 0.0
        if total <= 0:
            continue
        r_m = linear_radius(total, vmin, vmax)

        # build slices
        vals = [(fld, float(row.get(fld, 0.0)) or 0.0) for fld in FIELDS]
        sum_pos = sum(v for _, v in vals)
        if sum_pos <= 0:
            continue

        ang = 0.0
        biggest = max(vals, key=lambda kv: kv[1])[0]
        for fld, v in vals:
            if v <= 0:
                continue
            frac = v / sum_pos
            sweep = frac * 2 * math.pi
            poly = slice_polygon(lon, lat, r_m, ang, ang + sweep, NVERT_ARC)
            records.append({
                "name": str(row.get(name_field, "")),
                "energy_type": fld,
                "radius_m": r_m,
                "label_anchor": 1 if fld == biggest else 0,
                "geometry": poly
            })
            ang += sweep

    out = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    out.to_file(OUT_FILE, driver="GeoJSON")
    print(f"[OK] wrote {OUT_FILE} (features={len(out)})")


if __name__ == "__main__":
    main()
