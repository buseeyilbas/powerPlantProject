# step27_data_quality_report.py
# This script ONLY prints a data quality summary to the console.
# It does NOT create any report file on disk.

import os
import json
from collections import Counter

# Base paths (adapt these if your folder structure changes)
BASE = r"C:\Users\jo73vure\Desktop\powerPlantProject\data"
ALL_JSON_DIR = os.path.join(BASE, "json")
VALID_JSON_DIR = os.path.join(BASE, "valid_json")
ACTIVE_JSON_DIR = os.path.join(BASE, "active_json")

# Field names in the MaStR JSON entries
FIELD_STATE = "Bundesland"
FIELD_ENERGY = "Energietraeger"


def _iter_json_files(directory: str, only_einheiten: bool = False):
    """
    Yield full paths of JSON files in a directory.

    If only_einheiten is True, only files starting with 'Einheiten'
    are considered (matching the MaStR naming convention).
    """
    if not os.path.isdir(directory):
        return

    for name in os.listdir(directory):
        if not name.lower().endswith(".json"):
            continue
        if only_einheiten and not name.startswith("Einheiten"):
            continue
        yield os.path.join(directory, name)


def _load_entries_from_file(path: str):
    """
    Load a JSON file and return a flat list of entries.

    The MaStR JSON is usually a list of dicts, but this helper
    is defensive: if it is a dict, it will use its values.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"[WARN] Could not read JSON file: {path} ({exc})")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())

    # Fallback: unsupported structure
    return []


def _collect_stats(directory: str, only_einheiten: bool = False):
    """
    Collect simple statistics (counts, by-state, by-energy)
    for all entries in JSON files under the given directory.
    """
    total_count = 0
    by_state = Counter()
    by_energy = Counter()

    for path in _iter_json_files(directory, only_einheiten=only_einheiten):
        entries = _load_entries_from_file(path)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            total_count += 1

            state = entry.get(FIELD_STATE)
            if state:
                by_state[state] += 1

            energy = entry.get(FIELD_ENERGY)
            if energy:
                by_energy[energy] += 1

    return {
        "count": total_count,
        "by_state": dict(by_state),
        "by_energy": dict(by_energy),
    }


def _percent(numerator: int, denominator: int) -> float:
    """
    Compute percentage with two decimal places.
    Returns 0.0 if denominator is zero.
    """
    if denominator == 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def build_summary():
    """
    Build an in-memory summary structure containing:
    - total counts for ALL, VALID, ACTIVE
    - basic percentages between these sets
    """
    # "All" = only Einheiten*.json from the raw json directory
    all_stats = _collect_stats(ALL_JSON_DIR, only_einheiten=True)

    # "Valid" and "Active" = all JSON files in their respective folders
    valid_stats = _collect_stats(VALID_JSON_DIR, only_einheiten=False)
    active_stats = _collect_stats(ACTIVE_JSON_DIR, only_einheiten=False)

    all_count = all_stats["count"]
    valid_count = valid_stats["count"]
    active_count = active_stats["count"]

    overall = {
        "all": all_count,
        "valid": valid_count,
        "active": active_count,
        "valid_over_all": _percent(valid_count, all_count),
        "active_over_all": _percent(active_count, all_count),
        "active_over_valid": _percent(active_count, valid_count),
    }

    return {
        "overall": overall,
        "all": all_stats,
        "valid": valid_stats,
        "active": active_stats,
    }


def print_summary(summary: dict):
    """
    Print a compact summary to the console.
    This is the ONLY output of this script.
    """
    o = summary["overall"]

    print("\n📊 --- Extended MaStR Data Quality Summary (Console Only) ---")
    print(f"All entries:    {o['all']:,}")
    print(f"Valid entries:  {o['valid']:,}")
    print(f"Active entries: {o['active']:,}")

    print("\n📈 Percentages:")
    print(f"  • Valid / All   : {o['valid_over_all']}%")
    print(f"  • Active / All  : {o['active_over_all']}%")
    print(f"  • Active / Valid: {o['active_over_valid']}%")


if __name__ == "__main__":
    summary = build_summary()
    print_summary(summary)
