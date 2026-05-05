"""
Unit tests for step15_filter_json_by_state_4checks.py

Covers:
- helper functions and normalization utilities
- state polygon loading and lookup
- Landkreis prepared geometry loading and matching
- Bundesland and Gemeindeschluessel mapping helpers
- parse_point() valid and invalid cases
- end-to-end filtering with all 4 checks
- summary generation and bad JSON handling
- runtime errors when required polygon data is missing
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step15_filter_json_by_state_4checks as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    gadm_dir = tmp_path / "gadm"

    input_dir.mkdir()
    output_dir.mkdir()
    data_dir.mkdir()
    gadm_dir.mkdir()

    return {
        "root": tmp_path,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "data_dir": data_dir,
        "gadm_dir": gadm_dir,
    }


@pytest.fixture
def sample_state_geojson(temp_workspace):
    path = temp_workspace["data_dir"] / "polygon_states.json"

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Bayern"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.0, 49.0], [11.0, 49.0], [11.0, 51.0], [10.0, 51.0], [10.0, 49.0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"name": "Thüringen"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[11.0, 50.0], [12.0, 50.0], [12.0, 51.0], [11.0, 51.0], [11.0, 50.0]]],
                },
            },
        ],
    }

    write_json(path, payload)
    return path


@pytest.fixture
def sample_gadm_l2_geojson(temp_workspace):
    path = temp_workspace["gadm_dir"] / "gadm41_DEU_2.json"

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME_1": "Bayern", "NAME_2": "Landkreis A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.1, 49.1], [10.9, 49.1], [10.9, 50.9], [10.1, 50.9], [10.1, 49.1]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"NAME_1": "Thüringen", "NAME_2": "Landkreis B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[11.1, 50.1], [11.9, 50.1], [11.9, 50.9], [11.1, 50.9], [11.1, 50.1]]],
                },
            },
        ],
    }

    write_json(path, payload)
    return path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Baden-Württemberg", "badenwuerttemberg"),
        ("Thüringen", "thueringen"),
        ("Nordrhein-Westfalen", "nordrheinwestfalen"),
        ("Rheinland_Pfalz", "rheinlandpfalz"),
        ("Bayern (Test)", "bayerntest"),
        (None, ""),
        (123, ""),
    ],
)
def test_normalize_state_name(value, expected):
    assert mod.normalize_state_name(value) == expected


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.1"}, (10.5, 50.1)),
        ({"Laengengrad": "10,5", "Breitengrad": "50,1"}, (10.5, 50.1)),
        ({"Laengengrad": "181", "Breitengrad": "50"}, None),
        ({"Laengengrad": "10", "Breitengrad": "91"}, None),
        ({"Laengengrad": "abc", "Breitengrad": "50"}, None),
        ({}, None),
    ],
)
def test_parse_point(entry, expected):
    pt = mod.parse_point(entry)

    if expected is None:
        assert pt is None
    else:
        lon, lat = expected
        assert pt is not None
        assert pt.x == pytest.approx(lon)
        assert pt.y == pytest.approx(lat)


def test_load_state_polygons_returns_mapping(sample_state_geojson):
    polygons_by_norm, pretty_by_norm = mod.load_state_polygons(str(sample_state_geojson))

    assert "bayern" in polygons_by_norm
    assert "thueringen" in polygons_by_norm
    assert pretty_by_norm["bayern"] == "Bayern"
    assert pretty_by_norm["thueringen"] == "Thüringen"
    assert isinstance(polygons_by_norm["bayern"], MultiPolygon)


def test_polygon_state_of_point_returns_expected_state(sample_state_geojson):
    polygons_by_norm, _ = mod.load_state_polygons(str(sample_state_geojson))

    assert mod.polygon_state_of_point(Point(10.5, 50.0), polygons_by_norm) == "bayern"
    assert mod.polygon_state_of_point(Point(11.5, 50.5), polygons_by_norm) == "thueringen"
    assert mod.polygon_state_of_point(Point(20.0, 60.0), polygons_by_norm) is None


def test_bl_code_to_norm_name():
    assert mod.bl_code_to_norm_name("1403") == "bayern"
    assert mod.bl_code_to_norm_name("1415") == "thueringen"
    assert mod.bl_code_to_norm_name(1403) == "bayern"
    assert mod.bl_code_to_norm_name("9999") is None
    assert mod.bl_code_to_norm_name(None) is None


def test_gs_prefix_to_norm_name():
    assert mod.gs_prefix_to_norm_name("09670000") == "bayern"
    assert mod.gs_prefix_to_norm_name("16000000") == "thueringen"
    assert mod.gs_prefix_to_norm_name("9") is None
    assert mod.gs_prefix_to_norm_name(None) is None


def test_load_gadm_l2_prepared_returns_prepared_geometries(sample_gadm_l2_geojson):
    prepared_l2 = mod.load_gadm_l2_prepared(str(sample_gadm_l2_geojson))

    assert len(prepared_l2) == 2
    assert prepared_l2[0][0] == "Bayern"
    assert prepared_l2[0][1] == "Landkreis A"
    assert prepared_l2[0][2] is not None


def test_has_any_landkreis_match(sample_gadm_l2_geojson):
    prepared_l2 = mod.load_gadm_l2_prepared(str(sample_gadm_l2_geojson))

    assert mod.has_any_landkreis_match(Point(10.5, 50.0), prepared_l2) is True
    assert mod.has_any_landkreis_match(Point(11.5, 50.5), prepared_l2) is True
    assert mod.has_any_landkreis_match(Point(20.0, 60.0), prepared_l2) is False


def test_filter_json_by_state_three_checks_end_to_end(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    valid_bayern = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }
    invalid_point = {
        "id": 2,
        "Laengengrad": "181",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }
    no_polygon = {
        "id": 3,
        "Laengengrad": "20.0",
        "Breitengrad": "60.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }
    missing_bundesland = {
        "id": 4,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Gemeindeschluessel": "09670000",
    }
    missing_gs = {
        "id": 5,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
    }
    triple_mismatch = {
        "id": 6,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
    }
    no_landkreis = {
        "id": 7,
        "Laengengrad": "10.05",
        "Breitengrad": "49.05",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }
    valid_thueringen = {
        "id": 8,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
    }

    write_json(
        input_dir / "file1.json",
        [
            valid_bayern,
            invalid_point,
            no_polygon,
            missing_bundesland,
            missing_gs,
            triple_mismatch,
            no_landkreis,
            valid_thueringen,
        ],
    )
    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")
    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))

    mod.filter_json_by_state_three_checks(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
    )

    bayern_file = output_dir / "Bayern" / "file1.json"
    thueringen_file = output_dir / "Thüringen" / "file1.json"
    summary_file = output_dir / "_summary.json"

    assert bayern_file.exists()
    assert thueringen_file.exists()
    assert summary_file.exists()

    assert read_json(bayern_file) == [valid_bayern]
    assert read_json(thueringen_file) == [valid_thueringen]

    summary = read_json(summary_file)
    assert summary["files_processed"] == 2
    assert summary["entries_seen"] == 8
    assert summary["kept_entries"] == 2
    assert summary["dropped_no_polygon_match"] == 1
    assert summary["dropped_missing_bundesland"] == 1
    assert summary["dropped_missing_gemeindeschluessel"] == 1
    assert summary["dropped_triple_mismatch"] == 1
    assert summary["dropped_no_landkreis_match"] == 1
    assert summary["output_base"] == str(output_dir)
    assert summary["gadm_l2_path"] == str(sample_gadm_l2_geojson)

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "Saved" in out
    assert "Bayern/file1.json" in out
    assert "Thüringen/file1.json" in out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_state_three_checks_empty_input_writes_empty_summary(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))

    mod.filter_json_by_state_three_checks(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
    )

    summary = read_json(output_dir / "_summary.json")
    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["kept_entries"] == 0
    assert summary["dropped_no_polygon_match"] == 0
    assert summary["dropped_missing_bundesland"] == 0
    assert summary["dropped_missing_gemeindeschluessel"] == 0
    assert summary["dropped_triple_mismatch"] == 0
    assert summary["dropped_no_landkreis_match"] == 0

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_state_three_checks_raises_when_state_polygons_missing(
    monkeypatch,
    temp_workspace,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_states = temp_workspace["data_dir"] / "empty_states.json"
    write_json(empty_states, {"type": "FeatureCollection", "features": []})

    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))

    with pytest.raises(RuntimeError, match="No state polygons loaded"):
        mod.filter_json_by_state_three_checks(
            input_folder=str(input_dir),
            output_base=str(output_dir),
            polygon_states_path=str(empty_states),
        )


def test_filter_json_by_state_three_checks_raises_when_landkreis_missing(
    monkeypatch,
    temp_workspace,
    sample_state_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_gadm = temp_workspace["gadm_dir"] / "empty_gadm.json"
    write_json(empty_gadm, {"type": "FeatureCollection", "features": []})

    monkeypatch.setattr(mod, "GADM_L2_PATH", str(empty_gadm))

    with pytest.raises(RuntimeError, match="No Landkreis"):
        mod.filter_json_by_state_three_checks(
            input_folder=str(input_dir),
            output_base=str(output_dir),
            polygon_states_path=str(sample_state_geojson),
        )