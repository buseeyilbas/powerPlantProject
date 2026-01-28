
# Filename: step7_analyze_active_jsons_2ndfiltering.py
# Purpose:
#   Second-stage analysis for ACTIVE JSONs, but ONLY for entries that pass the strict
#   "4 checks" gate (copied from step15/step16 logic):
#     1) Point-in-polygon check against STATE polygons
#     2) Bundesland numeric code -> canonical state name
#     3) Gemeindeschluessel prefix -> canonical state name
#     4) Must match at least one Landkreis polygon (GADM L2)
#
#   After the 4-check gate, compute (per energy type):
#     - min installed power and max installed power
#     - commissioning year for min/max
#     - Bundesland code ("state number") for min/max
#     - file/index reference for traceability
#
# Outputs:
#   - report.md
#   - summary.json
#   - per_file.csv
#   - energy_type_minmax.csv
#   - energy_type_minmax.json
#
# Run:
#   py step7_analyze_active_jsons_2ndfiltering.py
#
# Notes:
#   - This script expects coordinate fields 'Laengengrad' and 'Breitengrad'.
#   - State polygons GeoJSON must have features[].properties.name.
#   - GADM L2 GeoJSON must have features[].properties.NAME_1 and NAME_2.

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.prepared import prep


# =========================
# === USER CONFIG (EDIT) ===
# =========================

INPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
OUTPUT_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\exports\step7_analysis_2ndfiltering"

# 4-check dependencies (same as step15/step16 style)
POLYGON_STATES_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\polygon_states.json"  # features[].properties.name
GADM_L2_PATH = r"C:\Users\jo73vure\Desktop\powerPlantProject\gadm_data\gadm41_DEU\gadm41_DEU_2.json"  # expects NAME_1 and NAME_2

LON_FIELD = "Laengengrad"
LAT_FIELD = "Breitengrad"

# Supervisor will provide these limits. Keep None to disable.
USER_LIMITS = {
    # Installed power limits in kW (applied after parsing power_kw)
    "power_kw_min": None,  # e.g. 0.1
    "power_kw_max": None,  # e.g. 50000

    # Optional: commissioning date limits (ISO "YYYY-MM-DD" preferred).
    "commissioning_date_min": None,  # e.g. "1990-01-01"
    "commissioning_date_max": None,  # e.g. "2025-12-31"
}

# Candidate field keys (add your exact keys here if different)
CANDIDATE_KEYS = {
    "energy": [
        "Energietraeger",
        "EnergietraegerId",
        "EnergietraegerSchluessel",
        "EnergietraegerBezeichnung",
        "EnergietraegerLabel",
    ],
    "power": [
        "Bruttoleistung",
        "Nettonennleistung",
        "InstallierteLeistung",
        "Nennleistung",
        "Leistung",
    ],
    "commissioning_date": [
        "Inbetriebnahmedatum",
        "InbetriebnahmeDatum",
        "Inbetriebnahme",
        "CommissioningDate",
    ],
}

# If power looks like it's in W, convert to kW above this threshold
WATT_TO_KW_THRESHOLD = 1_000_000  # if parsed power > 1e6, assume W


# ---------- ENERGY MAP / FIELDS ----------
ENERGY_CODE_TO_LABEL = {
    "2495": "Photovoltaik - Photovoltaics",
    "2497": "Windenergie Onshore - Onshore Wind Energy",
    "2498": "Wasserkraft - Hydropower",
    "2493": "Biogas - Biogas",
    "2496": "Stromspeicher - Battery Energy Storage",
# others:
    "2403": "Tiefe Geothermie - Deep Geothermal Energy",
    "2405": "Klärgas - Sewage Gas",
    "2406": "Druckentspannung - Pressure Relief Energy",
    "2957": "Druckentspannung (BHKW, Mischform) - Pressure Relief (Waste Pressure, CHP)",
    "2958": "Druckentspannung (kleinere Anlagen) - Pressure Relief (Small-scale Plants)",
}



# ==============================
# === 4-CHECKS MAPPING TABLES ===
# ==============================

# Bundesland (1400-1415) => canonical token
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

# Gemeindeschluessel 2-digit prefix => canonical token
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


# ======================
# === DATA STRUCTURES ===
# ======================

@dataclass
class ExtremumRef:
    file_name: str
    index_in_file: int
    bundesland_code: str
    bundesland_name: str 
    state_name_norm: str
    energy_code: str
    energy_label: str
    power_kw: float
    commissioning_date: str
    commissioning_year: str

    def to_compact_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["power_kw"] = round(float(d["power_kw"]), 6)
        return d


@dataclass
class EnergyMinMax:
    energy_code: str
    energy_label: str
    min_power_kw: Optional[float]
    max_power_kw: Optional[float]
    min_ref: Optional[ExtremumRef]
    max_ref: Optional[ExtremumRef]


# ======================
# === HELPERS / PARSE ===
# ======================

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def bytes_to_gb_mb(num_bytes: int) -> Tuple[float, float]:
    gb = num_bytes / (1024**3)
    mb = num_bytes / (1024**2)
    return gb, mb


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def pick_first(entry: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        if k in entry and entry[k] not in (None, ""):
            return safe_str(entry[k])
    return ""


def parse_float_maybe(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        if math.isnan(float(x)):
            return None
        return float(x)

    s = safe_str(x)
    if not s:
        return None

    # Accept comma decimals
    s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


def parse_power_kw(entry: Dict[str, Any]) -> Optional[float]:
    raw = None
    for k in CANDIDATE_KEYS["power"]:
        if k in entry and entry[k] not in (None, ""):
            raw = entry[k]
            break

    val = parse_float_maybe(raw)
    if val is None:
        return None

    if val > WATT_TO_KW_THRESHOLD:
        return val / 1000.0

    return val


def parse_date(entry: Dict[str, Any]) -> str:
    return pick_first(entry, CANDIDATE_KEYS["commissioning_date"])


def extract_year(date_str: str) -> str:
    s = safe_str(date_str)
    y = s[:4]
    return y if len(y) == 4 and y.isdigit() else "unknown"


def passes_limits(power_kw: Optional[float], commissioning_date: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    pmin = USER_LIMITS.get("power_kw_min")
    pmax = USER_LIMITS.get("power_kw_max")
    dmin = USER_LIMITS.get("commissioning_date_min")
    dmax = USER_LIMITS.get("commissioning_date_max")

    if power_kw is not None:
        if pmin is not None and power_kw < float(pmin):
            reasons.append(f"power_kw < {pmin}")
        if pmax is not None and power_kw > float(pmax):
            reasons.append(f"power_kw > {pmax}")

    # Date limits are string-based, expecting ISO YYYY-MM-DD for correct comparisons
    if commissioning_date:
        if dmin is not None and commissioning_date < str(dmin):
            reasons.append(f"date < {dmin}")
        if dmax is not None and commissioning_date > str(dmax):
            reasons.append(f"date > {dmax}")

    return (len(reasons) == 0), reasons


def bundesland_code_to_name(code: str) -> str:
    return BUNDESLAND_CODE_TO_NAME.get(str(code), "unknown")


# =============================
# === 4-CHECKS GEO HELPERS  ===
# =============================

def normalize_state_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = s.replace("ae", "ae").replace("oe", "oe").replace("ue", "ue").replace("ss", "ss")
    # Also normalize actual umlauts in case they exist
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    for ch in [" ", "_", "-", "(", ")", "[", "]", "{", "}", ".", ",", "'", '"', "/"]:
        s = s.replace(ch, "")
    return s


def parse_point(entry: Dict[str, Any], lon_key: str = LON_FIELD, lat_key: str = LAT_FIELD) -> Optional[Point]:
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
    data = read_json(geojson_path)
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
    for norm_name, mp in polygons_by_norm.items():
        if mp.covers(point):
            return norm_name
    return None


def bl_code_to_norm_name(code: Any) -> Optional[str]:
    if code is None:
        return None
    name = BUNDESLAND_CODE_TO_NAME.get(str(code).strip())
    return normalize_state_name(name) if name else None


def gs_prefix_to_norm_name(gs: Any) -> Optional[str]:
    if gs is None:
        return None
    s = str(gs)
    if len(s) < 2:
        return None
    name = GS_PREFIX_TO_NAME.get(s[:2])
    return normalize_state_name(name) if name else None


def load_gadm_l2_prepared(geojson_path: str):
    data = read_json(geojson_path)
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
    for _name_1, _name_2, pgeom in prepared_l2:
        # covers includes boundary points; fallback to contains
        if pgeom.context.covers(pt) if hasattr(pgeom, "context") and hasattr(pgeom.context, "covers") else pgeom.contains(pt):
            return True
    return False


# ============================
# === ENERGY LABEL PARSING ===
# ============================

def normalize_energy(value: str) -> Tuple[str, str]:
    """Return (energy_code, energy_label)."""
    raw = safe_str(value)
    if not raw:
        return "unknown", "UNKNOWN"

    # If this is a known numeric code
    if raw in ENERGY_CODE_TO_LABEL:
        return raw, ENERGY_CODE_TO_LABEL[raw]

    # If it is numeric-ish but not in map
    if raw.isdigit():
        return raw, ENERGY_CODE_TO_LABEL.get(raw, "UNKNOWN")

    # If it is already a label
    for code, label in ENERGY_CODE_TO_LABEL.items():
        if raw.lower() == label.lower():
            return code, label

    return "unknown", raw


def get_energy(entry: Dict[str, Any]) -> Tuple[str, str]:
    val = pick_first(entry, CANDIDATE_KEYS["energy"])
    return normalize_energy(val)


# ==================
# === OUTPUT IO   ===
# ==================

def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ======================
# === MAIN ANALYSIS  ===
# ======================

def analyze() -> None:
    ensure_dir(OUTPUT_FOLDER)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(OUTPUT_FOLDER, f"run_{timestamp}")
    ensure_dir(run_folder)

    json_files = [fn for fn in os.listdir(INPUT_FOLDER) if fn.lower().endswith(".json")]
    json_files.sort()

    if not json_files:
        print(f"No JSON files found in: {INPUT_FOLDER}")
        return

    print("\n==============================")
    print("STEP 7 - 4CHECK GATED ENERGY MIN/MAX")
    print("==============================")
    print(f"Input folder : {INPUT_FOLDER}")
    print(f"Output folder: {run_folder}")
    print(f"Files found  : {len(json_files)}")

    print("\n=== Limits ===")
    for k, v in USER_LIMITS.items():
        print(f"- {k}: {v}")

    # Load polygons once
    polygons_by_norm, pretty_by_norm = load_state_polygons(POLYGON_STATES_PATH)
    if not polygons_by_norm:
        raise RuntimeError("No state polygons loaded. Check POLYGON_STATES_PATH and properties.name.")

    prepared_l2 = load_gadm_l2_prepared(GADM_L2_PATH)
    if not prepared_l2:
        raise RuntimeError("No Landkreis polygons loaded. Check GADM_L2_PATH and NAME_1/NAME_2.")

    # Energy min/max tables
    energy_stats: Dict[str, EnergyMinMax] = {}

    # Per-file and global counters
    per_file_rows: List[Dict[str, Any]] = []

    dropped_total_invalid_entry = 0
    dropped_total_not_list = 0
    dropped_total_no_point = 0
    dropped_total_no_poly_state = 0
    dropped_total_missing_bl = 0
    dropped_total_missing_gs = 0
    dropped_total_triple_mismatch = 0
    dropped_total_no_landkreis = 0
    dropped_total_limits = 0
    dropped_total_missing_power = 0

    kept_total = 0
    seen_total = 0

    for file_i, file_name in enumerate(json_files, start=1):
        path = os.path.join(INPUT_FOLDER, file_name)
        size_bytes = os.path.getsize(path)
        size_gb, size_mb = bytes_to_gb_mb(size_bytes)

        try:
            data = read_json(path)
        except json.JSONDecodeError:
            print(f"\n[{file_i}/{len(json_files)}] Invalid JSON skipped: {file_name}")
            continue

        if not isinstance(data, list):
            dropped_total_not_list += 1
            print(f"\n[{file_i}/{len(json_files)}] Not a list JSON skipped: {file_name}")
            continue

        file_seen = len(data)
        file_kept = 0

        # Local drop reasons
        d_invalid = 0
        d_no_point = 0
        d_no_poly = 0
        d_missing_bl = 0
        d_missing_gs = 0
        d_mismatch = 0
        d_no_landkreis = 0
        d_limits = 0
        d_missing_power = 0

        print(f"\n[{file_i}/{len(json_files)}] {file_name}")
        print(f"- entries: {file_seen}")
        print(f"- size   : {size_gb:.6f} GB ({size_mb:.2f} MB)")

        for idx, entry in enumerate(data):
            seen_total += 1

            if not isinstance(entry, dict):
                d_invalid += 1
                continue

            pt = parse_point(entry)
            if pt is None:
                d_no_point += 1
                continue

            poly_state_norm = polygon_state_of_point(pt, polygons_by_norm)
            if not poly_state_norm:
                d_no_poly += 1
                continue

            bundesland_code = safe_str(entry.get("Bundesland"))
            bl_norm = bl_code_to_norm_name(bundesland_code)
            if bl_norm is None:
                d_missing_bl += 1
                continue

            gs_norm = gs_prefix_to_norm_name(entry.get("Gemeindeschluessel"))
            if gs_norm is None:
                d_missing_gs += 1
                continue

            if not (poly_state_norm == bl_norm == gs_norm):
                d_mismatch += 1
                continue

            if not has_any_landkreis_match(pt, prepared_l2):
                d_no_landkreis += 1
                continue

            # After 4 checks: parse needed analysis fields
            power_kw = parse_power_kw(entry)
            if power_kw is None:
                d_missing_power += 1
                continue

            commissioning_date = safe_str(parse_date(entry))
            ok, _reasons = passes_limits(power_kw, commissioning_date)
            if not ok:
                d_limits += 1
                continue

            energy_code, energy_label = get_energy(entry)
            state_name_norm = poly_state_norm
            commissioning_year = extract_year(commissioning_date)

            ref = ExtremumRef(
                file_name=file_name,
                index_in_file=idx,
                bundesland_code=bundesland_code,
                bundesland_name=bundesland_code_to_name(bundesland_code),
                state_name_norm=state_name_norm,
                energy_code=energy_code,
                energy_label=energy_label,
                power_kw=float(power_kw),
                commissioning_date=commissioning_date,
                commissioning_year=commissioning_year,
            )

            # Update per-energy min/max
            key = f"{energy_code}::{energy_label}"
            if key not in energy_stats:
                energy_stats[key] = EnergyMinMax(
                    energy_code=energy_code,
                    energy_label=energy_label,
                    min_power_kw=None,
                    max_power_kw=None,
                    min_ref=None,
                    max_ref=None,
                )

            g = energy_stats[key]

            if g.min_power_kw is None or ref.power_kw < float(g.min_power_kw):
                g.min_power_kw = ref.power_kw
                g.min_ref = ref

            if g.max_power_kw is None or ref.power_kw > float(g.max_power_kw):
                g.max_power_kw = ref.power_kw
                g.max_ref = ref

            file_kept += 1
            kept_total += 1

        # Accumulate global drops
        dropped_total_invalid_entry += d_invalid
        dropped_total_no_point += d_no_point
        dropped_total_no_poly_state += d_no_poly
        dropped_total_missing_bl += d_missing_bl
        dropped_total_missing_gs += d_missing_gs
        dropped_total_triple_mismatch += d_mismatch
        dropped_total_no_landkreis += d_no_landkreis
        dropped_total_limits += d_limits
        dropped_total_missing_power += d_missing_power

        per_file_rows.append(
            {
                "file_name": file_name,
                "entries_total": file_seen,
                "entries_kept_after_4checks_and_limits": file_kept,
                "file_size_gb": round(size_gb, 9),
                "file_size_mb": round(size_mb, 3),
                "dropped_invalid_entry": d_invalid,
                "dropped_no_point": d_no_point,
                "dropped_no_state_polygon": d_no_poly,
                "dropped_missing_bundesland": d_missing_bl,
                "dropped_missing_gemeindeschluessel": d_missing_gs,
                "dropped_triple_mismatch": d_mismatch,
                "dropped_no_landkreis_match": d_no_landkreis,
                "dropped_missing_power": d_missing_power,
                "dropped_limits": d_limits,
            }
        )

        print(f"- kept (after 4 checks + limits): {file_kept}")
        print("- dropped (reasons):")
        print(f"  - invalid entry            : {d_invalid}")
        print(f"  - no point/coords          : {d_no_point}")
        print(f"  - no state polygon         : {d_no_poly}")
        print(f"  - missing Bundesland       : {d_missing_bl}")
        print(f"  - missing Gemeindeschl     : {d_missing_gs}")
        print(f"  - triple mismatch          : {d_mismatch}")
        print(f"  - no Landkreis match       : {d_no_landkreis}")
        print(f"  - missing power            : {d_missing_power}")
        print(f"  - user limits              : {d_limits}")

    # Build energy rows
    energy_rows: List[Dict[str, Any]] = []
    for _k, g in sorted(energy_stats.items(), key=lambda kv: (kv[1].energy_label, kv[1].energy_code)):
        min_ref = None if g.min_ref is None else g.min_ref.to_compact_dict()
        max_ref = None if g.max_ref is None else g.max_ref.to_compact_dict()

        energy_rows.append(
            {
                "energy_code": g.energy_code,
                "energy_label": g.energy_label,
                "min_power_kw": None if g.min_power_kw is None else round(float(g.min_power_kw), 6),
                "min_year": "" if g.min_ref is None else g.min_ref.commissioning_year,
                "min_bundesland": "" if g.min_ref is None else g.min_ref.bundesland_code,
                "min_file": "" if g.min_ref is None else g.min_ref.file_name,
                "min_index": "" if g.min_ref is None else g.min_ref.index_in_file,
                "max_power_kw": None if g.max_power_kw is None else round(float(g.max_power_kw), 6),
                "max_year": "" if g.max_ref is None else g.max_ref.commissioning_year,
                "max_bundesland": "" if g.max_ref is None else g.max_ref.bundesland_code,
                "max_file": "" if g.max_ref is None else g.max_ref.file_name,
                "max_index": "" if g.max_ref is None else g.max_ref.index_in_file,
            }
        )

    # Write outputs
    per_file_csv = os.path.join(run_folder, "per_file.csv")
    energy_csv = os.path.join(run_folder, "energy_type_minmax.csv")
    energy_json = os.path.join(run_folder, "energy_type_minmax.json")
    summary_json = os.path.join(run_folder, "summary.json")
    report_md = os.path.join(run_folder, "report.md")

    write_csv(per_file_csv, per_file_rows)
    write_csv(energy_csv, energy_rows)

    # energy json (with full refs)
    energy_payload: List[Dict[str, Any]] = []
    for _k, g in sorted(energy_stats.items(), key=lambda kv: (kv[1].energy_label, kv[1].energy_code)):
        energy_payload.append(
            {
                "energy_code": g.energy_code,
                "energy_type_name": ENERGY_CODE_TO_LABEL.get(g.energy_code, g.energy_label),
                "min_power_kw": g.min_power_kw,
                "max_power_kw": g.max_power_kw,
                "min_ref": None if g.min_ref is None else g.min_ref.to_compact_dict(),
                "max_ref": None if g.max_ref is None else g.max_ref.to_compact_dict(),
            }
        )


    with open(energy_json, "w", encoding="utf-8") as f:
        json.dump(energy_payload, f, ensure_ascii=False, indent=2)

    summary = {
        "input_folder": INPUT_FOLDER,
        "output_folder": run_folder,
        "files_seen": len(json_files),
        "entries_seen_total": seen_total,
        "entries_kept_total": kept_total,
        "limits_used": USER_LIMITS,
        "four_checks": {
            "polygon_states_path": POLYGON_STATES_PATH,
            "gadm_l2_path": GADM_L2_PATH,
            "lon_field": LON_FIELD,
            "lat_field": LAT_FIELD,
        },
        "dropped_totals": {
            "invalid_entry": dropped_total_invalid_entry,
            "not_list_json": dropped_total_not_list,
            "no_point": dropped_total_no_point,
            "no_state_polygon": dropped_total_no_poly_state,
            "missing_bundesland": dropped_total_missing_bl,
            "missing_gemeindeschluessel": dropped_total_missing_gs,
            "triple_mismatch": dropped_total_triple_mismatch,
            "no_landkreis_match": dropped_total_no_landkreis,
            "missing_power": dropped_total_missing_power,
            "user_limits": dropped_total_limits,
        },
        "energy_types_count": len(energy_rows),
    }

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Markdown report
    def md_line(s: str = "") -> str:
        return s + "\n"

    md = ""
    md += md_line("# Step 7 - 4check gated energy min/max report")
    md += md_line(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    md += md_line(f"- Input: `{INPUT_FOLDER}`")
    md += md_line(f"- Output: `{run_folder}`")
    md += md_line(f"- Files: **{len(json_files)}**")
    md += md_line(f"- Entries seen total: **{seen_total}**")
    md += md_line(f"- Entries kept total: **{kept_total}**")
    md += md_line("")

    md += md_line("## Limits used")
    for k, v in USER_LIMITS.items():
        md += md_line(f"- `{k}`: `{v}`")
    md += md_line("")

    md += md_line("## Drop totals")
    for k, v in summary["dropped_totals"].items():
        md += md_line(f"- `{k}`: **{v}**")
    md += md_line("")

    md += md_line("## Output files")
    md += md_line("- `per_file.csv`")
    md += md_line("- `energy_type_minmax.csv`")
    md += md_line("- `energy_type_minmax.json`")
    md += md_line("- `summary.json`")
    md += md_line("")

    md += md_line("## Energy type min/max (quick view)")
    for row in energy_rows:
        md += md_line(
            f"- {row['energy_label']} ({row['energy_code']}): "
            f"min={row['min_power_kw']} kW (year={row['min_year']}, BL={row['min_bundesland']}), "
            f"max={row['max_power_kw']} kW (year={row['max_year']}, BL={row['max_bundesland']})"
        )

    with open(report_md, "w", encoding="utf-8") as f:
        f.write(md)

    print("\n==============================")
    print("DONE - Outputs written")
    print("==============================")
    print(f"- {report_md}")
    print(f"- {summary_json}")
    print(f"- {per_file_csv}")
    print(f"- {energy_csv}")
    print(f"- {energy_json}")


if __name__ == "__main__":
    analyze()
