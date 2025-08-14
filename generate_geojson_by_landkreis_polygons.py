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

try:
    from shapely.strtree import STRtree  # Fast spatial index if available
    HAS_STRTREE = True
except Exception:
    HAS_STRTREE = False

# ======== CONFIG ========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"
OUTPUT_DIR   = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis_polygon"
FILTER_NAME_1: Optional[str] = None

# ======== HELPERS ========
def slugify(value: str) -> str:
    tr = (("ä","ae"),("ö","oe"),("ü","ue"),("Ä","Ae"),("Ö","Oe"),("Ü","Ue"),("ß","ss"))
    for a,b in tr:
        value = value.replace(a,b)
    value = re.sub(r"[^\w\s-]", "", value)
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

def load_gadm_l2(gadm_path: str, filter_name_1: Optional[str]=None):
    with open(gadm_path, encoding="utf-8") as f:
        data = json.load(f)

    feats = data["features"] if isinstance(data, dict) and "features" in data else data
    out = []
    for ft in feats:
        props = ft.get("properties", {}) or {}
        n1 = props.get("NAME_1")
        n2 = props.get("NAME_2")
        cc2 = props.get("CC_2")
        if filter_name_1 and n1 != filter_name_1:
            continue

        geom = shape(ft.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, (Polygon, MultiPolygon)):
            continue

        out.append({
            "name_1": n1,
            "name_2": n2,
            "cc_2": cc2,
            "geom": geom,
            "prep": prep(geom)
        })
    return out

def build_index(polys: List[Dict[str, Any]]):
    if not HAS_STRTREE:
        return None, polys, {}
    geoms = [p["geom"] for p in polys]
    tree = STRtree(geoms)
    geom_to_poly = {id(p["geom"]): p for p in polys}
    return tree, polys, geom_to_poly

def extract_point(entry: Dict[str, Any]) -> Optional[Point]:
    def parse_num(obj, key):
        val = obj.get(key)
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.strip().replace(",", ".")
            try:
                return float(val)
            except Exception:
                return None
        return None

    lon = parse_num(entry, "Laengengrad")
    lat = parse_num(entry, "Breitengrad")
    if lon is None or lat is None:
        for lk, bk in (("longitude","latitude"), ("lon","lat"), ("x","y"), ("LONGITUDE","LATITUDE"), ("Lon","Lat")):
            lon2 = parse_num(entry, lk)
            lat2 = parse_num(entry, bk)
            if lon2 is not None and lat2 is not None:
                lon, lat = lon2, lat2
                break

    if lon is None or lat is None:
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return Point(lon, lat)

def assign_landkreis(pt: Point, tree, geom_to_poly) -> Optional[Dict[str, Any]]:
    if tree is None:
        return None
    hits = tree.query(pt)
    for geom in hits:
        poly = geom_to_poly.get(id(geom))
        if poly and poly["prep"].covers(pt):
            return poly
    return None

def write_feature_collection(path: str, feats: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {"type": "FeatureCollection", "features": feats}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

def main():
    landkreise = load_gadm_l2(GADM_L2_PATH, filter_name_1=FILTER_NAME_1)
    if not landkreise:
        print("❌ No Landkreis polygons loaded — check GADM path or FILTER_NAME_1.")
        return

    tree, poly_list, geom_to_poly = build_index(landkreise)
    gadm_names = [rec["name_2"] for rec in poly_list]

    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    unmatched: List[Dict[str, Any]] = []

    total_files = 0
    matched_count = 0
    fallback_count = 0
    unmatched_count = 0

    for root, _, files in os.walk(INPUT_FOLDER):
        for fn in files:
            if not fn.lower().endswith(".json"):
                continue
            total_files += 1
            fpath = os.path.join(root, fn)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not read {fpath}: {e}")
                continue

            if not isinstance(data, list):
                continue

            for entry in data:
                pt = extract_point(entry)
                if pt is None:
                    unmatched.append({"type":"Feature","geometry":None,"properties":entry})
                    unmatched_count += 1
                    continue

                match = assign_landkreis(pt, tree, geom_to_poly)

                if match is None:
                    raw_lk = str(entry.get("Landkreis", "")).strip()
                    if raw_lk:
                        fallback_name = fallback_name_contains(raw_lk, gadm_names)
                        if fallback_name:
                            for rec in poly_list:
                                if rec["name_2"] == fallback_name:
                                    match = rec
                                    fallback_count += 1
                                    break

                if match is None:
                    unmatched.append({
                        "type":"Feature",
                        "geometry":{"type":"Point", "coordinates":[pt.x, pt.y]},
                        "properties":entry
                    })
                    unmatched_count += 1
                    continue

                props = {k:v for k,v in entry.items() if k not in ("Laengengrad","Breitengrad")}
                props.update({
                    "ASSIGNED_NAME_1": match["name_1"],
                    "ASSIGNED_NAME_2": match["name_2"],
                    "ASSIGNED_CC_2": match["cc_2"],
                })
                feat = {
                    "type":"Feature",
                    "geometry":{"type":"Point","coordinates":[pt.x, pt.y]},
                    "properties": props
                }
                key = (match["cc_2"] or "UNKNOWN", match["name_2"] or "Unknown_Landkreis")
                buckets[key].append(feat)
                matched_count += 1

    for (cc2, name2), feats in buckets.items():
        safe = f"{cc2}_{slugify(name2)}.geojson"
        out_path = os.path.join(OUTPUT_DIR, safe)
        write_feature_collection(out_path, feats)
        print(f"✅ {len(feats):>6} features -> {out_path}")

    unmatched_path = os.path.join(OUTPUT_DIR, "_unmatched.geojson")
    write_feature_collection(unmatched_path, unmatched)

    print("\n—— Summary ——")
    print(f"Processed JSON files : {total_files}")
    print(f"Matched features     : {matched_count}")
    print(f"Fallback matched     : {fallback_count}")
    print(f"Unmatched features   : {unmatched_count} -> {unmatched_path}")
    print(f"Landkreise written   : {len(buckets)} -> {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
