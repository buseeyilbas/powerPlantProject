"""
Unit tests for step19_filter_json_by_landkreis.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step19_filter_json_by_landkreis as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    gadm_dir = tmp_path / "gadm"

    input_dir.mkdir()
    output_dir.mkdir()
    gadm_dir.mkdir()

    return {
        "root": tmp_path,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "gadm_dir": gadm_dir,
    }


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
        ("Landkreis A", "landkreis a"),
        ("Landkreis/B", "landkreis_b"),
        ("A\\B", "a_b"),
        ("  Mixed__Name  ", "mixed_name"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_safe_filename(value, expected):
    assert mod.safe_filename(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Bayern", "bayern"),
        ("Thüringen", "thueringen"),
        ("Baden-Württemberg", "badenwuerttemberg"),
        ("Nordrhein-Westfalen", "nordrheinwestfalen"),
        ("Rheinland_Pfalz", "rheinlandpfalz"),
        (None, ""),
        (123, ""),
    ],
)
def test_normalize_state_name_token(value, expected):
    assert mod.normalize_state_name_token(value) == expected


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


def test_load_gadm_l2_returns_expected_structures(sample_gadm_l2_geojson):
    result = mod.load_gadm_l2(str(sample_gadm_l2_geojson))

    assert len(result) == 2

    name_1, name_2, geom = result[0]
    assert name_1 == "Bayern"
    assert name_2 == "Landkreis A"
    assert isinstance(geom, MultiPolygon)


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


def test_filter_json_by_landkreis_end_to_end(temp_workspace, sample_gadm_l2_geojson, capsys):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    valid_a = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }

    valid_b = {
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

    write_json(
        input_dir / "file1.json",
        [
            valid_a,
            valid_b,
            invalid_point,
            outside,
        ],
    )

    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    mod.filter_json_by_landkreis(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    a_file = output_dir / "landkreis a_bayern" / "file1.json"
    b_file = output_dir / "landkreis b_thüringen" / "file1.json"
    summary_file = output_dir / "_summary.json"

    assert a_file.exists()
    assert b_file.exists()
    assert summary_file.exists()

    assert read_json(a_file) == [valid_a]
    assert read_json(b_file) == [valid_b]

    summary = read_json(summary_file)

    assert summary["files_processed"] == 2
    assert summary["entries_seen"] == 4
    assert summary["kept_entries"] == 2
    assert summary["dropped_no_polygon_match"] == 1
    assert summary["dropped_missing_bundesland"] == 0
    assert summary["dropped_missing_gemeindeschluessel"] == 0
    assert summary["dropped_state_triple_mismatch"] == 0
    assert summary["output_base"] == str(output_dir)

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "Saved" in out
    assert "landkreis a_bayern/file1.json" in out
    assert "landkreis b_thüringen/file1.json" in out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_landkreis_multiple_entries_same_bucket(temp_workspace, sample_gadm_l2_geojson):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry1 = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
    }
    entry2 = {
        "id": 2,
        "Laengengrad": "10.6",
        "Breitengrad": "50.1",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670001",
    }

    write_json(input_dir / "file1.json", [entry1, entry2])

    mod.filter_json_by_landkreis(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    out_file = output_dir / "landkreis a_bayern" / "file1.json"
    assert out_file.exists()
    assert read_json(out_file) == [entry1, entry2]


def test_filter_json_by_landkreis_counts_missing_bundesland_and_gs(temp_workspace, sample_gadm_l2_geojson):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    missing_bundesland = {
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

    write_json(input_dir / "file1.json", [missing_bundesland, missing_gs])

    mod.filter_json_by_landkreis(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 2
    assert summary["kept_entries"] == 0
    assert summary["dropped_no_polygon_match"] == 0
    assert summary["dropped_missing_bundesland"] == 1
    assert summary["dropped_missing_gemeindeschluessel"] == 1
    assert summary["dropped_state_triple_mismatch"] == 0


def test_filter_json_by_landkreis_counts_state_triple_mismatch(temp_workspace, sample_gadm_l2_geojson):
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

    mod.filter_json_by_landkreis(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 1
    assert summary["kept_entries"] == 0
    assert summary["dropped_no_polygon_match"] == 0
    assert summary["dropped_missing_bundesland"] == 0
    assert summary["dropped_missing_gemeindeschluessel"] == 0
    assert summary["dropped_state_triple_mismatch"] == 1


def test_filter_json_by_landkreis_empty_input_writes_empty_summary(
    temp_workspace,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mod.filter_json_by_landkreis(
        input_folder=str(input_dir),
        output_base=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_summary.json")

    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["kept_entries"] == 0
    assert summary["dropped_no_polygon_match"] == 0
    assert summary["dropped_missing_bundesland"] == 0
    assert summary["dropped_missing_gemeindeschluessel"] == 0
    assert summary["dropped_state_triple_mismatch"] == 0

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_landkreis_raises_when_l2_missing(temp_workspace):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_gadm = temp_workspace["gadm_dir"] / "empty_gadm.json"
    write_json(empty_gadm, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No L2 polygons loaded"):
        mod.filter_json_by_landkreis(
            input_folder=str(input_dir),
            output_base=str(output_dir),
            gadm_l2_path=str(empty_gadm),
        )