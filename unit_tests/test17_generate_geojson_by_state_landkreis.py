# test17_generate_geojson_by_state_landkreis.py
"""
Unit and integration tests for step17_generate_geojson_by_state_landkreis.py

Covers:
- safe_filename: ensures filenames are OS-safe and lowercase
- parse_point: parses numeric and comma-based coordinates, ignores invalid ones
- to_feature: constructs valid GeoJSON features with geometry and properties
- Integration test for convert_by_state_landkreis:
  - Loads small JSON dataset
  - Skips invalid coordinates
  - Writes valid GeoJSON FeatureCollection
  - Prints summary of processed features
"""

import json
from pathlib import Path
from shapely.geometry import Point
import pytest

import step17_generate_geojson_by_state_landkreis as mod


# ---------- helpers ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests for safe_filename ----------
@pytest.mark.parametrize(
    "input_name,expected_contains",
    [
        ("München-Stadt", "münchen-stadt"),
        ("Baden-Württemberg/2025", "baden-württemberg_2025"),
        ("Region@Name!", "regionname"),
        (" Thüringen ", "thueringen"),
    ],
)
def test_safe_filename_removes_specials(input_name, expected_contains):
    safe = mod.safe_filename(input_name)
    assert expected_contains in safe
    assert "@" not in safe
    assert "/" not in safe
    assert "\\" not in safe


# ---------- unit tests for parse_point ----------
@pytest.mark.parametrize(
    "entry,valid",
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.0"}, True),
        ({"Laengengrad": "10,5", "Breitengrad": "50,0"}, True),
        ({"Laengengrad": "abc", "Breitengrad": "50"}, False),
        ({"Laengengrad": "10", "Breitengrad": "95"}, False),
        ({"Laengengrad": None, "Breitengrad": "50"}, False),
    ],
)
def test_parse_point_various_cases(entry, valid):
    result = mod.parse_point(entry)
    if valid:
        assert isinstance(result, Point)
        assert -180 <= result.x <= 180
    else:
        assert result is None


# ---------- unit tests for to_feature ----------
def test_to_feature_structure_and_geometry():
    entry = {"Laengengrad": "10.1", "Breitengrad": "50.5", "Bundesland": "1403", "Landkreis": "Bad Kissingen"}
    pt = Point(10.1, 50.5)
    feature = mod.to_feature(entry, pt)

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert "Bundesland" in feature["properties"]
    assert "Landkreis" in feature["properties"]


def test_to_feature_returns_none_for_invalid_point():
    entry = {"Laengengrad": "999", "Breitengrad": "50", "Bundesland": "1403"}
    assert mod.to_feature(entry, None) is None


# ---------- integration test for convert_by_state_landkreis ----------
def test_convert_by_state_landkreis_creates_geojson(tmp_path, capsys):
    # Arrange
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    entries = [
        {
            "Laengengrad": "10.0",
            "Breitengrad": "50.0",
            "Bundesland": "1403",
            "Landkreis": "Bad Kissingen",
            "id": 1
        },
        {
            "Laengengrad": "200",  # invalid coordinate
            "Breitengrad": "95",
            "Bundesland": "1403",
            "Landkreis": "Bad Kissingen",
            "id": 2
        },
        {
            "Laengengrad": "10,1",
            "Breitengrad": "50,5",
            "Bundesland": "1403",
            "Landkreis": "Rhön-Grabfeld",
            "id": 3
        }
    ]
    wjson(input_dir / "plants.json", entries)

    # Act
    mod.convert_by_state_landkreis(str(input_dir), str(output_dir), gadm_l2_path="dummy")

    # Assert
    out_files = list(output_dir.glob("*.geojson"))
    assert len(out_files) >= 1

    # Load the first output GeoJSON
    geo = rjson(out_files[0])
    assert geo["type"] == "FeatureCollection"
    feats = geo["features"]

    # Only valid coordinates should remain
    all_ids = [f["properties"]["id"] for f in feats]
    assert 2 not in all_ids
    assert all(isinstance(f["geometry"]["coordinates"], list) for f in feats)

    out = capsys.readouterr().out
    assert "Processing" in out or "Saved" in out


def test_convert_by_state_landkreis_handles_invalid_json(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    # Act
    mod.convert_by_state_landkreis(str(in_dir), str(out_dir), gadm_l2_path="dummy")

    # Assert
    out = capsys.readouterr().out
    assert "Failed to load bad.json" in out
    assert not list(out_dir.glob("*.geojson"))
