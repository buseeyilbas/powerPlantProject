# test15_generate_geojson_by_state_3checks.py
"""
Unit tests for step15_generate_geojson_by_state_3checks.py

Covers:
- normalize_state_name: umlauts, punctuation, spacing, parentheses
- bl_code_to_norm_name: known mappings and unknown fallback
- polygon_state_of_point: detects correct state or None
- to_feature: handles valid and invalid coordinate entries
- Integration of convert_with_three_checks:
  - Reads JSON files, builds filtered FeatureCollections
  - Writes GeoJSON output with expected structure
  - Skips invalid/missing coordinate or state entries
  - Reports console progress for processed files
"""

import json
from pathlib import Path
import pytest
from shapely.geometry import Point, Polygon, MultiPolygon

import step15_generate_geojson_by_state_3checks as mod


# ---------- helpers ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests for normalize_state_name ----------
@pytest.mark.parametrize(
    "inp,expected_substrings",
    [
        ("Bayern", ["bayern"]),
        ("Baden-Württemberg", ["baden", "wuerttemberg"]),
        ("Hessen (Nord)", ["hessen", "nord"]),
        ("Sachsen!", ["sachsen"]),
        ("  Thüringen ", ["thueringen"]),
        ("", [""]),
        (None, [""]),
    ],
)
def test_normalize_state_name_various(inp, expected_substrings):
    result = mod.normalize_state_name(inp)
    for sub in expected_substrings:
        assert sub in result


# ---------- unit tests for bl_code_to_norm_name ----------
@pytest.mark.parametrize(
    "bl,expected",
    [
        ("1403", "bayern"),
        ("08", "baden-wuerttemberg"),
        ("1600", "thueringen"),
        ("9999", None),
        (None, None),
    ],
)
def test_bl_code_to_norm_name_cases(bl, expected):
    assert mod.bl_code_to_norm_name(bl) == expected


# ---------- unit tests for polygon_state_of_point ----------
def test_polygon_state_of_point_detects_inside_and_outside():
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mapping = {"bayern": MultiPolygon([polygon])}
    inside = Point(0.5, 0.5)
    outside = Point(2, 2)
    assert mod.polygon_state_of_point(inside, mapping) == "bayern"
    assert mod.polygon_state_of_point(outside, mapping) is None


# ---------- unit tests for to_feature ----------
def test_to_feature_valid_and_invalid_points():
    entry_valid = {"Laengengrad": "10.0", "Breitengrad": "50.0", "Bundesland": "1403"}
    feat = mod.to_feature(entry_valid)
    assert feat["geometry"]["type"] == "Point"
    assert feat["properties"]["Bundesland"] == "1403"

    entry_comma = {"Laengengrad": "10,5", "Breitengrad": "50,5", "Bundesland": "1403"}
    feat2 = mod.to_feature(entry_comma)
    assert feat2["geometry"]["coordinates"] == [10.5, 50.5]

    entry_bad_lat = {"Laengengrad": "10", "Breitengrad": "95"}
    assert mod.to_feature(entry_bad_lat) is None
    entry_bad_lon = {"Laengengrad": "200", "Breitengrad": "50"}
    assert mod.to_feature(entry_bad_lon) is None
    entry_non_numeric = {"Laengengrad": "abc", "Breitengrad": "50"}
    assert mod.to_feature(entry_non_numeric) is None


# ---------- integration test for convert_with_three_checks ----------
def test_convert_with_three_checks_creates_valid_geojson(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    in_dir.mkdir()

    # Create a mock polygon mapping (1 state)
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mod.STATE_POLYGONS = {"bayern": MultiPolygon([poly])}

    # Valid entries: one inside polygon, one outside
    data_valid = [
        {"Laengengrad": "0.5", "Breitengrad": "0.5", "Bundesland": "1403", "id": 1},  # inside
        {"Laengengrad": "5", "Breitengrad": "5", "Bundesland": "1403", "id": 2},    # outside
        {"Laengengrad": "abc", "Breitengrad": "50", "Bundesland": "1403", "id": 3},  # invalid
    ]
    wjson(in_dir / "plants.json", data_valid)

    # Act
    mod.convert_with_three_checks(str(in_dir), str(out_dir), polygon_states_path="dummy")

    # Assert
    out_files = list(out_dir.glob("*.geojson"))
    assert len(out_files) == 1
    out_data = rjson(out_files[0])
    assert out_data["type"] == "FeatureCollection"
    features = out_data["features"]

    # Only the point inside polygon should be included
    ids = [f["properties"]["id"] for f in features]
    assert ids == [1]
    coords = features[0]["geometry"]["coordinates"]
    assert 0 <= coords[0] <= 1 and 0 <= coords[1] <= 1

    out = capsys.readouterr().out
    assert "Processing" in out and "✔ Saved" in out


def test_convert_with_three_checks_handles_invalid_json(tmp_path, capsys):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    mod.convert_with_three_checks(str(in_dir), str(out_dir), polygon_states_path="dummy")

    out = capsys.readouterr().out
    assert "Failed to load bad.json" in out
    assert not list(out_dir.glob("*.geojson"))
