# test_16_generate_geojson_by_state_3checks_yearly.py
"""
Unit & integration tests for step16_generate_geojson_by_state_3checks_yearly.py

Covers:
- extract_year: different date formats → 'YYYY' or 'unknown'
- parse_point: decimals/commas and invalid/out-of-range coords
- polygon_state_of_point: find state polygon or None
- bl_code_to_norm_name / gs_prefix_to_norm_name: mapping correctness
- convert_by_state_year_with_three_checks:
  * reads polygons from file (properties.name)
  * triple-consistency (polygon + Bundesland + GS prefix)
  * groups by state/year and writes <PrettyState>/<YYYY>.geojson
  * writes _consistency_summary.json and prints summary
"""

import json
from pathlib import Path
import pytest
from shapely.geometry import Point, Polygon, MultiPolygon

import step16_generate_geojson_by_state_3checks_yearly as mod


# ---------- helpers ----------

def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_tiny_state_polygons(path: Path):
    """
    Create a tiny polygon GeoJSON with one state named 'Bayern'.
    Square covering lon [10,11], lat [49,51] so points inside will match.
    """
    poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Bayern"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [10.0, 49.0],
                        [11.0, 49.0],
                        [11.0, 51.0],
                        [10.0, 51.0],
                        [10.0, 49.0],
                    ]]
                }
            }
        ]
    }
    wjson(path, poly)


# ---------- unit tests ----------

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


def test_polygon_state_of_point_detects_inside_and_outside():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mp = MultiPolygon([poly])
    mapping = {"bayern": mp}
    assert mod.polygon_state_of_point(Point(0.5, 0.5), mapping) == "bayern"
    assert mod.polygon_state_of_point(Point(2, 2), mapping) is None


@pytest.mark.parametrize(
    "bl,expected",
    [
        ("1403", "bayern"),
        ("1402", "badenwuerttemberg"),
        ("1415", "thueringen"),
        ("9999", None),
        (None, None),
    ],
)
def test_bl_code_to_norm_name_cases(bl, expected):
    assert mod.bl_code_to_norm_name(bl) == expected


@pytest.mark.parametrize(
    "gs,expected",
    [
        ("09XXXXXX", "bayern"),
        ("08XXXXXX", "badenwuerttemberg"),
        ("16XXXXXX", "thueringen"),
        ("", None),
        (None, None),
        ("0", None),
    ],
)
def test_gs_prefix_to_norm_name_cases(gs, expected):
    assert mod.gs_prefix_to_norm_name(gs) == expected


# ---------- integration test ----------

def test_convert_by_state_year_with_three_checks_creates_geojson(tmp_path: Path, capsys):
    """
    Dataset:
      - file1.json:
          e1: inside polygon, BL=1403 (Bayern), GS prefix 09, year 2015 → consistent (kept)
          e2: invalid lon → ignored
          e3: inside polygon but BL/GS for Baden-Württemberg → mismatch
          e4: outside polygon but BL/GS = Bayern → no_polygon_match
      - file2.json:
          e5: inside polygon, BL=1403, GS=09, year 2019 → consistent (kept)
      - bad.json: malformed → warning, no crash
    """
    in_dir = tmp_path / "input"
    out_root = tmp_path / "out"
    in_dir.mkdir()

    polygons_path = tmp_path / "polygons.json"
    write_tiny_state_polygons(polygons_path)

    file1 = [
        {"Laengengrad": "10.2", "Breitengrad": "50.0", "id": 1,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121", "Inbetriebnahmedatum": "2015-02-10"},
        {"Laengengrad": "181", "Breitengrad": "50.0", "id": 2,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121", "Inbetriebnahmedatum": "2015-02-10"},
        {"Laengengrad": "10.3", "Breitengrad": "50.2", "id": 3,
         "Bundesland": "1402", "Gemeindeschluessel": "08111000", "Inbetriebnahmedatum": "2015-02-10"},
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "id": 4,
         "Bundesland": "1403", "Gemeindeschluessel": "09670000", "Inbetriebnahmedatum": "2015-02-10"},
    ]
    wjson(in_dir / "file1.json", file1)

    file2 = [
        {"Laengengrad": "10.4", "Breitengrad": "49.5", "id": 5,
         "Bundesland": "1403", "Gemeindeschluessel": "09670001", "Inbetriebnahmedatum": "2019-01-01"},
    ]
    wjson(in_dir / "file2.json", file2)

    (in_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")

    # Act
    mod.convert_by_state_year_with_three_checks(
        input_folder=str(in_dir),
        output_root=str(out_root),
        polygon_states_path=str(polygons_path),
        date_field="Inbetriebnahmedatum"
    )

    # Assert: per-state folder with per-year GeoJSONs
    state_dir = out_root / "Bayern"
    assert state_dir.exists()
    out_files = sorted(p.name for p in state_dir.glob("*.geojson"))
    # Expect 2015.geojson and 2019.geojson
    assert out_files == ["2015.geojson", "2019.geojson"]

    gj_2015 = rjson(state_dir / "2015.geojson")
    gj_2019 = rjson(state_dir / "2019.geojson")
    assert gj_2015["type"] == "FeatureCollection"
    assert gj_2019["type"] == "FeatureCollection"

    ids_2015 = sorted([f["properties"]["id"] for f in gj_2015["features"]])
    ids_2019 = sorted([f["properties"]["id"] for f in gj_2019["features"]])
    assert ids_2015 == [1]     # only consistent one from 2015
    assert ids_2019 == [5]     # consistent one from 2019

    # Summary JSON (in output_root)
    summary = rjson(out_root / "_consistency_summary.json")
    assert summary["files_processed"] == 3
    assert summary["entries_seen"] == 5
    assert summary["consistent"] == 2
    assert summary["no_polygon_match"] == 1       # e4
    assert summary["bundesland_missing_or_unmapped"] == 0
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 0
    assert summary["bundesland_mismatch_count"] == 1  # e3
    assert summary["gemeindeschluessel_mismatch_count"] == 1  # e3

    out = capsys.readouterr().out
    assert "⚠️ Could not load bad.json" in out
    assert "====== SUMMARY ======" in out
    assert "✅ Saved 1 features → Bayern/2015.geojson" in out or "✅ Saved 1 features" in out


def test_convert_by_state_year_with_three_checks_handles_invalid_json(tmp_path: Path, capsys):
    # Arrange
    in_dir = tmp_path / "in"
    out_root = tmp_path / "out"
    in_dir.mkdir()

    (in_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    polygons_path = tmp_path / "polygons.json"
    write_tiny_state_polygons(polygons_path)

    # Act
    mod.convert_by_state_year_with_three_checks(
        input_folder=str(in_dir),
        output_root=str(out_root),
        polygon_states_path=str(polygons_path),
        date_field="Inbetriebnahmedatum"
    )

    # Assert: no geojson written, summary with zeros, warning printed
    out = capsys.readouterr().out
    assert "⚠️ Could not load broken.json" in out
    assert not any(out_root.rglob("*.geojson"))

    summary = rjson(out_root / "_consistency_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 0
    assert summary["consistent"] == 0


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
