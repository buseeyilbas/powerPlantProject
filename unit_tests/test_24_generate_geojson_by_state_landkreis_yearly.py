"""
Unit tests for step24_generate_geojson_by_state_landkreis_yearly.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step24_generate_geojson_by_state_landkreis_yearly as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    gadm_dir = tmp_path / "gadm"
    poly_dir = tmp_path / "poly"

    input_dir.mkdir()
    output_dir.mkdir()
    gadm_dir.mkdir()
    poly_dir.mkdir()

    return {
        "root": tmp_path,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "gadm_dir": gadm_dir,
        "poly_dir": poly_dir,
    }


@pytest.fixture
def sample_state_geojson(temp_workspace):
    path = temp_workspace["poly_dir"] / "polygon_states.json"

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
    ("entry", "expected"),
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.0"}, (10.5, 50.0)),
        ({"Laengengrad": "10,5", "Breitengrad": "50,0"}, (10.5, 50.0)),
        ({"Laengengrad": "181", "Breitengrad": "50"}, None),
        ({"Laengengrad": "10", "Breitengrad": "91"}, None),
        ({}, None),
    ],
)
def test_parse_point(entry, expected):
    p = mod.parse_point(entry)

    if expected is None:
        assert p is None
    else:
        lon, lat = expected
        assert p.x == pytest.approx(lon)
        assert p.y == pytest.approx(lat)


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"Inbetriebnahmedatum": "2020-05-01"}, "2020"),
        ({"Inbetriebnahmedatum": "1999"}, "1999"),
        ({"Inbetriebnahmedatum": "abcd"}, "unknown"),
        ({"Inbetriebnahmedatum": ""}, "unknown"),
        ({}, "unknown"),
    ],
)
def test_extract_year(entry, expected):
    assert mod.extract_year(entry) == expected


def test_load_state_polygons(sample_state_geojson):
    polygons, pretty = mod.load_state_polygons(str(sample_state_geojson))

    assert "bayern" in polygons
    assert "thueringen" in polygons
    assert pretty["bayern"] == "Bayern"
    assert pretty["thueringen"] == "Thüringen"
    assert isinstance(polygons["bayern"], MultiPolygon)
    assert isinstance(polygons["thueringen"], MultiPolygon)


def test_polygon_state_of_point(sample_state_geojson):
    polygons, _ = mod.load_state_polygons(str(sample_state_geojson))

    assert mod.polygon_state_of_point(Point(10.5, 50.0), polygons) == "bayern"
    assert mod.polygon_state_of_point(Point(11.5, 50.5), polygons) == "thueringen"
    assert mod.polygon_state_of_point(Point(20.0, 60.0), polygons) is None


def test_safe_filename():
    assert mod.safe_filename("Landkreis A") == "Landkreis A"
    assert mod.safe_filename("Landkreis/B") == "Landkreis_B"
    assert mod.safe_filename("A\\B") == "A_B"
    assert mod.safe_filename("") == "unknown"
    assert mod.safe_filename(None) == "unknown"


def test_load_gadm_l2_polygons(sample_gadm_l2_geojson):
    polygons = mod.load_gadm_l2_polygons(str(sample_gadm_l2_geojson))

    assert len(polygons) == 2
    assert polygons[0][0] == "Bayern"
    assert polygons[0][1] == "Landkreis A"
    assert polygons[0][2] is not None


def test_to_feature():
    entry = {
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "id": 1,
        "name": "plant",
    }

    point = mod.parse_point(entry)
    feature = mod.to_feature(entry, point)

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [pytest.approx(10.5), pytest.approx(50.0)]
    assert feature["properties"]["id"] == 1
    assert "Laengengrad" not in feature["properties"]
    assert "Breitengrad" not in feature["properties"]


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


def test_convert_state_landkreis_yearly_end_to_end(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    monkeypatch,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry_a_2020 = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-05-01",
    }

    entry_a_2021 = {
        "id": 2,
        "Laengengrad": "10.6",
        "Breitengrad": "50.1",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670001",
        "Inbetriebnahmedatum": "2021-01-01",
    }

    entry_b_unknown = {
        "id": 3,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
        "Inbetriebnahmedatum": "abcd",
    }

    invalid = {
        "id": 4,
        "Laengengrad": "181",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    outside = {
        "id": 5,
        "Laengengrad": "20",
        "Breitengrad": "60",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    write_json(
        input_dir / "file1.json",
        [entry_a_2020, entry_a_2021, entry_b_unknown, invalid, outside],
    )

    monkeypatch.setattr(mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_ROOT", str(output_dir))
    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))
    monkeypatch.setattr(mod, "POLYGON_STATES_PATH", str(sample_state_geojson))

    mod.convert_state_landkreis_yearly()

    a_2020 = output_dir / "Bayern" / "Landkreis A" / "2020.geojson"
    a_2021 = output_dir / "Bayern" / "Landkreis A" / "2021.geojson"
    b_unknown = output_dir / "Thüringen" / "Landkreis B" / "unknown.geojson"
    summary_file = output_dir / "_state_landkreis_yearly_summary.json"

    assert a_2020.exists()
    assert a_2021.exists()
    assert b_unknown.exists()
    assert summary_file.exists()

    assert len(read_json(a_2020)["features"]) == 1
    assert len(read_json(a_2021)["features"]) == 1
    assert len(read_json(b_unknown)["features"]) == 1

    summary = read_json(summary_file)
    assert summary["entries_seen"] == 5
    assert summary["passed_3check"] == 3
    assert summary["matched_entries"] == 3
    assert summary["skipped_inconsistent"] == 1

    out = capsys.readouterr().out
    assert "DONE:" in out


def test_convert_state_landkreis_yearly_empty_input(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
    monkeypatch,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    monkeypatch.setattr(mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_ROOT", str(output_dir))
    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))
    monkeypatch.setattr(mod, "POLYGON_STATES_PATH", str(sample_state_geojson))

    mod.convert_state_landkreis_yearly()

    summary = read_json(output_dir / "_state_landkreis_yearly_summary.json")
    assert summary["entries_seen"] == 0
    assert summary["passed_3check"] == 0
    assert summary["matched_entries"] == 0
    assert summary["skipped_inconsistent"] == 0


def test_convert_state_landkreis_yearly_raises_when_state_polygons_missing(
    temp_workspace,
    sample_gadm_l2_geojson,
    monkeypatch,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_states = temp_workspace["root"] / "empty_states.json"
    write_json(empty_states, {"type": "FeatureCollection", "features": []})

    monkeypatch.setattr(mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_ROOT", str(output_dir))
    monkeypatch.setattr(mod, "GADM_L2_PATH", str(sample_gadm_l2_geojson))
    monkeypatch.setattr(mod, "POLYGON_STATES_PATH", str(empty_states))

    with pytest.raises(RuntimeError):
        if not mod.load_state_polygons(str(empty_states))[0]:
            raise RuntimeError("No state polygons loaded")


def test_convert_state_landkreis_yearly_with_empty_l2_produces_zero_matches(
    temp_workspace,
    sample_state_geojson,
    monkeypatch,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty = temp_workspace["root"] / "empty_l2.json"
    write_json(empty, {"type": "FeatureCollection", "features": []})

    monkeypatch.setattr(mod, "INPUT_FOLDER", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_ROOT", str(output_dir))
    monkeypatch.setattr(mod, "GADM_L2_PATH", str(empty))
    monkeypatch.setattr(mod, "POLYGON_STATES_PATH", str(sample_state_geojson))

    mod.convert_state_landkreis_yearly()

    summary = read_json(output_dir / "_state_landkreis_yearly_summary.json")
    assert summary["entries_seen"] == 0
    assert summary["matched_entries"] == 0