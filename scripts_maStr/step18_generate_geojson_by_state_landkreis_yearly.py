
import os
import re
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep


# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_ROOT  = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_landkreis_yearly"
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"  # expects properties.NAME_1 and properties.NAME_2
LON_FIELD    = "Laengengrad"
LAT_FIELD    = "Breitengrad"
DATE_FIELD   = "Inbetriebnahmedatum"  # used to extract year
# ===========================


# ---------- I/O helpers ----------

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_filename(name: str) -> str:
    """
    Make a safe filename/folder name from a human label.
    Keeps letters, digits, spaces, dashes, underscores, dots; replaces others with '_'.
    Collapses consecutive underscores.
    """
    name = (name or "").strip()
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^0-9A-Za-zÄÖÜäöüß \-_.]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name or "unknown"


# ---------- Geometry helpers ----------

def parse_point(entry: dict, lon_key: str = LON_FIELD, lat_key: str = LAT_FIELD) -> Optional[Point]:
    """
    Parse lon/lat strings with either dot or comma decimals, return shapely Point.
    Returns None if coordinates are invalid/out of bounds.
    """
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


def load_gadm_l2_polygons(geojson_path: str) -> List[Tuple[str, str, dict, MultiPolygon]]:
    """
    Load GADM Level-2 polygons and return a list of tuples:
      (name_1, name_2, properties, multipolygon)
    where:
      - name_1 = props["NAME_1"]  (State)
      - name_2 = props["NAME_2"]  (Landkreis)
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    results: List[Tuple[str, str, dict, MultiPolygon]] = []
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

        results.append((name_1, name_2, props, geom))
    return results


# ---------- Feature / year helpers ----------

def to_feature(entry: dict, point: Point) -> dict:
    """Build a GeoJSON Point Feature from the raw entry."""
    props = {k: v for k, v in entry.items() if k not in [LON_FIELD, LAT_FIELD]}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        "properties": props,
    }


def extract_year(entry: dict, field: str = DATE_FIELD) -> str:
    """
    Extract YYYY from a date-like string. Accepts 'YYYY-MM-DD', 'YYYY', etc.
    Returns 'unknown' when missing/invalid.
    """
    val = str(entry.get(field, "") or "").strip()
    if len(val) >= 4 and val[:4].isdigit():
        return val[:4]
    return "unknown"


# ---------- Main converter ----------

def convert_state_landkreis_yearly(
    input_folder: str,
    output_root: str,
    gadm_l2_path: str,
    date_field: str = DATE_FIELD
):
    os.makedirs(output_root, exist_ok=True)

    # Load and prepare polygons for fast containment checks
    l2_polys = load_gadm_l2_polygons(gadm_l2_path)
    if not l2_polys:
        raise RuntimeError("No Level-2 polygons loaded. Check GADM_L2_PATH and NAME_1/NAME_2 fields.")
    prepared = [(name_1, name_2, prep(geom)) for (name_1, name_2, _props, geom) in l2_polys]

    # Buckets: {state: {landkreis: {year: [features...]}}}
    buckets: Dict[str, Dict[str, Dict[str, List[dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # Stats
    total_files = 0
    total_entries = 0
    matched_entries = 0
    unmatched_entries = 0
    sample_unmatched = []

    # Walk through all JSON files
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

                matched = False
                for name_1, name_2, pgeom in prepared:
                    # covers() includes boundary points; prepared geometry proxies don't surface covers(),
                    # so we check via the wrapped geometry if available; otherwise fallback to contains().
                    if pgeom.context.covers(pt) if hasattr(pgeom, "context") and hasattr(pgeom.context, "covers") else pgeom.contains(pt):
                        year = extract_year(entry, date_field)
                        feat = to_feature(entry, pt)
                        buckets[name_1][name_2][year].append(feat)
                        matched_entries += 1
                        matched = True
                        break

                if not matched:
                    unmatched_entries += 1
                    if len(sample_unmatched) < 200:
                        sample_unmatched.append({
                            "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
                            "coords": [pt.x, pt.y]
                        })

    # Write: <OUTPUT_ROOT>/<STATE>/<LANDKREIS>/<YYYY>.geojson
    for state_name, lkr_map in buckets.items():
        state_folder = os.path.join(output_root, safe_filename(state_name))
        os.makedirs(state_folder, exist_ok=True)

        for lkr_name, years_map in lkr_map.items():
            lkr_folder = os.path.join(state_folder, safe_filename(lkr_name))
            os.makedirs(lkr_folder, exist_ok=True)

            for year, feats in years_map.items():
                if not feats:
                    continue
                out_path = os.path.join(lkr_folder, f"{year}.geojson")
                geojson = {"type": "FeatureCollection", "features": feats}
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(geojson, f, ensure_ascii=False, indent=2)
                print(f"✅ Saved {len(feats):5d} features → {state_name}/{lkr_name}/{year}.geojson")

    # Summary
    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "matched_entries": matched_entries,
        "unmatched_entries": unmatched_entries,
        "unmatched_samples_first_200": sample_unmatched,
        "output_root": output_root,
        "gadm_l2_path": gadm_l2_path,
        "date_field": date_field,
    }
    log_path = os.path.join(output_root, "_state_landkreis_yearly_summary.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n====== SUMMARY ======")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    convert_state_landkreis_yearly(INPUT_FOLDER, OUTPUT_ROOT, GADM_L2_PATH, DATE_FIELD)
