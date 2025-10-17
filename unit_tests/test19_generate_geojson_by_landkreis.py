# test19_generate_geojson_by_landkreis.py
"""
Unit and integration tests for step19_generate_geojson_by_landkreis.py

Covers:
- safe_filename: cleans and normalizes filenames
- parse_point: parses both '.' and ',' decimals, rejects invalid coordinates
- to_feature: creates valid GeoJSON structure and properties
- Integration test for convert_by_landkreis:
  - Reads a small test dataset
  - Filters invalid coordinate entries
  - Generates valid GeoJSON FeatureCollection
  - Reports progress in console
"""

import json
from pathlib import Path
from shapely.geometry import Point
import pytest

import step19_generate_geojson_by_landkreis as mod


# ---------- helpers ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: safe_filename ----------
@pytest.mark.parametrize(
    "input_name,expected_part",
    [
        ("München-Stadt", "münchen-stadt"),
        ("Baden-Württemberg/2025", "baden-württemberg_2025"),
        ("Landkreis@Name!", "landkreisname"),
        (" Region ", "region"),
    ],
)
def test_safe_filename_removes_special_characters(input_name, expected_part):
    result = mod.safe_filename(input_name)
    assert expected_part in result
    assert "@" not in result
    assert "/" not in result
    assert result.strip() == result


# ---------- unit tests: parse_point ----------
def test_parse_point_valid_and_comma_decimal():
    entry_dot = {"Laengengrad": "10.5", "Breitengrad": "50.1"}
    entry_comma = {"Laengengrad": "10,5", "Breitengrad": "50,1"}

    pt1, pt2 = mod.parse_point(entry_dot), mod.parse_point(entry_comma)
    assert isinstance(pt1, Point)
    assert isinstance(pt2, Point)
    assert round(pt2.x, 1) == 10.5
    assert round(pt2.y, 1) == 50.1


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
def test_to_feature_builds_valid_geojson():
    entry = {
        "Laengengrad": "10.2",
        "Breitengrad": "50.3",
        "Bundesland": "1403",
        "Landkreis": "Bad Kissingen",
        "Energietraeger": "2493",
        "id": "X1"
    }
    pt = Point(10.2, 50.3)
    f = mod.to_feature(entry, pt)

    assert f["type"] == "Feature"
    assert f["geometry"]["type"] == "Point"
    assert "Bundesland" in f["properties"]
    assert f["properties"]["id"] == "X1"


def test_to_feature_returns_none_for_invalid_point():
    entry = {"Laengengrad": "10.2", "Breitengrad": "50.3", "Landkreis": "Test"}
    assert mod.to_feature(entry, None) is None


# ---------- integration test: convert_by_landkreis ----------
def test_convert_by_landkreis_creates_valid_geojson(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    in_dir.mkdir()

    entries = [
        {
            "Laengengrad": "10.0",
            "Breitengrad": "50.0",
            "Bundesland": "1403",
            "Landkreis": "Bad Kissingen",
            "Energietraeger": "2493",
            "id": 1
        },
        {
            "Laengengrad": "10,5",
            "Breitengrad": "50,5",
            "Bundesland": "1403",
            "Landkreis": "Bad Kissingen",
            "Energietraeger": "2493",
            "id": 2
        },
        {
            "Laengengrad": "200",  # invalid coordinate
            "Breitengrad": "95",
            "Bundesland": "1403",
            "Landkreis": "Bad Kissingen",
            "id": 3
        }
    ]
    wjson(in_dir / "plants.json", entries)

    # Act
    mod.convert_by_landkreis(str(in_dir), str(out_dir), gadm_l2_path="dummy")

    # Assert
    out_files = list(out_dir.glob("*.geojson"))
    assert len(out_files) >= 1

    data = rjson(out_files[0])
    assert data["type"] == "FeatureCollection"

    features = data["features"]
    ids = [f["properties"]["id"] for f in features]
    assert 3 not in ids  # invalid coordinate skipped
    assert 1 in ids and 2 in ids

    for f in features:
        assert "geometry" in f
        assert f["geometry"]["type"] == "Point"
        coords = f["geometry"]["coordinates"]
        assert all(isinstance(c, (int, float)) for c in coords)

    out = capsys.readouterr().out
    assert "Processing" in out or "Saved" in out


def test_convert_by_landkreis_handles_invalid_json(tmp_path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    # Act
    mod.convert_by_landkreis(str(input_dir), str(output_dir), gadm_l2_path="dummy")

    # Assert
    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert not list(output_dir.glob("*.geojson"))
