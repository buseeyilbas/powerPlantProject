# test18_generate_geojson_by_state_landkreis_yearly.py
"""
Unit and integration tests for step18_generate_geojson_by_state_landkreis_yearly.py

Covers:
- extract_year: parses ISO, short-year, and invalid dates
- safe_filename: removes unsafe characters and whitespace
- parse_point: handles both '.' and ',' decimals, rejects invalid coords
- to_feature: builds valid GeoJSON structure
- Integration test for convert_state_landkreis_yearly:
  - Reads mock JSON data
  - Groups by year and Landkreis
  - Filters out invalid coordinates
  - Writes yearly GeoJSON FeatureCollections
  - Prints progress logs
"""

import json
from pathlib import Path
from shapely.geometry import Point
import pytest

import step18_generate_geojson_by_state_landkreis_yearly as mod


# ---------- helpers ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: extract_year ----------
@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"Inbetriebnahmedatum": "2020-03-01"}, "2020"),
        ({"Inbetriebnahmedatum": "2018"}, "2018"),
        ({"Inbetriebnahmedatum": "abc"}, "unknown"),
        ({"Inbetriebnahmedatum": ""}, "unknown"),
        ({}, "unknown"),
    ],
)
def test_extract_year_various(entry, expected):
    assert mod.extract_year(entry) == expected


# ---------- unit tests: safe_filename ----------
@pytest.mark.parametrize(
    "inp,expected_sub",
    [
        ("München/Stadt", "münchen_stadt"),
        ("Region-Name (2024)", "region-name_2024"),
        ("  Thüringen!", "thueringen"),
        ("A@B#C", "abc"),
    ],
)
def test_safe_filename_removes_specials(inp, expected_sub):
    result = mod.safe_filename(inp)
    assert expected_sub in result
    assert all(c not in result for c in ["@", "#", "/", "(", ")"])
    assert result == result.strip()


# ---------- unit tests: parse_point ----------
def test_parse_point_accepts_dots_and_commas():
    entry1 = {"Laengengrad": "10.2", "Breitengrad": "50.5"}
    entry2 = {"Laengengrad": "10,2", "Breitengrad": "50,5"}
    p1, p2 = mod.parse_point(entry1), mod.parse_point(entry2)
    assert isinstance(p1, Point)
    assert isinstance(p2, Point)
    assert round(p2.x, 1) == 10.2 and round(p2.y, 1) == 50.5


@pytest.mark.parametrize(
    "entry",
    [
        {"Laengengrad": "abc", "Breitengrad": "50"},
        {"Laengengrad": "10", "Breitengrad": "95"},
        {"Laengengrad": None, "Breitengrad": "50"},
    ],
)
def test_parse_point_invalid_cases(entry):
    assert mod.parse_point(entry) is None


# ---------- unit tests: to_feature ----------
def test_to_feature_builds_valid_geojson_feature():
    entry = {
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Landkreis": "Bad Kissingen",
        "Inbetriebnahmedatum": "2020-05-06",
        "Energietraeger": "2493"
    }
    pt = Point(10.5, 50.0)
    feat = mod.to_feature(entry, pt)
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert "Landkreis" in feat["properties"]
    assert feat["properties"]["Energietraeger"] == "2493"


def test_to_feature_returns_none_for_missing_point():
    entry = {"Laengengrad": "10", "Breitengrad": "50"}
    assert mod.to_feature(entry, None) is None


# ---------- integration test: convert_state_landkreis_yearly ----------
def test_convert_state_landkreis_yearly_creates_valid_outputs(tmp_path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_root = tmp_path / "out"
    input_dir.mkdir()

    entries = [
        {
            "Laengengrad": "10.0",
            "Breitengrad": "50.0",
            "Landkreis": "Bad Kissingen",
            "Inbetriebnahmedatum": "2020-06-15",
            "Energietraeger": "2493",
            "id": 1
        },
        {
            "Laengengrad": "10.2",
            "Breitengrad": "50.1",
            "Landkreis": "Bad Kissingen",
            "Inbetriebnahmedatum": "2020-12-31",
            "Energietraeger": "2495",
            "id": 2
        },
        {
            "Laengengrad": "abc",
            "Breitengrad": "xyz",
            "Landkreis": "Bad Kissingen",
            "Inbetriebnahmedatum": "2020-01-01",
            "id": 3
        }
    ]
    wjson(input_dir / "plants.json", entries)

    # Act
    mod.convert_state_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_root),
        gadm_l2_path="dummy",
        date_field="Inbetriebnahmedatum"
    )

    # Assert
    out_files = list(output_root.glob("*.geojson"))
    assert len(out_files) >= 1

    data = rjson(out_files[0])
    assert data["type"] == "FeatureCollection"
    features = data["features"]

    # IDs 1 and 2 should remain, invalid coords (id 3) should be skipped
    ids = [f["properties"]["id"] for f in features]
    assert 1 in ids and 2 in ids and 3 not in ids

    # Check geometry validity
    for f in features:
        assert f["geometry"]["type"] == "Point"
        assert isinstance(f["geometry"]["coordinates"], list)

    out = capsys.readouterr().out
    assert "Processing" in out or "Saved" in out


def test_convert_state_landkreis_yearly_handles_invalid_json(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    mod.convert_state_landkreis_yearly(
        input_folder=str(input_dir),
        output_root=str(output_dir),
        gadm_l2_path="dummy",
        date_field="Inbetriebnahmedatum"
    )

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert not list(output_dir.glob("*.geojson"))
