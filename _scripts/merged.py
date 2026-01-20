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
import step15_generate_geojson_by_state_4checks as step15
import step16_generate_geojson_by_state_4checks_yearly as step16
import step17_generate_geojson_by_state_landkreis as step17
import step18_generate_geojson_by_state_landkreis_yearly as step18
import step19_generate_geojson_by_landkreis as step19
import step20_generate_geojson_by_landkreis_yearly as step20
import step21_filter_json_by_state_4checks as step21
import step22_filter_json_by_state_4checks_yearly as step22
import step23_filter_json_by_state_landkreis as step23
import step24_filter_json_by_state_landkreis_yearly as step24
import step25_filter_json_by_landkreis as step25
import step26_filter_json_by_landkreis_yearly as step26



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
    print("🚀  MaStR Automation Start (Step 10 → Step 26)")
    print("==============================\n")

    cfg = load_config("merged_path.json")
    paths = cfg["paths"]
    gadm_path = cfg["gadm_polygons"]["gadm_l2_path"]
    poly_path = cfg["state_3checks"]["polygon_states_path"]
    steps_enabled = cfg.get("steps", {})

    # Step 10..26 inclusive => 17 steps
    total_steps = 17
    step_no = 0

    def step(msg: str):
        nonlocal step_no
        step_no += 1
        log_step(step_no, total_steps, msg)

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
        # step11 expects a LIST of codes (see step11 script)
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
        # still count 4 steps for consistent numbering
        for _ in range(4):
            step("Filtering skipped")
            log_skip(step_no, total_steps, "filtering disabled")

    # ---- STEP 14–20: GeoJSON generation ----
    if steps_enabled.get("geojson", True):
        step("Step 14 - All-Germany GeoJSON (keep step14 as-is)")
        safe_run(
            step14.convert_all_germany_with_three_checks,
            paths["active_json_folder"],
            poly_path,
            cfg["outputs"]["all_points_geojson"],
            os.path.join(os.path.dirname(cfg["outputs"]["all_points_geojson"]), "_consistency_summary.json"),
        )

        step("Step 15 - Per-state GeoJSON (4 checks)")
        safe_run(
            step15.convert_with_4_checks,
            paths["active_json_folder"],
            paths["geojson_by_state_4_checks_folder"],
            poly_path,
            gadm_path,
        )

        step("Step 16 - Per-state yearly GeoJSON (4 checks)")
        safe_run(
            step16.convert_by_state_year_with_4_checks,
            paths["active_json_folder"],
            paths["geojson_by_state_yearly_4_checks_folder"],
            poly_path,
            cfg["date_fields"]["commissioning"],
        )

        step("Step 17 - GeoJSON by state & Landkreis")
        safe_run(
            step17.convert_by_state_landkreis,
            paths["active_json_folder"],
            paths["geojson_by_state_landkreis_folder"],
            gadm_path,
        )

        step("Step 18 - GeoJSON by state, Landkreis & year")
        safe_run(
            step18.convert_state_landkreis_yearly,
            paths["active_json_folder"],
            paths["geojson_by_state_landkreis_yearly_folder"],
            gadm_path,
            cfg["date_fields"]["commissioning"],
        )

        step("Step 19 - GeoJSON by Landkreis (nationwide)")
        safe_run(
            step19.convert_by_landkreis,
            paths["active_json_folder"],
            paths["geojson_by_landkreis_folder"],
            gadm_path,
        )

        step("Step 20 - GeoJSON by Landkreis yearly (nationwide)")
        # step20 uses internal INPUT_FOLDER/OUTPUT_ROOT constants (no args)
        safe_run(step20.convert_landkreis_yearly)
    else:
        for _ in range(7):
            step("GeoJSON skipped")
            log_skip(step_no, total_steps, "geojson disabled")

    # ---- STEP 21–26: Post-filtering (4 checks + Landkreis grouping) ----
    if steps_enabled.get("post_filtering_4checks", True):
        step("Step 21 - Filter JSON by state (4 checks)")
        safe_run(
            step21.filter_json_by_state_three_checks,
            paths["active_json_folder"],
            paths["filtered_json_by_state_4checks_folder"],
            poly_path,
        )

        step("Step 22 - Filter JSON by state yearly (4 checks)")
        safe_run(
            step22.filter_json_by_state_year_four_checks,
            paths["active_json_folder"],
            paths["filtered_json_by_state_yearly_4checks_folder"],
            poly_path,
            gadm_path,
            cfg["date_fields"]["commissioning"],
        )

        step("Step 23 - Filter JSON by state + Landkreis")
        safe_run(
            step23.filter_json_by_state_landkreis,
            paths["filtered_json_by_state_4checks_folder"],
            paths["filtered_json_by_state_landkreis_folder"],
            gadm_path,
        )

        step("Step 24 - Filter JSON by state + Landkreis yearly")
        safe_run(
            step24.filter_json_by_state_landkreis_yearly,
            paths["filtered_json_by_state_yearly_4checks_folder"],
            paths["filtered_json_by_state_landkreis_yearly_folder"],
            gadm_path,
            cfg["date_fields"]["commissioning"],
        )

        step("Step 25 - Filter JSON by Landkreis (nationwide)")
        safe_run(
            step25.filter_json_by_landkreis,
            paths["filtered_json_by_state_4checks_folder"],
            paths["filtered_json_by_landkreis_folder"],
            gadm_path,
        )

        step("Step 26 - Filter JSON by Landkreis yearly (nationwide)")
        safe_run(
            step26.filter_json_by_landkreis_yearly,
            paths["filtered_json_by_state_yearly_4checks_folder"],
            paths["filtered_json_by_landkreis_yearly_folder"],
            gadm_path,
            cfg["date_fields"]["commissioning"],
        )
    else:
        for _ in range(6):
            step("Post-filtering skipped")
            log_skip(step_no, total_steps, "post_filtering_4checks disabled")

    print("==============================")
    print("✅ MaStR Pipeline Finished")
    print("==============================\n")


if __name__ == "__main__":
    main()
