import os
import json
from datetime import datetime

# === Import all step scripts ===
import step1_download_mastr as step1
import step2_extract_zip as step2
import step3_validate_xml as step3
import step4_xml_to_json as step4
import step5_valid_json as step5
import step6_filter_json_by_active_status as step6
import step7_list_states as step7
import step8_list_energy_types as step8
import step9_list_years as step9
import step10_filter_json_by_energy_code as step10
import step11_filter_json_by_state_bundesland as step11
import step12_filter_json_by_state_gemeindeschluessel as step12
import step13_filter_json_by_installation_year as step13
import step14_json_to_geojson_batch as step14
import step15_generate_geojson_by_state_3checks as step15
import step16_generate_geojson_by_state_3checks_yearly as step16
import step17_generate_geojson_by_state_landkreis as step17
import step18_generate_geojson_by_state_landkreis_yearly as step18
import step19_generate_geojson_by_landkreis as step19


# === Helper functions ===
def load_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def log_step(num: int, total: int, message: str):
    print(f"\n[{num}/{total}] 🔹 {message}")


def log_done():
    print("   ✅ Done.\n")


def log_skip(num: int, total: int, reason: str):
    print(f"[{num}/{total}] ⏩ Skipped step ({reason})")


def log_warn(msg: str):
    print(f"   ⚠ {msg}\n")


def safe_run(func, *args, **kwargs):
    """Run a function safely so pipeline continues even if one step fails."""
    try:
        func(*args, **kwargs)
        log_done()
    except Exception as e:
        log_warn(f"Step failed: {e}")


# === MAIN PIPELINE ===
def main():
    print("\n==============================")
    print("🚀  MaStR Full Automation Start")
    print("==============================\n")

    cfg = load_config("merged_path.json")
    paths = cfg["paths"]
    url = cfg["download"]["url"]
    gadm_path = cfg["gadm_polygons"]["gadm_l2_path"]
    poly_path = cfg["state_3checks"]["polygon_states_path"]
    steps_enabled = cfg.get("steps", {})

    total_steps = 19

    # --- STEP 1: Download ZIP ---
    if steps_enabled.get("download", True):
        log_step(1, total_steps, "Downloading MaStR ZIP")
        safe_run(step1.download_file, url, destination_folder=paths["raw_data_folder"])
    else:
        log_skip(1, total_steps, "using existing raw data")

    # --- STEP 2: Extract ZIP ---
    if steps_enabled.get("extract", True):
        log_step(2, total_steps, "Extracting ZIP files")
        safe_run(step2.extract_all_zips, paths["raw_data_folder"], paths["extracted_folder"])
    else:
        log_skip(2, total_steps, "using already extracted files")

    # --- STEP 3: Validate XML ---
    if steps_enabled.get("validate_xml", True):
        log_step(3, total_steps, "Validating XML files")
        safe_run(step3.validate_and_copy_xmls, paths["extracted_folder"], paths["valid_xml_folder"])
    else:
        log_skip(3, total_steps, "using existing valid XMLs")

    # --- STEP 4: Convert XML → JSON ---
    if steps_enabled.get("xml_to_json", True):
        log_step(4, total_steps, "Converting XML → JSON")
        safe_run(step4.batch_convert_xml_to_json, paths["valid_xml_folder"], paths["json_folder"])
    else:
        log_skip(4, total_steps, "using existing JSON files")

    # --- STEP 5: Valid JSON ---
    if steps_enabled.get("valid_json", True):
        log_step(5, total_steps, "Filtering JSON entries by required keys")
        step5.input_folder = paths["json_folder"]
        step5.output_folder = paths["valid_json_folder"]
        safe_run(step5.process_all_jsons)
    else:
        log_skip(5, total_steps, "using existing valid JSON files")

    # --- STEP 6: Active JSON Filter ---
    if steps_enabled.get("filter_active", True):
        log_step(6, total_steps, "Filtering active power plants (EinheitBetriebsstatus=35)")
        step6.input_folder = paths["valid_json_folder"]
        step6.output_folder = paths["active_json_folder"]
        safe_run(step6.filter_active_jsons)
    else:
        log_skip(6, total_steps, "using existing active JSONs")

    # --- STEP 7: List States ---
    if steps_enabled.get("metadata_listing", True):
        log_step(7, total_steps, "Listing available states (Bundesland codes)")
        safe_run(step7.list_state_codes, paths["active_json_folder"])
    else:
        log_skip(7, total_steps, "metadata listing skipped")

    # --- STEP 8: List Energy Types ---
    if steps_enabled.get("metadata_listing", True):
        log_step(8, total_steps, "Listing available energy carrier codes (Energieträger)")
        safe_run(step8.list_energy_codes, paths["active_json_folder"])
    else:
        log_skip(8, total_steps, "metadata listing skipped")

    # --- STEP 9: List Years ---
    if steps_enabled.get("metadata_listing", True):
        log_step(9, total_steps, "Listing commissioning years")
        safe_run(step9.list_installation_years, paths["active_json_folder"])
    else:
        log_skip(9, total_steps, "metadata listing skipped")

    # --- STEP 10–13: Filtering ---
    if steps_enabled.get("filtering", True):
        log_step(10, total_steps, "Filtering by energy codes")
        safe_run(
            step10.filter_by_energy_codes,
            input_folder=paths["active_json_folder"],
            output_base_folder=paths["filtered_json_by_energy_code_folder"],
            energy_key="Energietraeger",
            energy_codes=cfg["energy_codes"]
        )

        log_step(11, total_steps, "Filtering by Bundesland codes")
        safe_run(
            step11.filter_by_state_codes,
            paths["active_json_folder"],
            paths["filtered_json_by_state_bundesland_folder"],
            "Bundesland",
            cfg["state_codes"]
        )

        log_step(12, total_steps, "Filtering by Gemeindeschlüssel prefixes")
        safe_run(step12.filter_by_state_prefix, paths["active_json_folder"], paths["filtered_json_by_state_gemeindeschluessel_folder"])

        log_step(13, total_steps, "Filtering by installation years")
        safe_run(step13.filter_by_installation_years, paths["active_json_folder"], paths["filtered_json_by_year_folder"])
    else:
        log_skip(10, total_steps, "filtering steps skipped")

    # --- STEP 14–19: GeoJSON Generation ---
    if steps_enabled.get("geojson", True):
        log_step(14, total_steps, "Generating all-Germany GeoJSON (3-check consistency)")
        safe_run(
            step14.convert_all_germany_with_three_checks,
            paths["active_json_folder"],
            poly_path,
            cfg["outputs"]["all_points_geojson"],
            os.path.join(os.path.dirname(cfg["outputs"]["all_points_geojson"]), "_consistency_summary.json")
        )

        log_step(15, total_steps, "Generating per-state GeoJSON (3-checks)")
        safe_run(step15.convert_with_three_checks, paths["active_json_folder"], paths["geojson_by_state_three_checks_folder"], poly_path)

        log_step(16, total_steps, "Generating per-state yearly GeoJSON (3-checks + year)")
        safe_run(step16.convert_by_state_year_with_three_checks, paths["active_json_folder"], paths["geojson_by_state_yearly_three_checks_folder"], poly_path, cfg["date_fields"]["commissioning"])

        log_step(17, total_steps, "Generating GeoJSON grouped by state & Landkreis")
        safe_run(step17.convert_by_state_landkreis, paths["active_json_folder"], paths["geojson_by_state_landkreis_folder"], gadm_path)

        log_step(18, total_steps, "Generating GeoJSON grouped by state, Landkreis & year")
        safe_run(step18.convert_state_landkreis_yearly, paths["active_json_folder"], paths["geojson_by_state_landkreis_yearly_folder"], gadm_path, cfg["date_fields"]["commissioning"])

        log_step(19, total_steps, "Generating GeoJSON grouped by Landkreis (all states)")
        safe_run(step19.convert_by_landkreis, paths["active_json_folder"], paths["geojson_by_landkreis_folder"], gadm_path)
    else:
        log_skip(14, total_steps, "GeoJSON generation skipped")

    print("==============================")
    print("✅ MaStR Full Pipeline Finished")
    print("==============================\n")


if __name__ == "__main__":
    main()
