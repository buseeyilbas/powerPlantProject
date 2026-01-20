# test_14_json_to_geojson_batch.py
"""
Unit tests for step14_json_to_geojson_batch module.

Covers:
1) parse_point() validation for numeric/commas/range/non-numeric cases.
2) to_feature() builds proper GeoJSON Feature with properties preserved.
3) convert_all_germany_with_three_checks(): end-to-end with a tiny polygon set,
   counting consistent features, mismatches, no-polygon matches, and handling bad JSON.
"""

import json
from pathlib import Path
import pytest

# Module under test (matches your script API)
import step14_json_to_geojson_batch as batch


def rjson(path: Path):
    """Helper: read a JSON/GeoJSON file as dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Tests for parse_point & to_feature ----------

def test_parse_point_valid_and_invalid_cases():
    # Valid decimal
    p = batch.parse_point({"Laengengrad": "10.5", "Breitengrad": "50.1"})
    assert p is not None and pytest.approx(p.x) == 10.5 and pytest.approx(p.y) == 50.1

    # Valid with comma decimals
    p = batch.parse_point({"Laengengrad": "10,5", "Breitengrad": "50,1"})
    assert p is not None and pytest.approx(p.x) == 10.5 and pytest.approx(p.y) == 50.1

    # Invalid: latitude out of range
    assert batch.parse_point({"Laengengrad": "10", "Breitengrad": "100"}) is None

    # Invalid: longitude out of range
    assert batch.parse_point({"Laengengrad": "200", "Breitengrad": "50"}) is None

    # Invalid: non-numeric
    assert batch.parse_point({"Laengengrad": "abc", "Breitengrad": "50"}) is None

    # Invalid: missing keys
    assert batch.parse_point({"name": "no coords"}) is None


def test_to_feature_builds_geojson_properties():
    """to_feature() should produce a proper GeoJSON Feature and keep properties except coords."""
    entry = {"Laengengrad": "10.0", "Breitengrad": "50.0", "id": 42, "name": "plant"}
    point = batch.parse_point(entry)
    feat = batch.to_feature(entry, point)

    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [pytest.approx(10.0), pytest.approx(50.0)]
    # Coordinates fields should be excluded from properties, others preserved
    assert feat["properties"]["id"] == 42
    assert feat["properties"]["name"] == "plant"
    assert "Laengengrad" not in feat["properties"]
    assert "Breitengrad" not in feat["properties"]


# ---------- Tests for convert_all_germany_with_three_checks ----------

def _write_polygon_states(path: Path):
    """
    Create a tiny polygon GeoJSON with one state: 'Bayern'.
    Square covering lon [10,11], lat [49,51] so test points inside will match.
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
    path.write_text(json.dumps(poly, ensure_ascii=False, indent=2), encoding="utf-8")


def test_convert_all_germany_with_three_checks_basic(tmp_path: Path, capsys):
    """
    Build a minimal dataset:
      - file1.json:
          e1: inside polygon, BL=1403 (Bayern), GS prefix 09 → consistent
          e2: invalid lon → ignored (but counted in entries_seen)
          e3: inside polygon but BL/GS mapped to Baden-Württemberg (1402/08) → mismatch
          e4: outside polygon but BL/GS correct → no_polygon_match
      - file2.json:
          e5: inside polygon, BL=1403, GS=09 → consistent
      - bad.json: malformed JSON → should print warning, not crash
    """
    in_dir = tmp_path / "input"
    in_dir.mkdir()
    out_geojson = tmp_path / "out.geojson"
    summary_path = tmp_path / "summary.json"
    polygons = tmp_path / "polygons.json"
    _write_polygon_states(polygons)

    # file1 entries
    file1 = [
        # e1: valid/consistent (Bayern)
        {"Laengengrad": "10.2", "Breitengrad": "50.0", "id": 1,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},
        # e2: invalid lon
        {"Laengengrad": "181", "Breitengrad": "50.0", "id": 2,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},
        # e3: inside polygon but mismatched BL/GS (Baden-Württemberg)
        {"Laengengrad": "10.3", "Breitengrad": "50.2", "id": 3,
         "Bundesland": "1402", "Gemeindeschluessel": "08111000"},
        # e4: outside polygon but correct BL/GS
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "id": 4,
         "Bundesland": "1403", "Gemeindeschluessel": "09670000"},
    ]
    (in_dir / "file1.json").write_text(json.dumps(file1), encoding="utf-8")

    # file2 entries
    file2 = [
        # e5: valid/consistent (Bayern)
        {"Laengengrad": "10.4", "Breitengrad": "49.5", "id": 5,
         "Bundesland": "1403", "Gemeindeschluessel": "09670001"},
    ]
    (in_dir / "file2.json").write_text(json.dumps(file2), encoding="utf-8")

    # bad.json
    (in_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")

    # Act
    batch.convert_all_germany_with_three_checks(
        input_folder=str(in_dir),
        polygon_states_path=str(polygons),
        output_geojson=str(out_geojson),
        summary_path=str(summary_path),
    )

    # Assert: output geojson
    assert out_geojson.exists()
    gj = rjson(out_geojson)
    assert gj["type"] == "FeatureCollection"
    # Only e1 and e5 should be written (consistent)
    ids = sorted([f["properties"]["id"] for f in gj["features"]])
    assert ids == [1, 5]

    # Assert: summary content
    assert summary_path.exists()
    summary = rjson(summary_path)
    # Processed 3 JSON files (file1, file2, bad.json)
    assert summary["files_processed"] == 3
    # 5 entries seen across valid files
    assert summary["entries_seen"] == 5
    # 2 consistent (e1 & e5)
    assert summary["consistent_written"] == 2
    # 1 outside polygon (e4)
    assert summary["no_polygon_match"] == 1
    # 1 mismatch (e3) counted for both BL and GS mismatch
    assert summary["bundesland_mismatch_count"] == 1
    assert summary["gemeindeschluessel_mismatch_count"] == 1
    # no missing BL/GS in our data
    assert summary["bundesland_missing_or_unmapped"] == 0
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 0

    # Console output: Should include warning for bad.json and final "Created"
    out = capsys.readouterr().out
    assert "⚠️ Could not load bad.json" in out
    assert "====== SUMMARY ======" in out
    assert "✅ Created" in out


def test_convert_all_germany_with_three_checks_empty_folder(tmp_path: Path, capsys):
    """Empty input folder should produce an empty FeatureCollection and a valid summary."""
    in_dir = tmp_path / "empty_in"
    in_dir.mkdir()
    polygons = tmp_path / "polygons.json"
    _write_polygon_states(polygons)
    out_geojson = tmp_path / "out.geojson"
    summary_path = tmp_path / "summary.json"

    batch.convert_all_germany_with_three_checks(
        input_folder=str(in_dir),
        polygon_states_path=str(polygons),
        output_geojson=str(out_geojson),
        summary_path=str(summary_path),
    )

    # Output should exist but have empty features
    gj = rjson(out_geojson)
    assert gj["type"] == "FeatureCollection"
    assert gj["features"] == []

    summary = rjson(summary_path)
    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["consistent_written"] == 0

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out
    assert "✅ Created" in out


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
