# Filename: step0_for2and3_make_landkreis_centers.py
# Purpose:
#   Build authoritative Landkreis centers using GADM polygons.
#   Solves:
#     - nested Landkreis conflicts
#     - border proximity (aesthetic crowding)

from pathlib import Path
import os
import re
import unicodedata
import collections

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ================= CONFIG =================

DEBUG_PRINT = True

CRS_INPUT = "EPSG:4326"
CRS_METRIC = "EPSG:3035"
CRS_OUTPUT = "EPSG:4326"

# Nested shifting
STEP_M = 3500.0
MAX_LOCAL_ITER = 40
MAX_GLOBAL_ITER = 10

# Border proximity pull
BORDER_THRESHOLD_M = 4500.0

INPUT_ROOT = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"
)

LANDKREIS_POLYGONS_PATH = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
)

CENTERS_DIR = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\landkreis_centers"
)
CENTERS_PATH = CENTERS_DIR / "de_landkreis_centers.geojson"

STATE_SLUG_TO_OFFICIAL = {
    "baden-wuerttemberg": "Baden-Württemberg",
    "baden-württemberg": "Baden-Württemberg",
    "bayern": "Bayern",
    "berlin": "Berlin",
    "brandenburg": "Brandenburg",
    "bremen": "Bremen",
    "hamburg": "Hamburg",
    "hessen": "Hessen",
    "mecklenburg-vorpommern": "Mecklenburg-Vorpommern",
    "niedersachsen": "Niedersachsen",
    "nordrhein-westfalen": "Nordrhein-Westfalen",
    "rheinland-pfalz": "Rheinland-Pfalz",
    "saarland": "Saarland",
    "sachsen": "Sachsen",
    "sachsen-anhalt": "Sachsen-Anhalt",
    "schleswig-holstein": "Schleswig-Holstein",
    "thueringen": "Thüringen",
    "thüringen": "Thüringen",
    "thuringen": "Thüringen",
}

NAME_FIELDS = (
    "Landkreis", "landkreis", "Kreis", "kreis",
    "kreis_name", "Landkreisname", "landkreisname", "GEN"
)

# ================= HELPERS =================

def norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def clean_kreis_label(name):
    if not name:
        return ""
    s = name.lower()
    for rep in ["kreisfreie stadt", "landkreis", "stadtkreis", "kreis"]:
        s = s.replace(rep, " ")
    s = re.sub(r"-?kreis\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(w.capitalize() for w in s.split())


def extract_ags5(row):
    for k in (
        "Gemeindeschluessel", "gemeindeschluessel",
        "AGS", "ags", "ags_id", "kreisschluessel", "rs"
    ):
        if k in row and pd.notna(row[k]):
            d = re.sub(r"[^0-9]", "", str(row[k]))
            if len(d) >= 5:
                return d[:5]
    return None


def scan_geojsons(folder):
    for r, _, fns in os.walk(folder):
        for fn in fns:
            if fn.lower().endswith(".geojson"):
                yield Path(r) / fn


def choose_label(labels):
    labels = [l for l in labels if l]
    if not labels:
        return ""
    cnt = collections.Counter(labels)
    top = cnt.most_common(1)[0][1]
    cands = [l for l, n in cnt.items() if n == top]
    return max(cands, key=len)


def shift_inward(poly):
    buf = poly
    for _ in range(MAX_LOCAL_ITER):
        buf = buf.buffer(-STEP_M)
        if buf.is_empty:
            break
        pt = buf.representative_point()
        if pt.within(poly):
            return pt
    return poly.representative_point()

# ================= MAIN =================

def main():
    print("\n[step2_0] Building Landkreis centers (nested + border-safe)")

    if not LANDKREIS_POLYGONS_PATH.exists():
        raise RuntimeError(f"GADM polygons not found: {LANDKREIS_POLYGONS_PATH}")

    g_polys = gpd.read_file(LANDKREIS_POLYGONS_PATH)
    if g_polys.crs is None:
        g_polys = g_polys.set_crs(CRS_INPUT, allow_override=True)

    g_polys_m = g_polys[["geometry"]].to_crs(CRS_METRIC)
    g_polys_m["area"] = g_polys_m.geometry.area
    sidx = g_polys_m.sindex

    centers_acc = {}

    # ---------- collect plant points ----------
    for state_dir in INPUT_ROOT.iterdir():
        if not state_dir.is_dir():
            continue

        state_slug = norm(state_dir.name)
        state_name = STATE_SLUG_TO_OFFICIAL.get(state_slug, state_dir.name)

        for p in scan_geojsons(state_dir):
            try:
                g = gpd.read_file(p)
            except Exception:
                continue

            if g.empty or "geometry" not in g.columns:
                continue

            if g.crs is None:
                g = g.set_crs(CRS_INPUT, allow_override=True)

            g = g[g.geometry.notnull()]
            g = g[g.geometry.geom_type.isin(["Point", "MultiPoint"])]

            try:
                g = g.explode(index_parts=False)
            except Exception:
                g = g.explode()

            g = g.to_crs(CRS_METRIC)

            for _, r in g.iterrows():
                ags5 = extract_ags5(r)
                if not ags5:
                    continue

                lab = None
                for nm in NAME_FIELDS:
                    if nm in r and pd.notna(r[nm]):
                        lab = clean_kreis_label(r[nm])
                        break

                acc = centers_acc.setdefault(
                    ags5,
                    {
                        "xs": [],
                        "ys": [],
                        "labels": [],
                        "state_slug": state_slug,
                        "state_name": state_name,
                    },
                )
                acc["xs"].append(r.geometry.x)
                acc["ys"].append(r.geometry.y)
                if lab:
                    acc["labels"].append(lab)

    # ---------- initial centers ----------
    centers = {}

    for ags5, acc in centers_acc.items():
        cx = sum(acc["xs"]) / len(acc["xs"])
        cy = sum(acc["ys"]) / len(acc["ys"])
        pt = Point(cx, cy)

        cand = list(sidx.query(pt, predicate="contains"))
        if cand:
            idx = min(cand, key=lambda i: g_polys_m.iloc[i]["area"])
        else:
            idx = g_polys_m.geometry.distance(pt).idxmin()

        poly = g_polys_m.iloc[idx].geometry
        area = g_polys_m.iloc[idx]["area"]

        if not pt.within(poly):
            pt = poly.representative_point()

        centers[ags5] = {
            "point": pt,
            "polygon": poly,
            "area": area,
            "kreis_name": choose_label(acc["labels"]) or ags5,
        }

    # ---------- nested conflict resolution ----------
    for it in range(MAX_GLOBAL_ITER):
        changed = False
        for ags5, c in centers.items():
            pt = c["point"]
            poly = c["polygon"]
            area = c["area"]

            cand = list(sidx.query(pt, predicate="contains"))
            for idx in cand:
                other_poly = g_polys_m.iloc[idx].geometry
                other_area = g_polys_m.iloc[idx]["area"]

                if pt.within(other_poly) and other_area < area:
                    c["point"] = shift_inward(poly)
                    changed = True
                    if DEBUG_PRINT:
                        print(f"[NESTED SHIFT] {c['kreis_name']} (AGS={ags5})")
                    break
        if not changed:
            break

    # ---------- border proximity pull ----------
    for ags5, c in centers.items():
        pt = c["point"]
        poly = c["polygon"]

        dist = pt.distance(poly.boundary)
        if dist < BORDER_THRESHOLD_M:
            c["point"] = shift_inward(poly)
            if DEBUG_PRINT:
                print(
                    f"[BORDER PULL] {c['kreis_name']} (AGS={ags5}) "
                    f"dist_to_border={int(dist)} m"
                )

    # ---------- write output ----------
    rows = []
    for ags5, c in centers.items():
        acc = centers_acc[ags5]
        rows.append(
            {
                "ags5": ags5,
                "kreis_key": ags5,
                "kreis_name": c["kreis_name"],
                "state_slug": acc["state_slug"],
                "state_name": acc["state_name"],
                "geometry": c["point"],
            }
        )

    g_out = gpd.GeoDataFrame(rows, geometry="geometry", crs=CRS_METRIC).to_crs(CRS_OUTPUT)
    CENTERS_DIR.mkdir(parents=True, exist_ok=True)
    g_out.to_file(CENTERS_PATH, driver="GeoJSON")

    print(f"\n[OK] Wrote {CENTERS_PATH} ({len(g_out)} centers)")


if __name__ == "__main__":
    main()
