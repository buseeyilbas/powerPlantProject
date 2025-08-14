# generate_geojson_by_landkreis_from_valid_json.py
# Purpose: Scan all JSON files under INPUT_FOLDER, convert entries to points,
#          assign each to a Landkreis/Kreisfreie Stadt from GADM L2 polygons,
#          and write one GeoJSON per Landkreis. Unmatched points go to _unmatched.geojson.

import os
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import shape, Point, Polygon, MultiPolygon, box
from shapely.prepared import prep

from rapidfuzz import process, fuzz

# ------------------ CONFIG ------------------
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
OUTPUT_DIR   = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis"
FILTER_NAME_1: Optional[str] = None
# -------------------------------------------

def slugify(value: str) -> str:
    pairs = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
             ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"))
    for a, b in pairs:
        value = value.replace(a, b)
    value = re.sub(r"[^\w\s\-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[-\s]+", "-", value).strip("-_").lower()
    return value or "unknown"

def normalize_landkreis_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\b(lk|kreis|krs|stadt|region|landkreis)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

def fallback_name_contains(name2_input: str, gadm_names: List[str]) -> Optional[str]:
    norm_input = normalize_landkreis_name(name2_input)
    for gadm_name in gadm_names:
        if normalize_landkreis_name(gadm_name) in norm_input or norm_input in normalize_landkreis_name(gadm_name):
            print(f"🔍 Fallback match (contains): '{name2_input}' → '{gadm_name}'")
            return gadm_name
    print(f"❌ No fallback match for: {name2_input}")
    return None

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def load_gadm_l2(gadm_path: str, filter_name_1: Optional[str]) -> List[Dict[str, Any]]:
    with open(gadm_path, encoding="utf-8") as f:
        data = json.load(f)

    feats = data["features"] if isinstance(data, dict) and "features" in data else data
    out: List[Dict[str, Any]] = []
    for ft in feats:
        props = ft.get("properties") or {}
        name_1 = props.get("NAME_1")
        name_2 = props.get("NAME_2")
        cc_2   = props.get("CC_2")

        if filter_name_1 and name_1 != filter_name_1:
            continue

        geom = shape(ft.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, (Polygon, MultiPolygon)):
            continue

        minx, miny, maxx, maxy = geom.bounds
        out.append({
            "name_1": name_1,
            "name_2": name_2,
            "cc_2": cc_2,
            "geom": geom,
            "bbox": (minx, miny, maxx, maxy),
        })
    return out

def parse_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip().replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None
    return None

def extract_point(entry: Dict[str, Any]) -> Optional[Point]:
    lon = parse_float(entry.get("Laengengrad"))
    lat = parse_float(entry.get("Breitengrad"))
    if lon is None or lat is None:
        for lk, bk in (("longitude","latitude"), ("lon","lat"), ("x","y"), ("LONGITUDE","LATITUDE"), ("Lon","Lat")):
            lon2 = parse_float(entry.get(lk))
            lat2 = parse_float(entry.get(bk))
            if lon2 is not None and lat2 is not None:
                lon, lat = lon2, lat2
                break
    if lon is None or lat is None:
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return Point(lon, lat)

def bbox_contains(bbox: Tuple[float,float,float,float], x: float, y: float) -> bool:
    minx, miny, maxx, maxy = bbox
    return (minx <= x <= maxx) and (miny <= y <= maxy)

def write_feature_collection(path: str, features: List[Dict[str, Any]]) -> None:
    ensure_dir(os.path.dirname(path))
    payload = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

def main():
    landkreise = load_gadm_l2(GADM_L2_PATH, FILTER_NAME_1)
    if not landkreise:
        print("❌ No polygons loaded. Check GADM_L2_PATH or FILTER_NAME_1.")
        return

    gadm_name2_list = [lk["name_2"] for lk in landkreise]
    buckets: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    unmatched: List[Dict[str, Any]] = []

    total_files = 0
    matched_count = 0
    unmatched_count = 0
    fallback_count = 0

    for root, _, files in os.walk(INPUT_FOLDER):
        for fname in files:
            if not fname.lower().endswith(".json"):
                continue
            total_files += 1
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load {fname}: {e}")
                continue

            if not isinstance(data, list):
                continue

            for entry in data:
                pt = extract_point(entry)
                if pt is None:
                    unmatched.append({"type":"Feature","geometry":None,"properties":entry})
                    unmatched_count += 1
                    continue

                x, y = pt.x, pt.y
                found = None
                for rec in landkreise:
                    if not bbox_contains(rec["bbox"], x, y):
                        continue
                    if rec["geom"].covers(pt):
                        found = rec
                        break

                raw_lk = str(entry.get("Landkreis", "")).strip()
                if found is None and raw_lk:
                    fallback_name = fallback_name_contains(raw_lk, gadm_name2_list)
                    if fallback_name:
                        for rec in landkreise:
                            if rec["name_2"] == fallback_name:
                                found = rec
                                fallback_count += 1
                                break

                if found is None:
                    unmatched.append({
                        "type":"Feature",
                        "geometry":{"type":"Point","coordinates":[x, y]},
                        "properties":entry
                    })
                    unmatched_count += 1
                    continue

                props = {k: v for k, v in entry.items() if k not in ("Laengengrad","Breitengrad")}
                props.update({
                    "ASSIGNED_NAME_1": found["name_1"],
                    "ASSIGNED_NAME_2": found["name_2"],
                    "ASSIGNED_CC_2": found["cc_2"],
                })

                feature = {
                    "type": "Feature",
                    "geometry": {"type":"Point","coordinates":[x, y]},
                    "properties": props
                }

                key = (found["name_1"] or "Unknown_State",
                       found["name_2"] or "Unknown_Landkreis",
                       found["cc_2"] or "UNKNOWN")
                buckets[key].append(feature)
                matched_count += 1

    for (state_name, lk_name, cc2), feats in buckets.items():
        state_slug = slugify(state_name)
        lk_slug = slugify(lk_name)
        lk_folder = os.path.join(OUTPUT_DIR, state_slug, f"{cc2}_{lk_slug}")
        out_path = os.path.join(lk_folder, "features.geojson")
        write_feature_collection(out_path, feats)
        print(f"✅ {len(feats):>6} -> {out_path}")

    unmatched_path = os.path.join(OUTPUT_DIR, "_unmatched.geojson")
    write_feature_collection(unmatched_path, unmatched)

    print("\n—— Summary ——")
    print(f"Processed JSON files : {total_files}")
    print(f"Matched features     : {matched_count}")
    print(f"Fallback matched     : {fallback_count}")
    print(f"Unmatched features   : {unmatched_count} -> {unmatched_path}")
    print(f"States written       : {len(set(k[0] for k in buckets.keys()))}")
    print(f"Landkreise written   : {len(buckets)} -> {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
