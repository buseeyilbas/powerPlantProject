
"""
step25_filter_json_by_landkreis.py

Group entries by Landkreis using GADM L2 polygons and save raw JSONs.
We enforce STATE-level "3 checks" to avoid misclassified entries:
  polygon STATE (NAME_1) == Bundesland code == Gemeindeschluessel prefix.

Output structure (keeps original filenames):
  <OUTPUT_BASE>/<Landkreis NAME_2>__<State NAME_1>/<original_filename>.json
This naming avoids collisions between identically named Landkreise in different states.
"""

import os
import re
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep

# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_BASE  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_landkreis"
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"  # expects NAME_1 and NAME_2
LON_FIELD    = "Laengengrad"
LAT_FIELD    = "Breitengrad"
# ===========================

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

def safe_filename(name: str) -> str:
    name = (name or "").strip().lower()
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^0-9a-zäöüß \-_.]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name or "unknown"

def normalize_state_name_token(name: str) -> str:
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

def load_gadm_l2(geojson_path: str) -> List[Tuple[str, str, MultiPolygon]]:
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
        out.append((name_1, name_2, geom))
    return out

def bl_code_to_norm_name(code: str) -> Optional[str]:
    if code is None: return None
    name = BUNDESLAND_CODE_TO_NAME.get(str(code).strip())
    return normalize_state_name_token(name) if name else None

def gs_prefix_to_norm_name(gs: str) -> Optional[str]:
    if gs is None: return None
    s = str(gs)
    if len(s) < 2:
        return None
    name = GS_PREFIX_TO_NAME.get(s[:2])
    return normalize_state_name_token(name) if name else None

def filter_json_by_landkreis(
    input_folder: str,
    output_base: str,
    gadm_l2_path: str
):
    os.makedirs(output_base, exist_ok=True)

    l2 = load_gadm_l2(gadm_l2_path)
    if not l2:
        raise RuntimeError("No L2 polygons loaded.")
    prepared = [(name_1, name_2, prep(geom)) for (name_1, name_2, geom) in l2]

    total_files = 0
    total_entries = 0
    kept_entries = 0
    dropped_mismatch = 0
    dropped_no_match = 0
    dropped_missing_bl = 0
    dropped_missing_gs = 0

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

        # buckets: {"<Landkreis>__<State>": [entries]}
        buckets: Dict[str, List[dict]] = defaultdict(list)

        for entry in data:
            total_entries += 1
            pt = parse_point(entry)
            if pt is None:
                continue

            matched_state = None
            matched_lk = None
            for name_1, name_2, pgeom in prepared:
                if pgeom.context.covers(pt) if hasattr(pgeom, "context") and hasattr(pgeom.context, "covers") else pgeom.contains(pt):
                    matched_state = name_1
                    matched_lk = name_2
                    break
            if not matched_state:
                dropped_no_match += 1
                continue

            bl_norm = bl_code_to_norm_name(entry.get("Bundesland"))
            if bl_norm is None:
                dropped_missing_bl += 1
                continue

            gs_norm = gs_prefix_to_norm_name(entry.get("Gemeindeschluessel"))
            if gs_norm is None:
                dropped_missing_gs += 1
                continue

            if normalize_state_name_token(matched_state) == bl_norm == gs_norm:
                key = f"{matched_lk}__{matched_state}"
                out_folder = os.path.join(output_base, safe_filename(key))
                os.makedirs(out_folder, exist_ok=True)
                buckets[key].append(entry)
                kept_entries += 1
            else:
                dropped_mismatch += 1

        # write one file per key for this source file
        for key, entries in buckets.items():
            out_folder = os.path.join(output_base, safe_filename(key))
            os.makedirs(out_folder, exist_ok=True)
            out_path = os.path.join(out_folder, fname)
            save_json(entries, out_path)
            print(f"✔ Saved {len(entries):>5} entries → {safe_filename(key)}/{fname}")

    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "kept_entries": kept_entries,
        "dropped_no_polygon_match": dropped_no_match,
        "dropped_missing_bundesland": dropped_missing_bl,
        "dropped_missing_gemeindeschluessel": dropped_missing_gs,
        "dropped_state_triple_mismatch": dropped_mismatch,
        "output_base": output_base,
    }
    with open(os.path.join(output_base, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n====== SUMMARY ======")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    filter_json_by_landkreis(INPUT_FOLDER, OUTPUT_BASE, GADM_L2_PATH)
