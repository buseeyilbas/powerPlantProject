
"""
step21_filter_json_by_state_3checks_yearly.py

Like step20, but split outputs by commissioning year (DATE_FIELD).
Output structure (keeps original filenames):
  <OUTPUT_ROOT>/<PrettyState>/<YYYY>/<original_filename>.json

Entries are saved ONLY if polygon state == Bundesland (code) == Gemeinde prefix (2-digit).
"""

import os
import json
from collections import defaultdict
from typing import Dict, Optional, Tuple, List
from shapely.geometry import shape, MultiPolygon, Polygon, Point

# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_ROOT  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_state_yearly_3checks"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # features[].properties.name
DATE_FIELD = "Inbetriebnahmedatum"
LON_FIELD = "Laengengrad"
LAT_FIELD = "Breitengrad"
# ============================

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

def normalize_state_name(name: str) -> str:
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

def parse_point(entry: dict) -> Optional[Point]:
    try:
        lon = float(str(entry.get(LON_FIELD, "")).replace(",", "."))
        lat = float(str(entry.get(LAT_FIELD, "")).replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return Point(lon, lat)
    except Exception:
        return None

def extract_year(entry: dict, field: str = DATE_FIELD) -> str:
    val = str(entry.get(field, "") or "").strip()
    y = val[:4]
    return y if y.isdigit() and len(y) == 4 else "unknown"

def load_state_polygons(geojson_path: str):
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    polygons_by_norm: Dict[str, MultiPolygon] = {}
    pretty_by_norm: Dict[str, str] = {}

    for feat in feats:
        props = feat.get("properties", {}) or {}
        name = props.get("name")
        if not name:
            continue
        geom = shape(feat.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue
        key = normalize_state_name(name)
        polygons_by_norm[key] = geom
        pretty_by_norm[key] = name
    return polygons_by_norm, pretty_by_norm

def polygon_state_of_point(pt: Point, polygons_by_norm: Dict[str, MultiPolygon]) -> Optional[str]:
    for norm, mp in polygons_by_norm.items():
        if mp.covers(pt):
            return norm
    return None

def bl_code_to_norm_name(code: str) -> Optional[str]:
    if code is None: return None
    name = BUNDESLAND_CODE_TO_NAME.get(str(code).strip())
    return normalize_state_name(name) if name else None

def gs_prefix_to_norm_name(gs: str) -> Optional[str]:
    if gs is None: return None
    s = str(gs)
    if len(s) < 2:
        return None
    name = GS_PREFIX_TO_NAME.get(s[:2])
    return normalize_state_name(name) if name else None

def filter_json_by_state_year_three_checks(
    input_folder: str,
    output_root: str,
    polygon_states_path: str,
    date_field: str = DATE_FIELD
):
    os.makedirs(output_root, exist_ok=True)

    polygons_by_norm, pretty_by_norm = load_state_polygons(polygon_states_path)
    if not polygons_by_norm:
        raise RuntimeError("No state polygons loaded.")

    # Stats
    total_files = 0
    total_entries = 0
    kept_entries = 0
    dropped_no_poly = 0
    dropped_missing_bl = 0
    dropped_missing_gs = 0
    dropped_mismatch = 0

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

        # Buckets for this source file
        buckets: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))

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
                year = extract_year(entry, date_field)
                buckets[poly_state_norm][year].append(entry)
                kept_entries += 1
            else:
                dropped_mismatch += 1

        # Write outputs grouped by state/year
        for state_norm, years_map in buckets.items():
            pretty_state = pretty_by_norm.get(state_norm, state_norm)
            for year, entries in years_map.items():
                out_folder = os.path.join(output_root, pretty_state, year)
                os.makedirs(out_folder, exist_ok=True)
                out_path = os.path.join(out_folder, fname)
                save_json(entries, out_path)
                print(f"✔ Saved {len(entries):>5} entries → {pretty_state}/{year}/{fname}")

    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "kept_entries": kept_entries,
        "dropped_no_polygon_match": dropped_no_poly,
        "dropped_missing_bundesland": dropped_missing_bl,
        "dropped_missing_gemeindeschluessel": dropped_missing_gs,
        "dropped_triple_mismatch": dropped_mismatch,
        "output_root": output_root,
        "date_field": date_field,
    }
    with open(os.path.join(output_root, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n====== SUMMARY ======")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    filter_json_by_state_year_three_checks(INPUT_FOLDER, OUTPUT_ROOT, POLYGON_STATES_PATH, DATE_FIELD)
