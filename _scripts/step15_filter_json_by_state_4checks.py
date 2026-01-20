
"""
step21_filter_json_by_state_4checks.py

Filter raw JSON entries into per-state folders using a strict "4 checks" consistency rule:
  1) Point-in-polygon check against state polygons (from POLYGON_STATES_PATH).
  2) 'Bundesland' numeric code mapped to canonical state name.
  3) 'Gemeindeschluessel' 2-digit prefix mapped to canonical state name.
  4) Point-in-polygon check against Landkreis polygons (from GADM_L2_PATH).

Only entries that pass all four checks (polygon == Bundesland == Gemeindeschluessel) are saved.
Output structure (keeps original filenames per state, like step12 style):
  <OUTPUT_BASE>/<PrettyState>/<original_filename>.json

Notes:
- Coordinates must be under 'Laengengrad' and 'Breitengrad' (comma or dot decimals accepted).
- State polygons GeoJSON must have features with properties.name and Polygon/MultiPolygon geometries.
"""

import os
import json
from collections import defaultdict
from typing import Dict, Optional, Tuple, List
from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep


# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_BASE  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_state_4checks"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # features[].properties.name
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
LON_FIELD = "Laengengrad"
LAT_FIELD = "Breitengrad"
# ============================

# ---- Bundesland (1400–1415) => canonical token ----
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

# ---- Gemeindeschlüssel 2-digit prefix => canonical token ----
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

def load_gadm_l2_prepared(geojson_path: str):
    """
    Load GADM Level-2 polygons and return prepared geometries.
    Each item: (name_1, name_2, prepared_geom)
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    out = []
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

        out.append((name_1, name_2, prep(geom)))
    return out


def has_any_landkreis_match(pt: Point, prepared_l2) -> bool:
    """
    Step17-style: covers() includes boundary points; fallback to contains().
    """
    for _name_1, _name_2, pgeom in prepared_l2:
        if pgeom.context.covers(pt) if hasattr(pgeom, "context") and hasattr(pgeom.context, "covers") else pgeom.contains(pt):
            return True
    return False


def normalize_state_name(name: str) -> str:
    """Normalize labels for robust matching (lowercase, remove separators, handle umlauts/ß)."""
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

def save_json(data, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_point(entry: dict, lon_key: str = LON_FIELD, lat_key: str = LAT_FIELD) -> Optional[Point]:
    """Parse lon/lat strings with dot or comma decimals. Return shapely Point or None if invalid."""
    try:
        lon_raw = entry.get(lon_key, "")
        lat_raw = entry.get(lat_key, "")
        lon = float(str(lon_raw).replace(",", "."))
        lat = float(str(lat_raw).replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return Point(lon, lat)
    except Exception:
        return None

def load_state_polygons(geojson_path: str) -> Tuple[Dict[str, MultiPolygon], Dict[str, str]]:
    """
    Read state polygons and return:
      - polygons_by_norm: {normalized_state_name: MultiPolygon}
      - pretty_by_norm:   {normalized_state_name: original_pretty_name}
    Expects each feature to have properties.name and Polygon/MultiPolygon geometry.
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    polygons_by_norm: Dict[str, MultiPolygon] = {}
    pretty_by_norm: Dict[str, str] = {}

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
        key = normalize_state_name(state_name)
        polygons_by_norm[key] = geom
        pretty_by_norm[key] = state_name
    return polygons_by_norm, pretty_by_norm

def polygon_state_of_point(point: Point, polygons_by_norm: Dict[str, MultiPolygon]) -> Optional[str]:
    """Return normalized state name whose polygon covers the point."""
    for norm_name, mp in polygons_by_norm.items():
        if mp.covers(point):
            return norm_name
    return None

def bl_code_to_norm_name(code: str) -> Optional[str]:
    if code is None:
        return None
    name = BUNDESLAND_CODE_TO_NAME.get(str(code).strip())
    return normalize_state_name(name) if name else None

def gs_prefix_to_norm_name(gs: str) -> Optional[str]:
    if gs is None:
        return None
    s = str(gs)
    if len(s) < 2:
        return None
    name = GS_PREFIX_TO_NAME.get(s[:2])
    return normalize_state_name(name) if name else None

# ---------- Main ----------

def filter_json_by_state_three_checks(
    input_folder: str,
    output_base: str,
    polygon_states_path: str
):
    os.makedirs(output_base, exist_ok=True)

    polygons_by_norm, pretty_by_norm = load_state_polygons(polygon_states_path)
    if not polygons_by_norm:
        raise RuntimeError("No state polygons loaded. Check POLYGON_STATES_PATH and properties.name field.")

    # NEW (4th check): load prepared Landkreis polygons (Step17-style)
    prepared_l2 = load_gadm_l2_prepared(GADM_L2_PATH)
    if not prepared_l2:
        raise RuntimeError("No Landkreis (GADM L2) polygons loaded. Check GADM_L2_PATH and NAME_1/NAME_2 fields.")

    # Stats
    total_files = 0
    total_entries = 0
    kept_entries = 0
    dropped_no_poly = 0
    dropped_missing_bl = 0
    dropped_missing_gs = 0
    dropped_mismatch = 0

    # NEW (4th check): stats counter
    dropped_no_landkreis = 0

    for fname in os.listdir(input_folder):
        if not fname.endswith(".json"):
            continue
        total_files += 1
        fpath = os.path.join(input_folder, fname)

        try:
            data = load_json(fpath)
        except Exception as e:
            print(f"⚠️ Could not load {fname}: {e}")
            continue

        # Local buckets for this source file
        buckets: Dict[str, List[dict]] = defaultdict(list)

        for entry in data:
            total_entries += 1
            pt = parse_point(entry)
            if pt is None:
                continue

            poly_state_norm = polygon_state_of_point(pt, polygons_by_norm)
            if not poly_state_norm:
                dropped_no_poly += 1
                continue

            bl_norm = bl_code_to_norm_name(entry.get("Bundesland"))
            if bl_norm is None:
                dropped_missing_bl += 1
                continue

            gs_norm = gs_prefix_to_norm_name(entry.get("Gemeindeschluessel"))
            if gs_norm is None:
                dropped_missing_gs += 1
                continue

            if poly_state_norm == bl_norm == gs_norm:
                # NEW (4th check): must also match at least one Landkreis polygon
                if not has_any_landkreis_match(pt, prepared_l2):
                    dropped_no_landkreis += 1
                    continue

                buckets[poly_state_norm].append(entry)
                kept_entries += 1
            else:
                dropped_mismatch += 1

        # Write outputs for this source file (one copy under each passing state)
        for state_norm, entries in buckets.items():
            pretty_state = pretty_by_norm.get(state_norm, state_norm)
            out_folder = os.path.join(output_base, pretty_state)
            os.makedirs(out_folder, exist_ok=True)
            out_path = os.path.join(out_folder, fname)
            save_json(entries, out_path)
            print(f"✔ Saved {len(entries):>5} entries → {pretty_state}/{fname}")

    # Write a summary
    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "kept_entries": kept_entries,
        "dropped_no_polygon_match": dropped_no_poly,
        "dropped_missing_bundesland": dropped_missing_bl,
        "dropped_missing_gemeindeschluessel": dropped_missing_gs,
        "dropped_triple_mismatch": dropped_mismatch,

        # NEW (4th check): summary field
        "dropped_no_landkreis_match": dropped_no_landkreis,

        "output_base": output_base,
        "gadm_l2_path": GADM_L2_PATH,
    }

    with open(os.path.join(output_base, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n====== SUMMARY ======")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    filter_json_by_state_three_checks(INPUT_FOLDER, OUTPUT_BASE, POLYGON_STATES_PATH)
