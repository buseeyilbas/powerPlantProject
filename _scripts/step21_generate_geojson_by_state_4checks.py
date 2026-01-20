# step15_generate_geojson_by_state_4checks.py
# Updated: add 4th check -> entry must match a Landkreis (GADM L2) polygon as well.
#
# 4th check logic is inspired by step17_generate_geojson_by_state_landkreis.py:
# - Load GADM L2 polygons, prepare geometries (prep)
# - For each point, require that it falls into at least one Landkreis polygon (covers/contains fallback)

import os
import json
import re
from collections import defaultdict
from typing import Dict, Optional, List, Tuple

from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep


# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_4_checks"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # properties.name expected

# 4th check: Landkreis polygon source (GADM level 2)
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"  # expects properties.NAME_1 and properties.NAME_2
# ============================

LON_FIELD = "Laengengrad"
LAT_FIELD = "Breitengrad"


# ---- Bundesland (1400–1415) => canonical state name ----
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

# ---- Gemeindeschlüssel 2-digit prefix => canonical state name ----
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

def normalize_state_name(name: str) -> str:
    """Normalize state names to compare robustly across sources."""
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    for ch in [" ", "_", "-", "(", ")", "[", "]", "{", "}", ".", ",", "'", '"', "/"]:
        s = s.replace(ch, "")
    return s


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_point(entry: dict) -> Optional[Point]:
    """
    Parse lon/lat from 'Laengengrad'/'Breitengrad' and return a shapely Point.
    Accepts comma decimal separators as in original data.
    """
    try:
        lon_raw = entry.get(LON_FIELD, "")
        lat_raw = entry.get(LAT_FIELD, "")
        lon = float(str(lon_raw).replace(",", "."))
        lat = float(str(lat_raw).replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return Point(lon, lat)
    except Exception:
        return None


def load_state_polygons(geojson_path: str) -> Dict[str, MultiPolygon]:
    """
    Read state polygons and return {normalized_state_name: MultiPolygon}.
    Expects each feature to have properties.name and a Polygon/MultiPolygon geometry.
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    out: Dict[str, MultiPolygon] = {}
    for feat in feats:
        props = feat.get("properties", {}) or {}
        state_name = props.get("name")
        if not state_name:
            continue

        geom = shape(feat.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue

        out[normalize_state_name(state_name)] = geom

    return out


def polygon_state_of_point(point: Point, polygons: Dict[str, MultiPolygon]) -> Optional[str]:
    """
    Determine which state's polygon covers the point. Returns the *normalized* state name.
    Uses 'covers' so boundary points are included.
    """
    for norm_name, mp in polygons.items():
        if mp.covers(point):
            return norm_name
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


def to_feature(entry: dict, point: Point) -> dict:
    """Build a GeoJSON Feature (Point) from the entry."""
    props = {k: v for k, v in entry.items() if k not in [LON_FIELD, LAT_FIELD]}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        "properties": props,
    }


# ---------- 4th check: Landkreis polygons (inspired by step17) ----------

def load_landkreis_polygons(geojson_path: str) -> List[Tuple[str, str, MultiPolygon]]:
    """
    Load GADM Level-2 polygons (Landkreis).

    Returns list of (name_1, name_2, multipolygon)
      - name_1 = props["NAME_1"]  (State)
      - name_2 = props["NAME_2"]  (Landkreis)
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    out: List[Tuple[str, str, MultiPolygon]] = []
    for feat in feats:
        props = feat.get("properties", {}) or {}
        name_1 = props.get("NAME_1")
        name_2 = props.get("NAME_2")
        if not name_1 or not name_2:
            continue

        geom = shape(feat.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue

        out.append((name_1, name_2, geom))
    return out


def has_any_landkreis_match(pt: Point, prepared_l2) -> bool:
    """
    Step17-style: accept the point only if it falls into at least one Landkreis polygon.
    covers() includes boundary points; if covers not available from prepared context, fallback to contains().
    """
    for _name_1, _name_2, pgeom in prepared_l2:
        if pgeom.covers(pt) if hasattr(pgeom.context, "covers") else pgeom.contains(pt):
            return True
    return False


# ---------- Main ----------

def convert_with_4_checks(
    input_folder: str,
    output_folder: str,
    polygon_states_path: str,
    gadm_l2_path: str
):
    os.makedirs(output_folder, exist_ok=True)

    # Load state polygons once
    state_polygons = load_state_polygons(polygon_states_path)
    if not state_polygons:
        raise RuntimeError("No state polygons loaded. Check POLYGON_STATES_PATH and properties.name field.")

    # Load Landkreis polygons once (prepared, step17-style)
    l2 = load_landkreis_polygons(gadm_l2_path)
    if not l2:
        raise RuntimeError("No Landkreis (GADM L2) polygons loaded. Check GADM_L2_PATH and NAME_1/NAME_2 fields.")
    prepared_l2 = [(name_1, name_2, prep(geom)) for (name_1, name_2, geom) in l2]

    # Group consistent features by polygon state (normalized name)
    grouped: Dict[str, list] = defaultdict(list)

    # Counters/logs
    total_files = 0
    total_entries = 0
    consistent = 0

    no_poly = 0
    bl_missing = 0
    gs_missing = 0
    bl_mismatch = 0
    gs_mismatch = 0

    # NEW: 4th check counter
    no_landkreis_match = 0

    mismatch_samples = []

    for root, _, files in os.walk(input_folder):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            total_files += 1
            fpath = os.path.join(root, fname)

            try:
                data = load_json(fpath)
            except Exception as e:
                print(f"⚠️ Could not load {fname}: {e}")
                continue

            for entry in data:
                total_entries += 1
                pt = parse_point(entry)
                if pt is None:
                    continue

                poly_state_norm = polygon_state_of_point(pt, state_polygons)
                if not poly_state_norm:
                    no_poly += 1
                    continue

                bl_code = entry.get("Bundesland")
                bl_norm = bl_code_to_norm_name(bl_code) if bl_code is not None else None
                if bl_norm is None:
                    bl_missing += 1
                    mismatch_samples.append({
                        "reason": "bundesland_missing_or_unmapped",
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
                    })
                    continue

                gs = entry.get("Gemeindeschluessel")
                gs_norm = gs_prefix_to_norm_name(gs) if gs is not None else None
                if gs_norm is None:
                    gs_missing += 1
                    mismatch_samples.append({
                        "reason": "gemeindeschluessel_missing_or_unmapped",
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
                    })
                    continue

                # 3-check: polygon == Bundesland == Gemeindeschlüssel
                if poly_state_norm == bl_norm == gs_norm:
                    # 4th check: must also match a Landkreis polygon
                    if not has_any_landkreis_match(pt, prepared_l2):
                        no_landkreis_match += 1
                        continue

                    grouped[poly_state_norm].append(to_feature(entry, pt))
                    consistent += 1
                else:
                    if poly_state_norm != bl_norm:
                        bl_mismatch += 1
                    if poly_state_norm != gs_norm or bl_norm != gs_norm:
                        gs_mismatch += 1
                    mismatch_samples.append({
                        "reason": "triple_mismatch",
                        "poly_state": poly_state_norm,
                        "bl": bl_norm,
                        "gs": gs_norm,
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
                    })

    # Write one GeoJSON per state
    for state_norm, feats in grouped.items():
        if not feats:
            continue
        out_path = os.path.join(output_folder, f"{state_norm}.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {len(feats)} consistent features to {out_path}")

    # Summary
    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "consistent": consistent,
        "no_polygon_match": no_poly,
        "no_landkreis_match": no_landkreis_match,  # NEW
        "bundesland_missing_or_unmapped": bl_missing,
        "gemeindeschluessel_missing_or_unmapped": gs_missing,
        "bundesland_mismatch_count": bl_mismatch,
        "gemeindeschluessel_mismatch_count": gs_mismatch,
        "mismatch_samples_first_200": mismatch_samples[:200],
        "polygon_states_path": polygon_states_path,
        "gadm_l2_path": gadm_l2_path,
    }

    log_path = os.path.join(output_folder, "_consistency_summary.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n====== SUMMARY ======")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    convert_with_4_checks(
        INPUT_FOLDER,
        OUTPUT_FOLDER,
        POLYGON_STATES_PATH,
        GADM_L2_PATH
    )
