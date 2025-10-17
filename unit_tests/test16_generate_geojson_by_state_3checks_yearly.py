# test16_generate_geojson_by_state_3checks_yearly.py
"""
Unit and integration tests for step16_generate_geojson_by_state_3checks_yearly.py

Covers:
- extract_year: different date formats, missing or malformed values
- parse_point: handling of comma decimals, invalid or out-of-range coordinates
- polygon_state_of_point: identifies correct state polygon or None
- Integration test for convert_by_state_year_with_three_checks:
  - Loads mock JSON files per year
  - Filters invalid coordinates or outside polygons
  - Groups entries by state and commissioning year
  - Writes GeoJSON FeatureCollections per year
"""

import json
from pathlib import Path
from shapely.geometry import Point, Polygon, MultiPolygon
import pytest

import step16_generate_geojson_by_state_3checks_yearly as mod


# ---------- helper functions ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests for extract_year ----------
@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"Inbetriebnahmedatum": "2015-01-01"}, "2015"),
        ({"Inbetriebnahmedatum": "2019"}, "2019"),
        ({"Inbetriebnahmedatum": "abc"}, "unknown"),
        ({"Inbetriebnahmedatum": ""}, "unknown"),
        ({}, "unknown"),
    ],
)
def test_extract_year_handles_formats(entry, expected):
    assert mod.extract_year(entry) == expected


# ---------- unit tests for parse_point ----------
def test_parse_point_handles_decimal_and_comma():
    e1 = {"Laengengrad": "10.123", "Breitengrad": "50.987"}
    e2 = {"Laengengrad": "10,123", "Breitengrad": "50,987"}
    p1, p2 = mod.parse_point(e1), mod.parse_point(e2)
    assert isinstance(p1, Point) and isinstance(p2, Point)
    assert round(p2.x, 3) == 10.123 and round(p2.y, 3) == 50.987


def test_parse_point_returns_none_for_invalid_coords():
    bad_entries = [
        {"Laengengrad": "9999", "Breitengrad": "50"},
        {"Laengengrad": "abc", "Breitengrad": "50"},
        {"Laengengrad": "10", "Breitengrad": "95"},
        {"Laengengrad": None, "Breitengrad": None},
    ]
    for e in bad_entries:
        assert mod.parse_point(e) is None


# ---------- unit tests for polygon_state_of_point ----------
def test_polygon_state_of_point_detects_inside_and_outside():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mp = MultiPolygon([poly])
    mapping = {"bayern": mp}
    assert mod.polygon_state_of_point(Point(0.5, 0.5), mapping) == "bayern"
    assert mod.polygon_state_of_point(Point(2, 2), mapping) is None


# ---------- integration test for convert_by_state_year_with_three_checks ----------
def test_convert_by_state_year_with_three_checks_creates_geojson(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "input"
    out_root = tmp_path / "out"
    in_dir.mkdir()

    # Mock polygon mapping (only "bayern")
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mod.STATE_POLYGONS = {"bayern": MultiPolygon([poly])}

    # Prepare test JSON: one valid (inside polygon, 2015), one invalid (out of bounds), one unknown year
    entries = [
        {
            "Laengengrad": "0.5",
            "Breitengrad": "0.5",
            "Inbetriebnahmedatum": "2015-02-10",
            "Bundesland": "1403",
            "id": "A1"
        },
        {
            "Laengengrad": "5",
            "Breitengrad": "5",
            "Inbetriebnahmedatum": "2015-02-10",
            "Bundesland": "1403",
            "id": "A2"
        },
        {
            "Laengengrad": "0.6",
            "Breitengrad": "0.6",
            "Inbetriebnahmedatum": "",
            "Bundesland": "1403",
            "id": "A3"
        }
    ]
    wjson(in_dir / "plants.json", entries)

    # Act
    mod.convert_by_state_year_with_three_checks(
        input_folder=str(in_dir),
        output_root=str(out_root),
        polygon_states_path="dummy",
        date_field="Inbetriebnahmedatum"
    )

    # Assert
    out_files = list(out_root.glob("*.geojson"))
    assert len(out_files) == 1  # only one year (2015)
    out_data = rjson(out_files[0])

    assert out_data["type"] == "FeatureCollection"
    features = out_data["features"]

    # Only one valid feature should be included
    assert len(features) == 1
    assert features[0]["properties"]["id"] == "A1"

    out = capsys.readouterr().out
    assert "2015" in out and "Saved" in out


def test_convert_by_state_year_with_three_checks_handles_invalid_json(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "in"
    out_root = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    # Act
    mod.convert_by_state_year_with_three_checks(
        input_folder=str(in_dir),
        output_root=str(out_root),
        polygon_states_path="dummy",
        date_field="Inbetriebnahmedatum"
    )

    # Assert
    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert not any(out_root.glob("*.geojson"))
