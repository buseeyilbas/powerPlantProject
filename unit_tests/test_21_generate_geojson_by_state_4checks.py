"""
Unit tests for step21_generate_geojson_by_state_4checks.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step21_generate_geojson_by_state_4checks as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    polygon_dir = tmp_path / "polygons"
    gadm_dir = tmp_path / "gadm"

    input_dir.mkdir()
    output_dir.mkdir()
    polygon_dir.mkdir()
    gadm_dir.mkdir()

    return {
        "root": tmp_path,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "polygon_dir": polygon_dir,
        "gadm_dir": gadm_dir,
    }


@pytest.fixture
def sample_state_geojson(temp_workspace):
    path = temp_workspace["polygon_dir"] / "polygon_states.json"

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


def test_load_state_polygons(sample_state_geojson):
    polygons = mod.load_state_polygons(str(sample_state_geojson))

    assert "bayern" in polygons
    assert "thueringen" in polygons
    assert isinstance(polygons["bayern"], MultiPolygon)
    assert isinstance(polygons["thueringen"], MultiPolygon)


def test_polygon_state_of_point(sample_state_geojson):
    polygons = mod.load_state_polygons(str(sample_state_geojson))

    assert mod.polygon_state_of_point(Point(10.5, 50.0), polygons) == "bayern"
    assert mod.polygon_state_of_point(Point(11.5, 50.5), polygons) == "thueringen"
    assert mod.polygon_state_of_point(Point(20.0, 60.0), polygons) is None


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


def test_load_landkreis_polygons(sample_gadm_l2_geojson):
    result = mod.load_landkreis_polygons(str(sample_gadm_l2_geojson))

    assert len(result) == 2
    assert result[0][0] == "Bayern"
    assert result[0][1] == "Landkreis A"
    assert isinstance(result[0][2], MultiPolygon)


def test_has_any_landkreis_match(sample_gadm_l2_geojson):
    l2 = mod.load_landkreis_polygons(str(sample_gadm_l2_geojson))
    prepared_l2 = [(name_1, name_2, mod.prep(geom)) for (name_1, name_2, geom) in l2]

    assert mod.has_any_landkreis_match(Point(10.5, 50.0), prepared_l2) is True
    assert mod.has_any_landkreis_match(Point(11.5, 50.5), prepared_l2) is True
    assert mod.has_any_landkreis_match(Point(20.0, 60.0), prepared_l2) is False


def test_to_feature_excludes_coordinate_fields():
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
    assert feature["properties"]["name"] == "plant"
    assert "Laengengrad" not in feature["properties"]
    assert "Breitengrad" not in feature["properties"]


def test_convert_with_4_checks_end_to_end(
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

    valid_thueringen = {
        "id": 2,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
    }

    invalid_point = {
        "id": 3,
        "Laengengrad": "181",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    outside = {
        "id": 4,
        "Laengengrad": "20.0",
        "Breitengrad": "60.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    write_json(input_dir / "file1.json", [valid_bayern, valid_thueringen, invalid_point, outside])
    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    mod.convert_with_4_checks(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    bayern_geojson = output_dir / "bayern.geojson"
    thueringen_geojson = output_dir / "thueringen.geojson"
    summary_file = output_dir / "_consistency_summary.json"

    assert bayern_geojson.exists()
    assert thueringen_geojson.exists()
    assert summary_file.exists()

    bayern = read_json(bayern_geojson)
    thueringen = read_json(thueringen_geojson)

    assert bayern["type"] == "FeatureCollection"
    assert thueringen["type"] == "FeatureCollection"
    assert len(bayern["features"]) == 1
    assert len(thueringen["features"]) == 1
    assert bayern["features"][0]["properties"]["id"] == 1
    assert thueringen["features"][0]["properties"]["id"] == 2

    summary = read_json(summary_file)
    assert summary["files_processed"] == 2
    assert summary["entries_seen"] == 4
    assert summary["consistent"] == 2
    assert summary["no_polygon_match"] == 1
    assert summary["no_landkreis_match"] == 0
    assert summary["bundesland_missing_or_unmapped"] == 0
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 0
    assert summary["bundesland_mismatch_count"] == 0
    assert summary["gemeindeschluessel_mismatch_count"] == 0
    assert summary["polygon_states_path"] == str(sample_state_geojson)
    assert summary["gadm_l2_path"] == str(sample_gadm_l2_geojson)

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "Saved 1 consistent features" in out
    assert "====== SUMMARY ======" in out


def test_convert_with_4_checks_counts_no_landkreis_match(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry = {
        "id": 1,
        "Laengengrad": "10.05",
        "Breitengrad": "49.05",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    write_json(input_dir / "file1.json", [entry])

    mod.convert_with_4_checks(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 1
    assert summary["consistent"] == 0
    assert summary["no_polygon_match"] == 0
    assert summary["no_landkreis_match"] == 1

    assert not (output_dir / "bayern.geojson").exists()


def test_convert_with_4_checks_counts_missing_fields(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    missing_bl = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Gemeindeschluessel": "09670000",
    }
    missing_gs = {
        "id": 2,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
    }

    write_json(input_dir / "file1.json", [missing_bl, missing_gs])

    mod.convert_with_4_checks(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 2
    assert summary["consistent"] == 0
    assert summary["bundesland_missing_or_unmapped"] == 1
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 1


def test_convert_with_4_checks_counts_mismatches(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mismatch = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
    }

    write_json(input_dir / "file1.json", [mismatch])

    mod.convert_with_4_checks(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 1
    assert summary["consistent"] == 0
    assert summary["bundesland_mismatch_count"] == 1
    assert summary["gemeindeschluessel_mismatch_count"] == 1


def test_convert_with_4_checks_empty_input(
    temp_workspace,
    sample_state_geojson,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mod.convert_with_4_checks(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        polygon_states_path=str(sample_state_geojson),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["consistent"] == 0
    assert summary["no_polygon_match"] == 0
    assert summary["no_landkreis_match"] == 0


def test_convert_with_4_checks_raises_when_state_polygons_missing(
    temp_workspace,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_states = temp_workspace["polygon_dir"] / "empty.json"
    write_json(empty_states, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No state polygons loaded"):
        mod.convert_with_4_checks(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            polygon_states_path=str(empty_states),
            gadm_l2_path=str(sample_gadm_l2_geojson),
        )


def test_convert_with_4_checks_raises_when_landkreis_missing(
    temp_workspace,
    sample_state_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_gadm = temp_workspace["gadm_dir"] / "empty.json"
    write_json(empty_gadm, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No Landkreis"):
        mod.convert_with_4_checks(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            polygon_states_path=str(sample_state_geojson),
            gadm_l2_path=str(empty_gadm),
        )