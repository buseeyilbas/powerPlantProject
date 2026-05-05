"""
Unit tests for step6b_analyze_active_jsons_2ndfiltering.py using pytest.

These tests cover:
- helper and parsing functions
- state and Landkreis geo helpers
- energy normalization logic
- CSV writing
- end-to-end analyze() output generation
"""

import csv
import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step6b_analyze_active_jsons_2ndfiltering as analyze_mod


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with input/output/data folders."""
    workspace = tmp_path
    input_dir = workspace / "active_json"
    output_dir = workspace / "exports"
    data_dir = workspace / "data"
    gadm_dir = workspace / "gadm"

    input_dir.mkdir()
    output_dir.mkdir()
    data_dir.mkdir()
    gadm_dir.mkdir()

    return {
        "workspace": workspace,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "data_dir": data_dir,
        "gadm_dir": gadm_dir,
    }


@pytest.fixture
def sample_state_geojson(temp_workspace):
    """Create a minimal state polygon GeoJSON file."""
    path = temp_workspace["data_dir"] / "polygon_states.json"

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Thüringen"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.0, 50.0], [11.0, 50.0], [11.0, 51.0], [10.0, 51.0], [10.0, 50.0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "Bayern"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[11.0, 48.0], [12.0, 48.0], [12.0, 49.0], [11.0, 49.0], [11.0, 48.0]]],
                },
            },
        ],
    }

    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def sample_gadm_l2_geojson(temp_workspace):
    """Create a minimal Landkreis-level GeoJSON file."""
    path = temp_workspace["gadm_dir"] / "gadm41_DEU_2.json"

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME_1": "Thüringen", "NAME_2": "Testkreis"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.1, 50.1], [10.9, 50.1], [10.9, 50.9], [10.1, 50.9], [10.1, 50.1]]],
                },
            }
        ],
    }

    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_ensure_dir_creates_directory(tmp_path):
    target = tmp_path / "new_folder" / "nested"
    assert not target.exists()

    analyze_mod.ensure_dir(str(target))

    assert target.exists()
    assert target.is_dir()


def test_read_json_reads_valid_json(tmp_path):
    path = tmp_path / "sample.json"
    payload = {"a": 1, "b": "x"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = analyze_mod.read_json(str(path))

    assert result == payload


def test_bytes_to_gb_mb_returns_expected_values():
    num_bytes = 1024 * 1024 * 5
    gb, mb = analyze_mod.bytes_to_gb_mb(num_bytes)

    assert gb == pytest.approx(5 / 1024)
    assert mb == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (" abc ", "abc"),
        (123, "123"),
    ],
)
def test_safe_str(value, expected):
    assert analyze_mod.safe_str(value) == expected


def test_pick_first_returns_first_non_empty_value():
    entry = {"a": "", "b": None, "c": " value ", "d": "later"}

    result = analyze_mod.pick_first(entry, ["a", "b", "c", "d"])

    assert result == "value"


def test_pick_first_returns_empty_when_nothing_found():
    entry = {"a": "", "b": None}

    result = analyze_mod.pick_first(entry, ["x", "a", "b"])

    assert result == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (5, 5.0),
        (5.5, 5.5),
        ("12,34", 12.34),
        ("9.8", 9.8),
        ("", None),
        ("abc", None),
        (float("nan"), None),
    ],
)
def test_parse_float_maybe(value, expected):
    result = analyze_mod.parse_float_maybe(value)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_parse_power_kw_reads_standard_power_field():
    entry = {"Bruttoleistung": "123,5"}

    result = analyze_mod.parse_power_kw(entry)

    assert result == pytest.approx(123.5)


def test_parse_power_kw_converts_watts_to_kw_above_threshold():
    entry = {"Bruttoleistung": "2000000"}

    result = analyze_mod.parse_power_kw(entry)

    assert result == pytest.approx(2000.0)


def test_parse_power_kw_returns_none_for_missing_power():
    entry = {"OtherField": "x"}

    result = analyze_mod.parse_power_kw(entry)

    assert result is None


def test_parse_date_returns_first_matching_date_field():
    entry = {"InbetriebnahmeDatum": "2020-05-01"}

    result = analyze_mod.parse_date(entry)

    assert result == "2020-05-01"


@pytest.mark.parametrize(
    ("date_str", "expected"),
    [
        ("2024-01-02", "2024"),
        ("1999", "1999"),
        ("", "unknown"),
        ("xx-01-01", "unknown"),
    ],
)
def test_extract_year(date_str, expected):
    assert analyze_mod.extract_year(date_str) == expected


def test_passes_limits_accepts_valid_entry(monkeypatch):
    monkeypatch.setattr(
        analyze_mod,
        "USER_LIMITS",
        {
            "power_kw_min": 10,
            "power_kw_max": 100,
            "commissioning_date_min": "2000-01-01",
            "commissioning_date_max": "2030-12-31",
        },
    )

    ok, reasons = analyze_mod.passes_limits(50, "2020-01-01")

    assert ok is True
    assert reasons == []


def test_passes_limits_collects_all_reasons(monkeypatch):
    monkeypatch.setattr(
        analyze_mod,
        "USER_LIMITS",
        {
            "power_kw_min": 10,
            "power_kw_max": 100,
            "commissioning_date_min": "2000-01-01",
            "commissioning_date_max": "2030-12-31",
        },
    )

    ok, reasons = analyze_mod.passes_limits(5, "1990-01-01")

    assert ok is False
    assert "power_kw < 10" in reasons
    assert "date < 2000-01-01" in reasons


def test_bundesland_code_to_name_known_and_unknown():
    assert analyze_mod.bundesland_code_to_name("1415") == "thueringen"
    assert analyze_mod.bundesland_code_to_name("9999") == "unknown"


def test_normalize_state_name_normalizes_special_chars():
    value = "Baden-Württemberg (Test)"
    result = analyze_mod.normalize_state_name(value)
    assert result == "badenwuerttembergtest"


def test_parse_point_parses_valid_point():
    entry = {"Laengengrad": "10,5", "Breitengrad": "50,5"}

    pt = analyze_mod.parse_point(entry)

    assert pt is not None
    assert pt.x == pytest.approx(10.5)
    assert pt.y == pytest.approx(50.5)


def test_parse_point_returns_none_for_invalid_coordinates():
    entry = {"Laengengrad": "500", "Breitengrad": "999"}

    pt = analyze_mod.parse_point(entry)

    assert pt is None


def test_load_state_polygons_returns_normalized_mapping(sample_state_geojson):
    polygons_by_norm, pretty_by_norm = analyze_mod.load_state_polygons(str(sample_state_geojson))

    assert "thueringen" in polygons_by_norm
    assert "bayern" in polygons_by_norm
    assert pretty_by_norm["thueringen"] == "Thüringen"
    assert isinstance(polygons_by_norm["thueringen"], MultiPolygon)


def test_polygon_state_of_point_finds_covering_state(sample_state_geojson):
    polygons_by_norm, _ = analyze_mod.load_state_polygons(str(sample_state_geojson))
    pt = Point(10.5, 50.5)

    result = analyze_mod.polygon_state_of_point(pt, polygons_by_norm)

    assert result == "thueringen"


def test_polygon_state_of_point_returns_none_when_no_match(sample_state_geojson):
    polygons_by_norm, _ = analyze_mod.load_state_polygons(str(sample_state_geojson))
    pt = Point(20.0, 60.0)

    result = analyze_mod.polygon_state_of_point(pt, polygons_by_norm)

    assert result is None


def test_bl_code_to_norm_name():
    assert analyze_mod.bl_code_to_norm_name("1415") == "thueringen"
    assert analyze_mod.bl_code_to_norm_name(None) is None
    assert analyze_mod.bl_code_to_norm_name("9999") is None


def test_gs_prefix_to_norm_name():
    assert analyze_mod.gs_prefix_to_norm_name("16012345") == "thueringen"
    assert analyze_mod.gs_prefix_to_norm_name("01ABC") == "schleswigholstein"
    assert analyze_mod.gs_prefix_to_norm_name(None) is None
    assert analyze_mod.gs_prefix_to_norm_name("9") is None


def test_load_gadm_l2_prepared_returns_prepared_geometries(sample_gadm_l2_geojson):
    result = analyze_mod.load_gadm_l2_prepared(str(sample_gadm_l2_geojson))

    assert len(result) == 1
    name_1, name_2, prepared = result[0]
    assert name_1 == "Thüringen"
    assert name_2 == "Testkreis"
    assert prepared is not None


def test_has_any_landkreis_match_true_and_false(sample_gadm_l2_geojson):
    prepared_l2 = analyze_mod.load_gadm_l2_prepared(str(sample_gadm_l2_geojson))

    inside = Point(10.5, 50.5)
    outside = Point(20.0, 60.0)

    assert analyze_mod.has_any_landkreis_match(inside, prepared_l2) is True
    assert analyze_mod.has_any_landkreis_match(outside, prepared_l2) is False


def test_normalize_energy_known_code():
    code, label = analyze_mod.normalize_energy("2497")

    assert code == "2497"
    assert label == "Windenergie Onshore - Onshore Wind Energy"


def test_normalize_energy_unknown_numeric():
    code, label = analyze_mod.normalize_energy("9999")

    assert code == "9999"
    assert label == "UNKNOWN"


def test_normalize_energy_known_label():
    code, label = analyze_mod.normalize_energy("Biogas - Biogas")

    assert code == "2493"
    assert label == "Biogas - Biogas"


def test_normalize_energy_unknown_text():
    code, label = analyze_mod.normalize_energy("Custom Energy")

    assert code == "unknown"
    assert label == "Custom Energy"


def test_get_energy_reads_from_candidate_keys():
    entry = {"Energietraeger": "2495"}

    code, label = analyze_mod.get_energy(entry)

    assert code == "2495"
    assert label == "Photovoltaik - Photovoltaics"


def test_write_csv_writes_rows(tmp_path):
    path = tmp_path / "out.csv"
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]

    analyze_mod.write_csv(str(path), rows)

    assert path.exists()
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 2
    assert reader[0]["a"] == "1"
    assert reader[0]["b"] == "x"


def test_write_csv_does_nothing_for_empty_rows(tmp_path):
    path = tmp_path / "empty.csv"

    analyze_mod.write_csv(str(path), [])

    assert not path.exists()


def test_extremum_ref_to_compact_dict_rounds_values():
    ref = analyze_mod.ExtremumRef(
        file_name="a.json",
        index_in_file=1,
        bundesland_code="1415",
        bundesland_name="thueringen",
        state_name_norm="thueringen",
        energy_code="2497",
        energy_label="Windenergie Onshore - Onshore Wind Energy",
        power_kw=12.123456789,
        commissioning_date="2020-01-01",
        commissioning_year="2020",
        lon=10.123456789,
        lat=50.987654321,
        google_maps_url="https://www.google.com/maps?q=50.987654321,10.123456789",
    )

    compact = ref.to_compact_dict()

    assert compact["power_kw"] == round(12.123456789, 6)
    assert compact["lon"] == round(10.123456789, 6)
    assert compact["lat"] == round(50.987654321, 6)


def test_analyze_end_to_end_generates_all_outputs(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    valid_entries = [
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 500,
            "Inbetriebnahmedatum": "2020-01-01",
            "Energietraeger": "2497",
        },
        {
            "Laengengrad": 10.6,
            "Breitengrad": 50.6,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000001",
            "Bruttoleistung": 100,
            "Inbetriebnahmedatum": "2010-01-01",
            "Energietraeger": "2497",
        },
        {
            "Laengengrad": 10.55,
            "Breitengrad": 50.55,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000002",
            "Bruttoleistung": 50,
            "Inbetriebnahmedatum": "2015-05-05",
            "Energietraeger": "2495",
        },
    ]

    (input_dir / "valid.json").write_text(json.dumps(valid_entries), encoding="utf-8")
    (input_dir / "not_list.json").write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    (input_dir / "invalid.json").write_text("{invalid json", encoding="utf-8")

    monkeypatch.setattr(analyze_mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(analyze_mod, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(analyze_mod, "POLYGON_STATES_PATH", str(sample_state_geojson))
    monkeypatch.setattr(analyze_mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))
    monkeypatch.setattr(
        analyze_mod,
        "USER_LIMITS",
        {
            "power_kw_min": None,
            "power_kw_max": None,
            "commissioning_date_min": None,
            "commissioning_date_max": None,
        },
    )

    analyze_mod.analyze()

    out = capsys.readouterr().out
    assert "STEP 7 - 4CHECK GATED ENERGY MIN/MAX" in out
    assert "DONE - Outputs written" in out

    run_dirs = list(Path(output_dir).glob("run_*"))
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    report_md = run_dir / "report.md"
    summary_json = run_dir / "summary.json"
    per_file_csv = run_dir / "per_file.csv"
    energy_csv = run_dir / "energy_type_minmax.csv"
    energy_json = run_dir / "energy_type_minmax.json"

    assert report_md.exists()
    assert summary_json.exists()
    assert per_file_csv.exists()
    assert energy_csv.exists()
    assert energy_json.exists()

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["files_seen"] == 3
    assert summary["entries_seen_total"] == 3
    assert summary["entries_kept_total"] == 3
    assert summary["dropped_totals"]["not_list_json"] == 1
    assert summary["energy_types_count"] == 2

    per_file_rows = list(csv.DictReader(per_file_csv.open("r", encoding="utf-8", newline="")))
    assert len(per_file_rows) == 1
    assert per_file_rows[0]["file_name"] == "valid.json"
    assert per_file_rows[0]["entries_total"] == "3"
    assert per_file_rows[0]["entries_kept_after_4checks_and_limits"] == "3"

    energy_rows = list(csv.DictReader(energy_csv.open("r", encoding="utf-8", newline="")))
    assert len(energy_rows) == 2

    wind_row = next(row for row in energy_rows if row["energy_code"] == "2497")
    assert float(wind_row["min_power_kw"]) == pytest.approx(100.0)
    assert float(wind_row["max_power_kw"]) == pytest.approx(500.0)
    assert wind_row["min_year"] == "2010"
    assert wind_row["max_year"] == "2020"

    energy_payload = json.loads(energy_json.read_text(encoding="utf-8"))
    wind_payload = next(item for item in energy_payload if item["energy_code"] == "2497")
    assert wind_payload["min_ref"]["power_kw"] == pytest.approx(100.0)
    assert wind_payload["max_ref"]["power_kw"] == pytest.approx(500.0)
    assert len(wind_payload["max_top5_refs"]) == 2

    report_text = report_md.read_text(encoding="utf-8")
    assert "# Step 7 - 4check gated energy min/max report" in report_text
    assert "Windenergie Onshore - Onshore Wind Energy (2497)" in report_text


def test_analyze_tracks_drop_reasons(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entries = [
        "not a dict",
        {
            "Laengengrad": "",
            "Breitengrad": "",
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 20.0,
            "Breitengrad": 60.0,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "9999",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "1415",
            "Gemeindeschluessel": "",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "1403",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 10.05,
            "Breitengrad": 50.05,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
        },
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
        },
        {
            "Laengengrad": 10.5,
            "Breitengrad": 50.5,
            "Bundesland": "1415",
            "Gemeindeschluessel": "16000000",
            "Bruttoleistung": 100,
            "Inbetriebnahmedatum": "1980-01-01",
        },
    ]

    (input_dir / "drops.json").write_text(json.dumps(entries), encoding="utf-8")

    monkeypatch.setattr(analyze_mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(analyze_mod, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(analyze_mod, "POLYGON_STATES_PATH", str(sample_state_geojson))
    monkeypatch.setattr(analyze_mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))
    monkeypatch.setattr(
        analyze_mod,
        "USER_LIMITS",
        {
            "power_kw_min": None,
            "power_kw_max": None,
            "commissioning_date_min": "2000-01-01",
            "commissioning_date_max": None,
        },
    )

    analyze_mod.analyze()

    run_dir = next(Path(output_dir).glob("run_*"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    per_file_rows = list(csv.DictReader((run_dir / "per_file.csv").open("r", encoding="utf-8", newline="")))
    row = per_file_rows[0]

    assert summary["entries_seen_total"] == 9
    assert summary["entries_kept_total"] == 0

    assert summary["dropped_totals"]["invalid_entry"] == 1
    assert summary["dropped_totals"]["no_point"] == 1
    assert summary["dropped_totals"]["no_state_polygon"] == 1
    assert summary["dropped_totals"]["missing_bundesland"] == 1
    assert summary["dropped_totals"]["missing_gemeindeschluessel"] == 1
    assert summary["dropped_totals"]["triple_mismatch"] == 1
    assert summary["dropped_totals"]["no_landkreis_match"] == 1
    assert summary["dropped_totals"]["missing_power"] == 1
    assert summary["dropped_totals"]["user_limits"] == 1

    assert row["dropped_invalid_entry"] == "1"
    assert row["dropped_no_point"] == "1"
    assert row["dropped_no_state_polygon"] == "1"
    assert row["dropped_missing_bundesland"] == "1"
    assert row["dropped_missing_gemeindeschluessel"] == "1"
    assert row["dropped_triple_mismatch"] == "1"
    assert row["dropped_no_landkreis_match"] == "1"
    assert row["dropped_missing_power"] == "1"
    assert row["dropped_limits"] == "1"


def test_analyze_raises_when_state_polygons_missing(monkeypatch, temp_workspace, sample_gadm_l2_geojson):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    (input_dir / "valid.json").write_text("[]", encoding="utf-8")

    empty_states = temp_workspace["data_dir"] / "empty_states.json"
    empty_states.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

    monkeypatch.setattr(analyze_mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(analyze_mod, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(analyze_mod, "POLYGON_STATES_PATH", str(empty_states))
    monkeypatch.setattr(analyze_mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))

    with pytest.raises(RuntimeError, match="No state polygons loaded"):
        analyze_mod.analyze()


def test_analyze_raises_when_landkreis_polygons_missing(monkeypatch, temp_workspace, sample_state_geojson):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    (input_dir / "valid.json").write_text("[]", encoding="utf-8")

    empty_gadm = temp_workspace["gadm_dir"] / "empty_gadm.json"
    empty_gadm.write_text(json.dumps({"type": "FeatureCollection", "features": []}), encoding="utf-8")

    monkeypatch.setattr(analyze_mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(analyze_mod, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(analyze_mod, "POLYGON_STATES_PATH", str(sample_state_geojson))
    monkeypatch.setattr(analyze_mod, "GADM_L2_PATH", str(empty_gadm))

    with pytest.raises(RuntimeError, match="No Landkreis polygons loaded"):
        analyze_mod.analyze()


def test_analyze_returns_early_when_no_json_files(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    monkeypatch.setattr(analyze_mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(analyze_mod, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(analyze_mod, "POLYGON_STATES_PATH", str(sample_state_geojson))
    monkeypatch.setattr(analyze_mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))

    analyze_mod.analyze()

    out = capsys.readouterr().out
    assert "No JSON files found in" in out

    run_dirs = list(Path(output_dir).glob("run_*"))
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    assert run_dir.exists()
    assert run_dir.is_dir()

    # Since there were no JSON files, no report outputs should be written
    assert not (run_dir / "report.md").exists()
    assert not (run_dir / "summary.json").exists()
    assert not (run_dir / "per_file.csv").exists()
    assert not (run_dir / "energy_type_minmax.csv").exists()
    assert not (run_dir / "energy_type_minmax.json").exists()