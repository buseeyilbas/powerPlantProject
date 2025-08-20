
import os
import json
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.prepared import prep

# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
OUTPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_landkreis"
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"  # expects properties.NAME_2
LON_FIELD = "Laengengrad"
LAT_FIELD = "Breitengrad"
DATE_FIELD = "Inbetriebnahmedatum"  # optional; kept in properties as-is
# ===========================


# ---------- I/O helpers ----------

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_filename(name: str) -> str:
    """
    Make a safe filename from a Landkreis name.
    Keeps letters, digits, spaces, dashes, underscores; replaces others with '_'.
    Collapses consecutive underscores.
    """
    name = name.strip()
    # Replace slashes and backslashes first
    name = name.replace("/", "_").replace("\\", "_")
    # Replace remaining unsafe chars
    name = re.sub(r"[^0-9A-Za-zÄÖÜäöüß \-_\.]", "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    # Avoid empty filename
    return name or "unknown"


# ---------- Geometry helpers ----------

def parse_point(entry: dict, lon_key: str = LON_FIELD, lat_key: str = LAT_FIELD) -> Optional[Point]:
    """
    Parse lon/lat strings with either dot or comma decimals, return shapely Point.
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


def load_landkreis_polygons(geojson_path: str) -> List[Tuple[str, dict, MultiPolygon]]:
    """
    Load GADM Level-2 polygons.

    Returns a list of (name_2, properties, multipolygon), where:
      - name_2 is taken from properties["NAME_2"]
      - properties includes fields such as GID_2, NAME_1, NAME_2, TYPE_2, CC_2, etc. (as in GADM)
    """
    data = load_json(geojson_path)
    feats = data["features"] if isinstance(data, dict) and "features" in data else data

    results: List[Tuple[str, dict, MultiPolygon]] = []
    for feat in feats:
        props = feat.get("properties", {}) or {}
        name_2 = props.get("NAME_2")  # e.g., "Alb-Donau-Kreis", "Baden-Baden" (Stadtkreis)
        if not name_2:
            continue

        geom = shape(feat.get("geometry"))
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            continue

        results.append((name_2, props, geom))

    return results


# ---------- Feature builder ----------

def to_feature(entry: dict, point: Point) -> dict:
    """Build a GeoJSON Point Feature from the raw entry."""
    props = {k: v for k, v in entry.items() if k not in [LON_FIELD, LAT_FIELD]}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        "properties": props,
    }


# ---------- Main converter ----------

def convert_by_landkreis(
    input_folder: str,
    output_folder: str,
    gadm_l2_path: str
):
    os.makedirs(output_folder, exist_ok=True)

    # Load polygons and prepare for fast containment tests
    landkreise = load_landkreis_polygons(gadm_l2_path)
    if not landkreise:
        raise RuntimeError("No Landkreis polygons loaded. Check GADM_L2_PATH and that properties.NAME_2 exists.")

    # Prepare geometries (speed-up for contains/covers)
    prepared = [(name_2, props, prep(geom)) for (name_2, props, geom) in landkreise]

    # Accumulators
    grouped: Dict[str, List[dict]] = defaultdict(list)
    total_files = 0
    total_entries = 0
    matched_entries = 0
    unmatched_entries = 0
    sample_unmatched = []

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

                matched_name: Optional[str] = None

                # Find the first Landkreis polygon that covers the point
                for name_2, props, pgeom in prepared:
                    # Use covers() semantic via prepared geometries: pgeom.contains(pt) misses boundary points.
                    # We approximate with intersects on a very small buffer around the point if needed.
                    if pgeom.covers(pt) if hasattr(pgeom.context, "covers") else pgeom.contains(pt):
                        matched_name = name_2
                        break

                if matched_name:
                    grouped[matched_name].append(to_feature(entry, pt))
                    matched_entries += 1
                else:
                    unmatched_entries += 1
                    if len(sample_unmatched) < 200:
                        sample_unmatched.append({
                            "EinheitMastrNummer": entry.get("EinheitMastrNummer"),
                            "coords": [pt.x, pt.y]
                        })

    # Write one GeoJSON per Landkreis (by NAME_2)
    for name_2, feats in grouped.items():
        if not feats:
            continue
        out_name = safe_filename(name_2) + ".geojson"
        out_path = os.path.join(output_folder, out_name)
        geojson = {"type": "FeatureCollection", "features": feats}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {len(feats)} features → {out_name}")

    # Write summary
    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "matched_entries": matched_entries,
        "unmatched_entries": unmatched_entries,
        "unmatched_samples_first_200": sample_unmatched,
        "output_folder": output_folder,
        "gadm_l2_path": gadm_l2_path,
    }
    log_path = os.path.join(output_folder, "_landkreis_summary.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n====== SUMMARY ======")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    convert_by_landkreis(INPUT_FOLDER, OUTPUT_FOLDER, GADM_L2_PATH)
