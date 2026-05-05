"""
Unit tests for step20_filter_json_by_landkreis_yearly.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step20_filter_json_by_landkreis_yearly as mod


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
                "properties": {"NAME_1": "Thüringen", "NAME_2": "Landkreis B/City"},
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
        ("Landkreis B/City", "landkreis b_city"),
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


def test_load_gadm_l2_returns_expected_structures(sample_gadm_l2_geojson):
    result = mod.load_gadm_l2(str(sample_gadm_l2_geojson))

    assert len(result) == 2

    name_1, name_2, geom = result[0]
    assert name_1 == "Bayern"
    assert name_2 == "Landkreis A"
    assert isinstance(geom, MultiPolygon)

    name_1_b, name_2_b, geom_b = result[1]
    assert name_1_b == "Thüringen"
    assert name_2_b == "Landkreis B/City"
    assert isinstance(geom_b, MultiPolygon)


def test_bl_code_to_norm_name():
    assert mod.normalize_state_name_token(mod.BUNDESLAND_CODE_TO_NAME["1403"]) == "bayern"
    assert mod.normalize_state_name_token(mod.BUNDESLAND_CODE_TO_NAME["1415"]) == "thueringen"


def test_gs_prefix_to_norm_name():
    assert mod.normalize_state_name_token(mod.GS_PREFIX_TO_NAME["09"]) == "bayern"
    assert mod.normalize_state_name_token(mod.GS_PREFIX_TO_NAME["16"]) == "thueringen"


def test_filter_json_by_landkreis_yearly_end_to_end(temp_workspace, sample_gadm_l2_geojson, capsys):
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
    valid_thueringen_2021 = {
        "id": 3,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
        "Inbetriebnahmedatum": "2021-06-06",
    }
    invalid_point = {
        "id": 4,
        "Laengengrad": "181",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    no_polygon = {
        "id": 5,
        "Laengengrad": "20.0",
        "Breitengrad": "60.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    missing_bundesland = {
        "id": 6,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    missing_gs = {
        "id": 7,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    mismatch = {
        "id": 8,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1415",
        "Gemeindeschluessel": "16000000",
        "Inbetriebnahmedatum": "2021-01-01",
    }

    write_json(
        input_dir / "file1.json",
        [
            valid_bayern_2020,
            valid_bayern_unknown,
            valid_thueringen_2021,
            invalid_point,
            no_polygon,
            missing_bundesland,
            missing_gs,
            mismatch,
        ],
    )
    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")
    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")

    mod.filter_json_by_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    bayern_2020 = output_dir / "landkreis a" / "2020" / "file1.json"
    bayern_unknown = output_dir / "landkreis a" / "unknown" / "file1.json"
    thueringen_2021 = output_dir / "landkreis b_city" / "2021" / "file1.json"
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
    assert summary["entries_seen"] == 8
    assert summary["kept_entries"] == 3
    assert summary["dropped_no_polygon_match"] == 1
    assert summary["dropped_missing_bundesland"] == 1
    assert summary["dropped_missing_gemeindeschluessel"] == 1
    assert summary["dropped_state_triple_mismatch"] == 1
    assert summary["output_root"] == str(output_dir)
    assert summary["date_field"] == mod.DATE_FIELD

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "Saved" in out
    assert "landkreis a/2020/file1.json" in out
    assert "landkreis a/unknown/file1.json" in out
    assert "landkreis b_city/2021/file1.json" in out
    assert "====== SUMMARY ======" in out


def test_filter_json_by_landkreis_yearly_custom_date_field(temp_workspace, sample_gadm_l2_geojson):
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

    mod.filter_json_by_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
        date_field="custom_date",
    )

    out_file = output_dir / "landkreis a" / "2015" / "file1.json"
    summary = read_json(output_dir / "_summary.json")

    assert out_file.exists()
    assert read_json(out_file) == [entry]
    assert summary["date_field"] == "custom_date"


def test_filter_json_by_landkreis_yearly_multiple_entries_same_bucket(temp_workspace, sample_gadm_l2_geojson):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry_1 = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670000",
        "Inbetriebnahmedatum": "2020-01-01",
    }
    entry_2 = {
        "id": 2,
        "Laengengrad": "10.6",
        "Breitengrad": "50.1",
        "Bundesland": "1403",
        "Gemeindeschluessel": "09670001",
        "Inbetriebnahmedatum": "2020-12-31",
    }

    write_json(input_dir / "file1.json", [entry_1, entry_2])

    mod.filter_json_by_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    out_file = output_dir / "landkreis a" / "2020" / "file1.json"
    assert out_file.exists()
    assert read_json(out_file) == [entry_1, entry_2]


def test_filter_json_by_landkreis_yearly_empty_input_writes_empty_summary(
    temp_workspace,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mod.filter_json_by_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_dir),
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


def test_filter_json_by_landkreis_yearly_raises_when_l2_missing(temp_workspace):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty_gadm = temp_workspace["gadm_dir"] / "empty_gadm.json"
    write_json(empty_gadm, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No L2 polygons loaded"):
        mod.filter_json_by_landkreis_yearly(
            input_folder=str(input_dir),
            output_root=str(output_dir),
            gadm_l2_path=str(empty_gadm),
        )