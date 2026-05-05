"""
Unit tests for step16_filter_json_by_state_4checks_yearly.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step16_filter_json_by_state_4checks_yearly as mod


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


@pytest.mark.parametrize(
    ("entry", "field", "expected"),
    [
        ({"Inbetriebnahmedatum": "2020-05-01"}, "Inbetriebnahmedatum", "2020"),
        ({"Inbetriebnahmedatum": "1999"}, "Inbetriebnahmedatum", "1999"),
        ({"Inbetriebnahmedatum": "abcd-01-01"}, "Inbetriebnahmedatum", "unknown"),
        ({"Inbetriebnahmedatum": ""}, "Inbetriebnahmedatum", "unknown"),
        ({}, "Inbetriebnahmedatum", "unknown"),
        ({"custom_date": "2015-12-31"}, "custom_date", "2015"),
    ],
)
def test_extract_year(entry, field, expected):
    assert mod.extract_year(entry, field) == expected


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


def test_filter_json_by_state_year_four_checks_end_to_end(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    valid_bayern_2020 = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-05-01",
    }
    valid_bayern_unknown = {
        "id": 2,
        "Laengengrad": "10.6",
        "Breitengrad": "50.1",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670001",
        "Inbetriebnahmedatum": "abcd",
    }
    invalid_point = {
        "id": 3,
        "Laengengrad": "181",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    no_polygon = {
        "id": 4,
        "Laengengrad": "20.0",
        "Breitengrad": "60.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    missing_bundesland = {
        "id": 5,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    missing_gs = {
        "id": 6,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    triple_mismatch = {
        "id": 7,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
        "Inbetriebnahmedatum": "2021-01-01",
    }
    no_landkreis = {
        "id": 8,
        "Laengengrad": "10.05",
        "Breitengrad": "49.05",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    valid_thueringen_2021 = {
        "id": 9,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
        "Inbetriebnahmedatum": "2021-06-06",
    }

    write_json(
        input_dir / "file1.json",
        [
            valid_bayern_2020,
            valid_bayern_unknown,
            invalid_point,
            no_polygon,
            missing_bundesland,
            missing_gs,
            triple_mismatch,
            no_landkreis,
            valid_thueringen_2021,
        ],
    )
    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")
    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    mod.filter_json_by_state_year_four_checks(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    bayern_2020 = output_dir / "Bayern" / "2020" / "file1.json"
    bayern_unknown = output_dir / "Bayern" / "unknown" / "file1.json"
    thueringen_2021 = output_dir / "Thüringen" / "2021" / "file1.json"
    summary_file = output_dir / "_summary.json"

    assert bayern_2020.exists()
    assert bayern_unknown.exists()
    assert thueringen_2021.exists()
    assert summary_file.exists()

    assert read_json(bayern_2020) == [valid_bayern_2020]
    assert read_json(bayern_unknown) == [valid_bayern_unknown]
    assert read_json(thueringen_2021) == [valid_thueringen_2021]

    summary = read_json(summary_file)
    assert summary["files_processed"] == 2
    assert summary["entries_seen"] == 9
    assert summary["kept_entries"] == 3
    assert summary["dropped_no_polygon_match"] == 1
    assert summary["dropped_no_landkreis_match"] == 1
    assert summary["dropped_missing_bundesland"] == 1
    assert summary["dropped_missing_gemeindeschluessel"] == 1
    assert summary["dropped_triple_mismatch"] == 1
    assert summary["output_root"] == str(output_dir)
    assert summary["date_field"] == mod.DATE_FIELD
    assert summary["gadm_l2_path"] == str(sample_gadm_l2_geojson)

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "Saved" in out
    assert "Bayern/2020/file1.json" in out
    assert "Bayern/unknown/file1.json" in out
    assert "Thüringen/2021/file1.json" in out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_state_year_four_checks_custom_date_field(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "custom_date": "2015-09-09",
    }

    write_json(input_dir / "file1.json", [entry])

    mod.filter_json_by_state_year_four_checks(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
        date_field="custom_date",
    )

    out_file = output_dir / "Bayern" / "2015" / "file1.json"
    summary = read_json(output_dir / "_summary.json")

    assert out_file.exists()
    assert read_json(out_file) == [entry]
    assert summary["date_field"] == "custom_date"


def test_filter_json_by_state_year_four_checks_empty_input_writes_empty_summary(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mod.filter_json_by_state_year_four_checks(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_summary.json")
    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["kept_entries"] == 0
    assert summary["dropped_no_polygon_match"] == 0
    assert summary["dropped_no_landkreis_match"] == 0
    assert summary["dropped_missing_bundesland"] == 0
    assert summary["dropped_missing_gemeindeschluessel"] == 0
    assert summary["dropped_triple_mismatch"] == 0

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_state_year_four_checks_raises_when_state_polygons_missing(
    temp_workspace,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_states = temp_workspace["data_dir"] / "empty_states.json"
    write_json(empty_states, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No state polygons loaded"):
        mod.filter_json_by_state_year_four_checks(
            input_folder=str(input_dir),
            output_root=str(output_dir),
            polygon_states_path=str(empty_states),
            gadm_l2_path=str(sample_gadm_l2_geojson),
        )


def test_filter_json_by_state_year_four_checks_raises_when_landkreis_missing(
    temp_workspace,
    sample_state_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_gadm = temp_workspace["gadm_dir"] / "empty_gadm.json"
    write_json(empty_gadm, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No Landkreis"):
        mod.filter_json_by_state_year_four_checks(
            input_folder=str(input_dir),
            output_root=str(output_dir),
            polygon_states_path=str(sample_state_geojson),
            gadm_l2_path=str(empty_gadm),
        )