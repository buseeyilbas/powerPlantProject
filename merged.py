"""

End-to-end MaStR ETL pipeline that orchestrates:
1) Download ZIP
2) Extract ZIP
3) Validate XML & copy valid ones
4) Convert XML -> JSON
5) Validate JSON entries (required keys)
6) Build GeoJSON (all points)
7) Build state-sliced GeoJSON via polygons

This script reuses the existing modules:
- download_mastr.py
- extract_zip.py
- validate_xml.py
- xml_to_json.py
- valid_json.py
- json_to_geojson_batch.py
- generate_geojson_by_state_polygons.py

All paths and switches are configured via merged_path.json
"""

import os
import json
import sys
import traceback
from datetime import datetime

import download_mastr
import extract_zip
import validate_xml
import xml_to_json
import valid_json
import json_to_geojson_batch

# The state-by-polygon step is optional (needs shapely + polygons file)
try:
    import generate_geojson_by_state_polygons
    HAS_POLYGON_STEP = True
except Exception:
    HAS_POLYGON_STEP = False


def load_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def step_download(cfg: dict) -> str:
    """Download the MaStR ZIP and return the downloaded filepath."""
    url = cfg["download"]["url"]
    dest = cfg["paths"]["raw_data_folder"]
    print(f"[1/7] Downloading ZIP from: {url}")
    return download_mastr.download_file(url, destination_folder=dest)


def step_extract(cfg: dict) -> None:
    """Extract all ZIPs from raw folder into extracted folder."""
    print("[2/7] Extracting ZIP files...")
    extract_zip.extract_all_zips(
        cfg["paths"]["raw_data_folder"],
        cfg["paths"]["extracted_folder"]
    )


def step_validate_xml(cfg: dict) -> None:
    """Validate XMLs and copy valid ones to 'valid_xml'."""
    print("[3/7] Validating XML files...")
    validate_xml.validate_and_copy_xmls(
        cfg["paths"]["extracted_folder"],
        cfg["paths"]["valid_xml_folder"]
    )


def step_xml_to_json(cfg: dict) -> None:
    """Convert valid XMLs to JSON."""
    print("[4/7] Converting XML -> JSON...")
    xml_to_json.batch_convert_xml_to_json(
        cfg["paths"]["valid_xml_folder"],
        cfg["paths"]["json_folder"]
    )


def step_validate_json(cfg: dict) -> None:
    """
    Filter JSON entries by REQUIRED_KEYS using your valid_json.py.
    NOTE: valid_json.py uses module-level constants, we override them here.
    """
    print("[5/7] Filtering JSON entries by required keys...")
    valid_json.input_folder = cfg["paths"]["json_folder"]
    valid_json.output_folder = cfg["paths"]["valid_json_folder"]
    # If you want to override REQUIRED_KEYS from config, uncomment:
    # valid_json.REQUIRED_KEYS = cfg["validation"].get("required_keys", valid_json.REQUIRED_KEYS)
    valid_json.process_all_jsons()


def step_build_geojson_all(cfg: dict) -> None:
    """Create one big FeatureCollection from all valid JSON files."""
    print("[6/7] Building all-points GeoJSON...")
    ensure_dir(os.path.dirname(cfg["outputs"]["all_points_geojson"]))
    json_to_geojson_batch.convert_all_json_to_geojson(
        cfg["paths"]["valid_json_folder"],
        cfg["outputs"]["all_points_geojson"]
    )


def step_build_geojson_by_state(cfg: dict) -> None:
    """Optional: Create per-state GeoJSONs using polygon containment (requires shapely + polygons)."""
    if not cfg.get("state_polygons", {}).get("enabled", False):
        print("[7/7] State polygons step is disabled in config. Skipping.")
        return
    if not HAS_POLYGON_STEP:
        print("[7/7] generate_geojson_by_state_polygons module not available. Skipping.")
        return

    print("[7/7] Building per-state GeoJSONs via polygons...")
    # generate_geojson_by_state_polygons reads polygon file on import; we just call its function.
    # If you want to change the polygon path dynamically, set an env var or modify that module.
    generate_geojson_by_state_polygons.convert_jsons(
        cfg["paths"]["valid_json_folder"],
        cfg["outputs"]["by_state_geojson_folder"]
    )


def main():
    # 1) Load config
    cfg_path = os.environ.get("MASTR_CFG", "merged_path.json")
    cfg = load_config(cfg_path)

    # 2) Ensure folders exist
    for key, path in cfg["paths"].items():
        ensure_dir(path)

    # 3) Run pipeline
    started = datetime.now()
    print(f"== MaStR ETL pipeline started at {started.strftime('%Y-%m-%d %H:%M:%S')} ==")

    try:
        if cfg["download"].get("enabled", True):
            step_download(cfg)
        else:
            print("[1/7] Download step disabled. Skipping.")

        step_extract(cfg)
        step_validate_xml(cfg)
        step_xml_to_json(cfg)
        step_validate_json(cfg)
        step_build_geojson_all(cfg)
        step_build_geojson_by_state(cfg)

        print("\n✔ Pipeline completed successfully.")

    except Exception:
        print("\n✖ Pipeline failed with an unexpected error:")
        traceback.print_exc()

    finally:
        finished = datetime.now()
        delta = finished - started
        print(f"== Finished at {finished.strftime('%Y-%m-%d %H:%M:%S')} (elapsed {delta}) ==")


if __name__ == "__main__":
    main()
