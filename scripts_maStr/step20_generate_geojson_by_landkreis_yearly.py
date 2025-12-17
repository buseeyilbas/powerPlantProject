# # Filename: step20_generate_geojson_by_landkreis_yearly.py
# # Purpose:
# #   EXACT SAME LOGIC as step18_generate_geojson_by_state_landkreis_yearly.py
# #   BUT:
# #     - NO state-level folders
# #     - Nationwide → grouped ONLY by Landkreis and Year
# #
# # Output:
# #   <OUTPUT_ROOT>/<LANDKREIS>/<YYYY>.geojson
# #   + _landkreis_yearly_summary.json

# import os
# import re
# import json
# from collections import defaultdict
# from typing import Dict, List, Tuple, Optional

# from shapely.geometry import shape, MultiPolygon, Polygon, Point
# from shapely.prepared import prep


# # ========== CONFIG ==========
# INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
# OUTPUT_ROOT  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis_yearly"
# GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"

# LON_FIELD  = "Laengengrad"
# LAT_FIELD  = "Breitengrad"
# DATE_FIELD = "Inbetriebnahmedatum"
# # ============================


# # ---------- I/O helpers ----------

# def load_json(path: str):
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)


# def safe_filename(name: str) -> str:
#     """
#     SAME AS step18.
#     """
#     name = (name or "").strip()
#     name = name.replace("/", "_").replace("\\", "_")
#     name = re.sub(r"[^0-9A-Za-zÄÖÜäöüß \-_.]", "_", name)
#     name = re.sub(r"_+", "_", name)
#     return name or "unknown"


# # ---------- Geometry helpers ----------

# def parse_point(entry: dict) -> Optional[Point]:
#     try:
#         lon = float(str(entry.get(LON_FIELD, "")).replace(",", "."))
#         lat = float(str(entry.get(LAT_FIELD, "")).replace(",", "."))
#         if not (-90 <= lat <= 90 and -180 <= lon <= 180):
#             return None
#         return Point(lon, lat)
#     except Exception:
#         return None


# def load_gadm_l2_polygons(path: str) -> List[Tuple[str, MultiPolygon]]:
#     data = load_json(path)
#     feats = data["features"] if "features" in data else data

#     out = []
#     for f in feats:
#         props = f.get("properties", {})
#         lkr = props.get("NAME_2")
#         if not lkr:
#             continue

#         geom = shape(f.get("geometry"))
#         if isinstance(geom, Polygon):
#             geom = MultiPolygon([geom])
#         if not isinstance(geom, MultiPolygon):
#             continue

#         out.append((lkr, geom))
#     return out


# # ---------- Feature helpers ----------

# def to_feature(entry: dict, pt: Point) -> dict:
#     props = {k: v for k, v in entry.items() if k not in [LON_FIELD, LAT_FIELD]}
#     return {
#         "type": "Feature",
#         "geometry": {"type": "Point", "coordinates": [pt.x, pt.y]},
#         "properties": props,
#     }


# def extract_year(entry: dict) -> str:
#     val = str(entry.get(DATE_FIELD, "") or "").strip()
#     if len(val) >= 4 and val[:4].isdigit():
#         return val[:4]
#     return "unknown"


# # ---------- MAIN ----------

# def convert_landkreis_yearly():
#     os.makedirs(OUTPUT_ROOT, exist_ok=True)

#     l2_polys = load_gadm_l2_polygons(GADM_L2_PATH)
#     if not l2_polys:
#         raise RuntimeError("No GADM Level-2 polygons loaded.")

#     prepared = [(name, prep(geom)) for name, geom in l2_polys]

#     # {landkreis: {year: [features]}}
#     buckets: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))

#     stats = {
#         "files_processed": 0,
#         "entries_seen": 0,
#         "matched_entries": 0,
#         "unmatched_entries": 0,
#         "unmatched_samples_first_200": [],
#     }

#     for root, _, files in os.walk(INPUT_FOLDER):
#         for fn in files:
#             if not fn.endswith(".json"):
#                 continue

#             stats["files_processed"] += 1
#             path = os.path.join(root, fn)

#             try:
#                 data = load_json(path)
#             except Exception as e:
#                 print(f"⚠️ Could not load {fn}: {e}")
#                 continue

#             for entry in data:
#                 stats["entries_seen"] += 1
#                 pt = parse_point(entry)
#                 if pt is None:
#                     continue

#                 matched = False
#                 for lkr_name, pgeom in prepared:
#                     if (
#                         pgeom.context.covers(pt)
#                         if hasattr(pgeom, "context") and hasattr(pgeom.context, "covers")
#                         else pgeom.contains(pt)
#                     ):
#                         year = extract_year(entry)
#                         feat = to_feature(entry, pt)
#                         buckets[lkr_name][year].append(feat)
#                         stats["matched_entries"] += 1
#                         matched = True
#                         break

#                 if not matched:
#                     stats["unmatched_entries"] += 1
#                     if len(stats["unmatched_samples_first_200"]) < 200:
#                         stats["unmatched_samples_first_200"].append({
#                             "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
#                             "coords": [pt.x, pt.y],
#                         })

#     # ---------- WRITE ----------
#     for lkr, year_map in buckets.items():
#         lkr_dir = os.path.join(OUTPUT_ROOT, safe_filename(lkr))
#         os.makedirs(lkr_dir, exist_ok=True)

#         for year, feats in year_map.items():
#             if not feats:
#                 continue

#             out_path = os.path.join(lkr_dir, f"{year}.geojson")
#             with open(out_path, "w", encoding="utf-8") as f:
#                 json.dump(
#                     {"type": "FeatureCollection", "features": feats},
#                     f,
#                     ensure_ascii=False,
#                     indent=2,
#                 )

#             print(f"✅ Saved {len(feats):5d} features → {lkr}/{year}.geojson")

#     stats["output_root"] = OUTPUT_ROOT
#     stats["gadm_l2_path"] = GADM_L2_PATH
#     stats["date_field"] = DATE_FIELD

#     summary_path = os.path.join(OUTPUT_ROOT, "_landkreis_yearly_summary.json")
#     with open(summary_path, "w", encoding="utf-8") as f:
#         json.dump(stats, f, ensure_ascii=False, indent=2)

#     print("\n====== SUMMARY ======")
#     print(json.dumps(stats, indent=2, ensure_ascii=False))


# if __name__ == "__main__":
#     convert_landkreis_yearly()


# Filename: step20_generate_geojson_by_landkreis_yearly.py
# Purpose:
#   Nationwide → Landkreis → Year GeoJSON export
#   WITH strict 3-check consistency gate:
#     1) State polygon
#     2) Bundesland code
#     3) Gemeindeschluessel prefix
#
# Output:
#   <OUTPUT_ROOT>/<LANDKREIS>/<YEAR>.geojson
#   + _landkreis_yearly_summary.json

import os
import re
import json
from collections import defaultdict
from typing import Dict, List, Optional

from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep


# ================= CONFIG =================
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_ROOT  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis_yearly"

GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"

LON_FIELD  = "Laengengrad"
LAT_FIELD  = "Breitengrad"
DATE_FIELD = "Inbetriebnahmedatum"
# =========================================


# ---------- Bundesland / GS mappings (SAME AS STEP 16 / 18) ----------

BUNDESLAND_CODE_TO_NAME: Dict[str, str] = {
    "1400": "brandenburg",
    "1401": "berlin",
    "1402": "baden_wuerttemberg",
    "1403": "bayern",
    "1404": "bremen",
    "1405": "hessen",
    "1406": "hamburg",
    "1407": "mecklenburg_vorpommern",
    "1408": "niedersachsen",
    "1409": "nordrhein_westfalen",
    "1410": "rheinland_pfalz",
    "1411": "schleswig_holstein",
    "1412": "saarland",
    "1413": "sachsen",
    "1414": "sachsen_anhalt",
    "1415": "thueringen",
}

GS_PREFIX_TO_NAME: Dict[str, str] = {
    "01": "schleswig_holstein",
    "02": "hamburg",
    "03": "niedersachsen",
    "04": "bremen",
    "05": "nordrhein_westfalen",
    "06": "hessen",
    "07": "rheinland_pfalz",
    "08": "baden_wuerttemberg",
    "09": "bayern",
    "10": "saarland",
    "11": "berlin",
    "12": "brandenburg",
    "13": "mecklenburg_vorpommern",
    "14": "sachsen",
    "15": "sachsen_anhalt",
    "16": "thueringen",
}


# ---------- Helpers ----------

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_state_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = (s.replace("ä", "ae")
           .replace("ö", "oe")
           .replace("ü", "ue")
           .replace("ß", "ss"))
    for ch in [" ", "_", "-", "(", ")", "[", "]", "{", "}", ".", ",", "'", '"', "/"]:
        s = s.replace(ch, "")
    return s


def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^0-9A-Za-zÄÖÜäöüß \-_.]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name or "unknown"


def parse_point(entry: dict) -> Optional[Point]:
    try:
        lon = float(str(entry.get(LON_FIELD, "")).replace(",", "."))
        lat = float(str(entry.get(LAT_FIELD, "")).replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return Point(lon, lat)
    except Exception:
        return None


def extract_year(entry: dict) -> str:
    val = str(entry.get(DATE_FIELD, "") or "").strip()
    return val[:4] if len(val) >= 4 and val[:4].isdigit() else "unknown"


def to_feature(entry: dict, pt: Point) -> dict:
    props = {k: v for k, v in entry.items() if k not in [LON_FIELD, LAT_FIELD]}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [pt.x, pt.y]},
        "properties": props,
    }


# ---------- State polygon helpers (FROM STEP 16) ----------

def load_state_polygons(path: str):
    data = load_json(path)
    feats = data["features"] if "features" in data else data

    polygons = {}

    for f in feats:
        props = f.get("properties", {})
        name = props.get("name")
        if not name:
            continue

        geom = shape(f.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue

        polygons[normalize_state_name(name)] = geom

    return polygons


def polygon_state_of_point(pt: Point, polygons: Dict[str, MultiPolygon]) -> Optional[str]:
    for state_norm, mp in polygons.items():
        if mp.covers(pt):
            return state_norm
    return None


def bl_code_to_norm_name(code: str) -> Optional[str]:
    if not isinstance(code, str):
        code = str(code)
    name = BUNDESLAND_CODE_TO_NAME.get(code.strip())
    return normalize_state_name(name) if name else None


def gs_prefix_to_norm_name(gs: str) -> Optional[str]:
    if not isinstance(gs, str):
        gs = str(gs)
    if len(gs) < 2:
        return None
    name = GS_PREFIX_TO_NAME.get(gs[:2])
    return normalize_state_name(name) if name else None


# ---------- GADM L2 ----------

def load_gadm_l2_polygons(path: str):
    data = load_json(path)
    feats = data["features"] if "features" in data else data

    out = []
    for f in feats:
        props = f.get("properties", {})
        lkr = props.get("NAME_2")
        if not lkr:
            continue

        geom = shape(f.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue

        out.append((lkr, prep(geom)))

    return out


# ---------- MAIN ----------

def convert_landkreis_yearly():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    state_polys = load_state_polygons(POLYGON_STATES_PATH)
    l2_polys = load_gadm_l2_polygons(GADM_L2_PATH)

    buckets = defaultdict(lambda: defaultdict(list))

    stats = {
        "entries_seen": 0,
        "passed_3check": 0,
        "matched_entries": 0,
        "skipped_inconsistent": 0,
    }

    for root, _, files in os.walk(INPUT_FOLDER):
        for fn in files:
            if not fn.endswith(".json"):
                continue

            data = load_json(os.path.join(root, fn))

            for entry in data:
                stats["entries_seen"] += 1

                pt = parse_point(entry)
                if pt is None:
                    continue

                poly_state = polygon_state_of_point(pt, state_polys)
                bl_norm = bl_code_to_norm_name(entry.get("Bundesland"))
                gs_norm = gs_prefix_to_norm_name(entry.get("Gemeindeschluessel"))

                if not poly_state or not bl_norm or not gs_norm:
                    stats["skipped_inconsistent"] += 1
                    continue

                if not (poly_state == bl_norm == gs_norm):
                    stats["skipped_inconsistent"] += 1
                    continue

                stats["passed_3check"] += 1

                for lkr_name, pgeom in l2_polys:
                    if pgeom.context.covers(pt):
                        year = extract_year(entry)
                        feat = to_feature(entry, pt)
                        buckets[lkr_name][year].append(feat)
                        stats["matched_entries"] += 1
                        break

    # ---------- WRITE ----------
    for lkr, year_map in buckets.items():
        lkr_dir = os.path.join(OUTPUT_ROOT, safe_filename(lkr))
        os.makedirs(lkr_dir, exist_ok=True)

        for year, feats in year_map.items():
            if not feats:
                continue

            with open(os.path.join(lkr_dir, f"{year}.geojson"), "w", encoding="utf-8") as f:
                json.dump(
                    {"type": "FeatureCollection", "features": feats},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

    with open(os.path.join(OUTPUT_ROOT, "_landkreis_yearly_summary.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("DONE:", json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    convert_landkreis_yearly()
