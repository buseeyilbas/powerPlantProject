
import os
import json
from datetime import datetime

import download_mastr
import extract_zip
import validate_xml
import xml_to_json
import valid_json
import json_to_geojson_batch

# 3check step (polygon + Bundesland + Gemeindeschlüssel)
try:
    import generate_geojson_by_state_3checks as state_3checks
    HAS_3CHECKS = True
except Exception:
    HAS_3CHECKS = False


def load_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def step_download(cfg: dict) -> str:
    url = cfg["download"]["url"]
    dest = cfg["paths"]["raw_data_folder"]
    print(f"[1/7] Downloading ZIP from: {url}")
    return download_mastr.download_file(url, destination_folder=dest)


def step_extract(cfg: dict) -> None:
    print("[2/7] Extracting ZIP files...")
    extract_zip.extract_all_zips(
        cfg["paths"]["raw_data_folder"],
        cfg["paths"]["extracted_folder"]
    )


def step_validate_xml(cfg: dict) -> None:
    print("[3/7] Validating XML files...")
    validate_xml.validate_and_copy_xmls(
        cfg["paths"]["extracted_folder"],
        cfg["paths"]["valid_xml_folder"]
    )


def step_xml_to_json(cfg: dict) -> None:
    print("[4/7] Converting XML -> JSON...")
    xml_to_json.batch_convert_xml_to_json(
        cfg["paths"]["valid_xml_folder"],
        cfg["paths"]["json_folder"]
    )


def step_validate_json(cfg: dict) -> None:
    """
    Filter JSON entries by REQUIRED_KEYS using valid_json.py.
    You can override REQUIRED_KEYS via config if desired.
    """
    print("[5/7] Filtering JSON entries by required keys...")
    valid_json.input_folder = cfg["paths"]["json_folder"]
    valid_json.output_folder = cfg["paths"]["valid_json_folder"]
    
    valid_json.process_all_jsons()


def step_build_geojson_all(cfg: dict) -> None:
    
    print("[6/7] Building all-points GeoJSON...")
    ensure_dir(os.path.dirname(cfg["outputs"]["all_points_geojson"]))
    json_to_geojson_batch.convert_all_json_to_geojson(
        cfg["paths"]["valid_json_folder"],
        cfg["outputs"]["all_points_geojson"]
    ) 


def step_build_geojson_by_state_3checks(cfg: dict) -> None:
    
    opts = cfg.get("state_3checks", {})
    if not opts.get("enabled", False):
        print("[7/7] 3-checks per-state step is disabled in config. Skipping.")
        return
    if not HAS_3CHECKS:
        print("[7/7] Module generate_geojson_by_state_3checks not available. Skipping.")
        return

    in_folder = cfg["paths"]["valid_json_folder"]
    out_folder = cfg["outputs"]["by_state_three_checks_folder"]
    polygons_path = opts["polygon_states_path"]

    print("[7/7] Building per-state GeoJSONs via 3-check consistency filter...")
    ensure_dir(out_folder)
    state_3checks.convert_with_three_checks(
        input_folder=in_folder,
        output_folder=out_folder,
        polygon_states_path=polygons_path
    )


def main():
    # 1) Load config
    cfg_path = os.environ.get("MASTR_CFG", "merged_path.json")
    cfg = load_config(cfg_path)

    # 2) Ensure folders exist
    for _, path in cfg["paths"].items():
        ensure_dir(path)
    ensure_dir(os.path.dirname(cfg["outputs"]["all_points_geojson"]))
    ensure_dir(cfg["outputs"].get("by_state_three_checks_folder", ""))

    # 3) Run pipeline
    started = datetime.now()
    print(f"== MaStR ETL pipeline started at {started:%Y-%m-%d %H:%M:%S} ==")

    if cfg["download"].get("enabled", True):
        step_download(cfg)
    else:
        print("[1/7] Download step disabled. Skipping.")

    step_extract(cfg)
    step_validate_xml(cfg)
    step_xml_to_json(cfg)
    step_validate_json(cfg)
    step_build_geojson_all(cfg)
    step_build_geojson_by_state_3checks(cfg)

    print("\n✔ Pipeline completed successfully.")


if __name__ == "__main__":
    main()
