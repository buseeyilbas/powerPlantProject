# Filename: merged.py
# Purpose:
#   Single pipeline runner for MaStR processing steps.
#   - Supports step6a + step6b split (to avoid duplicate "step7" naming).
#   - Updates step15+ numbering based on the new file names / ordering.
#   - Overrides hardcoded INPUT_FOLDER/OUTPUT_ROOT style module configs from merged_path.json.

import os
import json

# === Import all step scripts ===
import step1_download_mastr as step1
import step2_extract_zip as step2
import step3_validate_xml as step3
import step4_xml_to_json as step4
import step5_valid_json as step5

import step6a_filter_json_by_active_status as step6a
import step6b_analyze_active_jsons_2ndfiltering as step6b

import step7_list_states as step7
import step8_list_energy_types as step8
import step9_list_years as step9

import step10_filter_json_by_energy_code as step10
import step11_filter_json_by_state_bundesland as step11
import step12_filter_json_by_state_gemeindeschluessel as step12
import step13_filter_json_by_installation_year as step13

import step14_json_to_geojson_batch as step14

# NEW step15+ (FILTER)
import step15_filter_json_by_state_4checks as step15
import step16_filter_json_by_state_4checks_yearly as step16
import step17_filter_json_by_state_landkreis as step17
import step18_filter_json_by_state_landkreis_yearly as step18
import step19_filter_json_by_landkreis as step19
import step20_filter_json_by_landkreis_yearly as step20

# NEW step21+ (GEOJSON GENERATE)
import step21_generate_geojson_by_state_4checks as step21
import step22_generate_geojson_by_state_4checks_yearly as step22
import step23_generate_geojson_by_state_landkreis as step23
import step24_generate_geojson_by_state_landkreis_yearly as step24
import step25_generate_geojson_by_landkreis as step25
import step26_generate_geojson_by_landkreis_yearly as step26

import step27_data_quality as step27
import step28_match_anlagen_einheiten_files as step28


# === Helper functions ===
def load_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def log_step(num: int, total: int, message: str) -> None:
    print(f"\n[{num}/{total}] 🔹 {message}")


def log_done() -> None:
    print("   ✅ Done.\n")


def log_skip(num: int, total: int, reason: str) -> None:
    print(f"[{num}/{total}] ⏩ Skipped step ({reason})")


def log_warn(msg: str) -> None:
    print(f"   ⚠ {msg}\n")


def safe_run(func, *args, **kwargs) -> None:
    """Run a function safely so pipeline continues even if one step fails."""
    try:
        func(*args, **kwargs)
        log_done()
    except Exception as e:
        log_warn(f"Step failed: {e}")


def _override_module_paths_for_step6a(paths: dict) -> None:
    # step6a uses module-level input_folder / output_folder
    if "valid_json_folder" in paths:
        step6a.input_folder = paths["valid_json_folder"]
    if "active_json_folder" in paths:
        step6a.output_folder = paths["active_json_folder"]


def _override_module_paths_for_step6b(paths: dict, poly_path: str, gadm_path: str) -> None:
    # step6b uses module-level INPUT_FOLDER / OUTPUT_FOLDER / POLYGON_STATES_PATH / GADM_L2_PATH
    if "active_json_folder" in paths:
        step6b.INPUT_FOLDER = paths["active_json_folder"]
    # Put outputs somewhere predictable; if you want, add it to merged_path.json later
    step6b.OUTPUT_FOLDER = os.path.join(os.path.dirname(paths["active_json_folder"]), "exports_step6b_analysis")
    step6b.POLYGON_STATES_PATH = poly_path
    step6b.GADM_L2_PATH = gadm_path


def _override_module_paths_for_geojson_generators(paths: dict, poly_path: str, gadm_path: str, commissioning_field: str) -> None:
    """
    Some geojson generator scripts (step21/22/24/26 etc.) often have hardcoded
    INPUT_FOLDER / OUTPUT_ROOT / POLYGON_STATES_PATH / GADM_L2_PATH / DATE_FIELD.
    We override them here so everything is driven by merged_path.json.
    """

    # Step21: by_state_4_checks
    if hasattr(step21, "INPUT_FOLDER"):
        step21.INPUT_FOLDER = paths["filtered_json_by_state_4checks_folder"]
    if hasattr(step21, "OUTPUT_ROOT"):
        step21.OUTPUT_ROOT = paths["geojson_by_state_4_checks_folder"]
    if hasattr(step21, "POLYGON_STATES_PATH"):
        step21.POLYGON_STATES_PATH = poly_path
    if hasattr(step21, "GADM_L2_PATH"):
        step21.GADM_L2_PATH = gadm_path

    # Step22: by_state_yearly_4_checks
    if hasattr(step22, "INPUT_FOLDER"):
        step22.INPUT_FOLDER = paths["filtered_json_by_state_yearly_4checks_folder"]
    if hasattr(step22, "OUTPUT_ROOT"):
        step22.OUTPUT_ROOT = paths["geojson_by_state_yearly_4_checks_folder"]
    if hasattr(step22, "POLYGON_STATES_PATH"):
        step22.POLYGON_STATES_PATH = poly_path
    if hasattr(step22, "GADM_L2_PATH"):
        step22.GADM_L2_PATH = gadm_path
    if hasattr(step22, "DATE_FIELD"):
        step22.DATE_FIELD = commissioning_field

    # Step23: by_state_landkreis
    if hasattr(step23, "INPUT_FOLDER"):
        step23.INPUT_FOLDER = paths["filtered_json_by_state_4checks_folder"]
    if hasattr(step23, "OUTPUT_ROOT"):
        step23.OUTPUT_ROOT = paths["geojson_by_state_landkreis_folder"]
    if hasattr(step23, "GADM_L2_PATH"):
        step23.GADM_L2_PATH = gadm_path

    # Step24: by_state_landkreis_yearly
    if hasattr(step24, "INPUT_FOLDER"):
        step24.INPUT_FOLDER = paths["filtered_json_by_state_yearly_4checks_folder"]
    if hasattr(step24, "OUTPUT_ROOT"):
        step24.OUTPUT_ROOT = paths["geojson_by_state_landkreis_yearly_folder"]
    if hasattr(step24, "POLYGON_STATES_PATH"):
        step24.POLYGON_STATES_PATH = poly_path
    if hasattr(step24, "GADM_L2_PATH"):
        step24.GADM_L2_PATH = gadm_path
    if hasattr(step24, "DATE_FIELD"):
        step24.DATE_FIELD = commissioning_field

    # Step25: by_landkreis
    if hasattr(step25, "INPUT_FOLDER"):
        step25.INPUT_FOLDER = paths["filtered_json_by_state_4checks_folder"]
    if hasattr(step25, "OUTPUT_ROOT"):
        step25.OUTPUT_ROOT = paths["geojson_by_landkreis_folder"]
    if hasattr(step25, "GADM_L2_PATH"):
        step25.GADM_L2_PATH = gadm_path

    # Step26: by_landkreis_yearly
    if hasattr(step26, "INPUT_FOLDER"):
        step26.INPUT_FOLDER = paths["filtered_json_by_state_yearly_4checks_folder"]
    if hasattr(step26, "OUTPUT_ROOT"):
        step26.OUTPUT_ROOT = paths["geojson_by_landkreis_yearly_folder"]
    if hasattr(step26, "POLYGON_STATES_PATH"):
        step26.POLYGON_STATES_PATH = poly_path
    if hasattr(step26, "GADM_L2_PATH"):
        step26.GADM_L2_PATH = gadm_path
    if hasattr(step26, "DATE_FIELD"):
        step26.DATE_FIELD = commissioning_field


# === MAIN PIPELINE ===
def main() -> None:
    print("\n==============================")
    print("🚀  MaStR Automation Start (Step 6a → Step 28)")
    print("==============================\n")

    cfg = load_config("merged_path.json")
    paths = cfg["paths"]

    gadm_path = cfg["gadm_polygons"]["gadm_l2_path"]
    poly_path = cfg["state_3checks"]["polygon_states_path"]
    steps_enabled = cfg.get("steps", {})

    commissioning_field = cfg.get("date_fields", {}).get("commissioning", "Inbetriebnahmedatum")

    # Total steps:
    # 6a, 6b, 7, 8, 9, 10-13, 14, 15-20, 21-26, 27, 28
    total_steps = 24
    step_no = 0

    def step(msg: str) -> None:
        nonlocal step_no
        step_no += 1
        log_step(step_no, total_steps, msg)

    # ---- STEP 1–5 (optional legacy) ----
    # Kept for completeness; your merged_path.json already disables them.
    if steps_enabled.get("download", False):
        step("Step 1 - Download MaStR ZIP")
        safe_run(step1.download_mastr_zip, cfg["download"]["url"], paths["raw_data_folder"])
    else:
        step("Step 1 - Download skipped")
        log_skip(step_no, total_steps, "download disabled")

    if steps_enabled.get("extract", False):
        step("Step 2 - Extract ZIP")
        safe_run(step2.extract_zip, paths["raw_data_folder"], paths["extracted_folder"])
    else:
        step("Step 2 - Extract skipped")
        log_skip(step_no, total_steps, "extract disabled")

    if steps_enabled.get("validate_xml", False):
        step("Step 3 - Validate XML")
        safe_run(step3.validate_xml_files, paths["extracted_folder"], paths["valid_xml_folder"])
    else:
        step("Step 3 - Validate XML skipped")
        log_skip(step_no, total_steps, "validate_xml disabled")

    if steps_enabled.get("xml_to_json", False):
        step("Step 4 - XML to JSON")
        safe_run(step4.convert_xml_to_json, paths["valid_xml_folder"], paths["json_folder"])
    else:
        step("Step 4 - XML to JSON skipped")
        log_skip(step_no, total_steps, "xml_to_json disabled")

    if steps_enabled.get("valid_json", False):
        step("Step 5 - Validate JSON")
        safe_run(step5.validate_json_files, paths["json_folder"], paths["valid_json_folder"])
    else:
        step("Step 5 - Validate JSON skipped")
        log_skip(step_no, total_steps, "valid_json disabled")

    # ---- STEP 6a: Filter active ----
    if steps_enabled.get("filter_active", False):
        step("Step 6a - Filter active JSONs (EinheitBetriebsstatus == 35)")
        _override_module_paths_for_step6a(paths)
        safe_run(step6a.filter_active_jsons)
    else:
        step("Step 6a - Filter active skipped")
        log_skip(step_no, total_steps, "filter_active disabled")

    # ---- STEP 6b: Analyze active JSONs (2nd filtering / report) ----
    # This is not in your merged_path.json by default, so it stays off unless you add the flag.
    if steps_enabled.get("analyze_active_second_stage", False):
        step("Step 6b - Analyze ACTIVE JSONs (4-check gated min/max report)")
        _override_module_paths_for_step6b(paths, poly_path, gadm_path)
        safe_run(step6b.analyze)
    else:
        step("Step 6b - Analyze active skipped")
        log_skip(step_no, total_steps, "analyze_active_second_stage disabled")

    # ---- STEP 7–9: Listing helpers (optional) ----
    if steps_enabled.get("list_states", False):
        step("Step 7 - List states")
        safe_run(step7.list_states)
    else:
        step("Step 7 - List states skipped")
        log_skip(step_no, total_steps, "list_states disabled")

    if steps_enabled.get("list_energy_types", False):
        step("Step 8 - List energy types")
        safe_run(step8.list_energy_types)
    else:
        step("Step 8 - List energy types skipped")
        log_skip(step_no, total_steps, "list_energy_types disabled")

    if steps_enabled.get("list_years", False):
        step("Step 9 - List years")
        safe_run(step9.list_years)
    else:
        step("Step 9 - List years skipped")
        log_skip(step_no, total_steps, "list_years disabled")

    # ---- STEP 10–13: Filtering (from active_json) ----
    if steps_enabled.get("filtering", True):
        step("Step 10 - Filtering by energy codes")
        safe_run(
            step10.filter_by_energy_codes,
            input_folder=paths["active_json_folder"],
            output_base_folder=paths["filtered_json_by_energy_code_folder"],
            energy_key="Energietraeger",
            energy_codes=cfg["energy_codes"],
        )

        step("Step 11 - Filtering by Bundesland codes")
        state_codes = cfg["state_codes"]
        if isinstance(state_codes, dict):
            state_codes = list(state_codes.keys())

        safe_run(
            step11.filter_by_state_codes,
            paths["active_json_folder"],
            paths["filtered_json_by_state_bundesland_folder"],
            "Bundesland",
            state_codes,
        )

        step("Step 12 - Filtering by Gemeindeschluessel prefixes")
        safe_run(
            step12.filter_by_state_prefix,
            paths["active_json_folder"],
            paths["filtered_json_by_state_gemeindeschluessel_folder"],
        )

        step("Step 13 - Filtering by installation years")
        safe_run(
            step13.filter_by_installation_years,
            paths["active_json_folder"],
            paths["filtered_json_by_year_folder"],
        )
    else:
        for _ in range(4):
            step("Filtering skipped")
            log_skip(step_no, total_steps, "filtering disabled")

    # ---- STEP 14: All-Germany GeoJSON (keep as-is) ----
    if steps_enabled.get("geojson_all_germany", True):
        step("Step 14 - All-Germany GeoJSON (3 checks batch)")
        safe_run(
            step14.convert_all_germany_with_three_checks,
            paths["active_json_folder"],
            poly_path,
            cfg["outputs"]["all_points_geojson"],
            os.path.join(os.path.dirname(cfg["outputs"]["all_points_geojson"]), "_consistency_summary.json"),
        )
    else:
        step("Step 14 - All-Germany GeoJSON skipped")
        log_skip(step_no, total_steps, "geojson_all_germany disabled")

    # ---- STEP 15–20: Post-filtering (4 checks + Landkreis grouping) ----
    if steps_enabled.get("post_filtering_4checks", True):
        step("Step 15 - Filter JSON by state (4 checks)")
        safe_run(
            step15.filter_json_by_state_three_checks,
            paths["active_json_folder"],
            paths["filtered_json_by_state_4checks_folder"],
            poly_path,
        )

        step("Step 16 - Filter JSON by state yearly (4 checks)")
        safe_run(
            step16.filter_json_by_state_year_four_checks,
            paths["active_json_folder"],
            paths["filtered_json_by_state_yearly_4checks_folder"],
            poly_path,
            gadm_path,
            commissioning_field,
        )

        step("Step 17 - Filter JSON by state + Landkreis")
        safe_run(
            step17.filter_json_by_state_landkreis,
            paths["filtered_json_by_state_4checks_folder"],
            paths["filtered_json_by_state_landkreis_folder"],
            gadm_path,
        )

        step("Step 18 - Filter JSON by state + Landkreis yearly")
        safe_run(
            step18.filter_json_by_state_landkreis_yearly,
            paths["filtered_json_by_state_yearly_4checks_folder"],
            paths["filtered_json_by_state_landkreis_yearly_folder"],
            gadm_path,
            commissioning_field,
        )

        step("Step 19 - Filter JSON by Landkreis (nationwide)")
        safe_run(
            step19.filter_json_by_landkreis,
            paths["filtered_json_by_state_4checks_folder"],
            paths["filtered_json_by_landkreis_folder"],
            gadm_path,
        )

        step("Step 20 - Filter JSON by Landkreis yearly (nationwide)")
        safe_run(
            step20.filter_json_by_landkreis_yearly,
            paths["filtered_json_by_state_yearly_4checks_folder"],
            paths["filtered_json_by_landkreis_yearly_folder"],
            gadm_path,
            commissioning_field,
        )
    else:
        for _ in range(6):
            step("Post-filtering skipped")
            log_skip(step_no, total_steps, "post_filtering_4checks disabled")

    # ---- STEP 21–26: GeoJSON generation (from filtered folders) ----
    if steps_enabled.get("geojson", True):
        _override_module_paths_for_geojson_generators(paths, poly_path, gadm_path, commissioning_field)

        step("Step 21 - Generate GeoJSON by state (4 checks)")
        # Some scripts have args, some are module-config based. We try both patterns safely.
        if hasattr(step21, "convert_with_4_checks"):
            safe_run(
                step21.convert_with_4_checks,
                paths["active_json_folder"],
                paths["geojson_by_state_4_checks_folder"],
                poly_path,
                gadm_path,
            )
        elif hasattr(step21, "convert_by_state_4checks"):
            safe_run(step21.convert_by_state_4checks)
        elif hasattr(step21, "main"):
            safe_run(step21.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step21 module")))

        step("Step 22 - Generate GeoJSON by state yearly (4 checks)")
        if hasattr(step22, "convert_by_state_year_with_4_checks"):
            safe_run(
                step22.convert_by_state_year_with_4_checks,
                paths["active_json_folder"],
                paths["geojson_by_state_yearly_4_checks_folder"],
                poly_path,
                commissioning_field,
            )
        elif hasattr(step22, "convert_state_yearly_4checks"):
            safe_run(step22.convert_state_yearly_4checks)
        elif hasattr(step22, "main"):
            safe_run(step22.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step22 module")))

        step("Step 23 - Generate GeoJSON by state & Landkreis")
        if hasattr(step23, "convert_by_state_landkreis"):
            safe_run(step23.convert_by_state_landkreis, paths["filtered_json_by_state_4checks_folder"], paths["geojson_by_state_landkreis_folder"], gadm_path)
        elif hasattr(step23, "main"):
            safe_run(step23.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step23 module")))

        step("Step 24 - Generate GeoJSON by state, Landkreis & year")
        if hasattr(step24, "convert_state_landkreis_yearly"):
            safe_run(step24.convert_state_landkreis_yearly)
        elif hasattr(step24, "main"):
            safe_run(step24.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step24 module")))

        step("Step 25 - Generate GeoJSON by Landkreis (nationwide)")
        if hasattr(step25, "convert_by_landkreis"):
            safe_run(step25.convert_by_landkreis, paths["filtered_json_by_state_4checks_folder"], paths["geojson_by_landkreis_folder"], gadm_path)
        elif hasattr(step25, "main"):
            safe_run(step25.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step25 module")))

        step("Step 26 - Generate GeoJSON by Landkreis yearly (nationwide)")
        if hasattr(step26, "convert_landkreis_yearly"):
            safe_run(step26.convert_landkreis_yearly)
        elif hasattr(step26, "main"):
            safe_run(step26.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No callable entrypoint found in step26 module")))
    else:
        for _ in range(6):
            step("GeoJSON generation skipped")
            log_skip(step_no, total_steps, "geojson disabled")

    # ---- STEP 27: Data quality ----
    if steps_enabled.get("data_quality", False):
        step("Step 27 - Data quality checks")
        if hasattr(step27, "main"):
            safe_run(step27.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No main() found in step27_data_quality.py")))
    else:
        step("Step 27 - Data quality skipped")
        log_skip(step_no, total_steps, "data_quality disabled")

    # ---- STEP 28: Match Anlagen/Einheiten ----
    if steps_enabled.get("match_anlagen_einheiten", False):
        step("Step 28 - Match Anlagen/Einheiten and check power consistency")
        if hasattr(step28, "main"):
            safe_run(step28.main)
        else:
            safe_run(lambda: (_ for _ in ()).throw(RuntimeError("No main() found in step28_match_anlagen_einheiten_files.py")))
    else:
        step("Step 28 - Match Anlagen/Einheiten skipped")
        log_skip(step_no, total_steps, "match_anlagen_einheiten disabled")

    print("==============================")
    print("✅ MaStR Pipeline Finished")
    print("==============================\n")


if __name__ == "__main__":
    main()