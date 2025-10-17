
import os
import json
from typing import Dict, Optional
from shapely.geometry import shape, MultiPolygon, Polygon, Point

# ========== CONFIG ==========
INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_GEOJSON = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany_three_checks.geojson"
SUMMARY_PATH   = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\_consistency_summary.json"
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # expects features[].properties.name
# ============================

# ---- Bundesland (1400–1415) => normalized state name ----
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

# ---- Gemeindeschlüssel 2-digit prefix => normalized state name ----
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
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
         .replace("ß", "ss"))
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
        lon_raw = entry.get("Laengengrad", "")
        lat_raw = entry.get("Breitengrad", "")
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
    Expects each feature to have properties.name and Polygon/MultiPolygon geometry.
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
    props = {k: v for k, v in entry.items() if k not in ["Laengengrad", "Breitengrad"]}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point.x, point.y]},
        "properties": props,
    }

# ---------- Main ----------

def convert_all_germany_with_three_checks(
    input_folder: str,
    polygon_states_path: str,
    output_geojson: str,
    summary_path: str
):
    # Load polygons once
    state_polygons = load_state_polygons(polygon_states_path)
    if not state_polygons:
        raise RuntimeError("No state polygons loaded. Check POLYGON_STATES_PATH and properties.name field.")

    features = []

    # Counters/logs
    total_files = 0
    total_entries = 0
    consistent = 0
    no_poly = 0
    bl_mismatch = 0
    gs_mismatch = 0
    bl_missing = 0
    gs_missing = 0

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
                point = parse_point(entry)
                if point is None:
                    continue

                poly_state_norm = polygon_state_of_point(point, state_polygons)
                if not poly_state_norm:
                    no_poly += 1
                    continue  # discard if no polygon match

                bl_code = entry.get("Bundesland")
                bl_norm = bl_code_to_norm_name(bl_code) if bl_code is not None else None
                if bl_norm is None:
                    bl_missing += 1
                    mismatch_samples.append({
                        "reason": "bundesland_missing_or_unmapped",
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer")
                    })
                    continue

                gs = entry.get("Gemeindeschluessel")
                gs_norm = gs_prefix_to_norm_name(gs) if gs is not None else None
                if gs_norm is None:
                    gs_missing += 1
                    mismatch_samples.append({
                        "reason": "gemeindeschluessel_missing_or_unmapped",
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer")
                    })
                    continue

                if poly_state_norm == bl_norm == gs_norm:
                    features.append(to_feature(entry, point))
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
                        "EinheitMastrNummer": entry.get("EinheitMastrNummer")
                    })

    # Write single All-Germany GeoJSON
    os.makedirs(os.path.dirname(output_geojson), exist_ok=True)
    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    # Write summary log
    summary = {
        "files_processed": total_files,
        "entries_seen": total_entries,
        "consistent_written": consistent,
        "no_polygon_match": no_poly,
        "bundesland_missing_or_unmapped": bl_missing,
        "gemeindeschluessel_missing_or_unmapped": gs_missing,
        "bundesland_mismatch_count": bl_mismatch,
        "gemeindeschluessel_mismatch_count": gs_mismatch,
        "mismatch_samples_first_200": mismatch_samples[:200],
        "output_geojson": output_geojson,
        "polygon_states_path": polygon_states_path
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n====== SUMMARY ======")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n✅ Created {output_geojson}")

if __name__ == "__main__":
    convert_all_germany_with_three_checks(
        INPUT_FOLDER,
        POLYGON_STATES_PATH,
        OUTPUT_GEOJSON,
        SUMMARY_PATH
    )
