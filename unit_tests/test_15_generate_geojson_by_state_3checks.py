# test_15_generate_geojson_by_state_3checks.py
"""
Unit tests for step15_generate_geojson_by_state_3checks.py

Covers:
- normalize_state_name: umlauts, punctuation, spacing, parentheses
- bl_code_to_norm_name: valid Bundesland codes and fallback
- polygon_state_of_point: detects correct state or None
- to_feature + parse_point: valid/invalid coordinate handling
- convert_with_three_checks: end-to-end with tiny polygon file,
  writes per-state GeoJSONs into OUTPUT_FOLDER and creates a summary
"""

import json
from pathlib import Path
import pytest
from shapely.geometry import Point, Polygon, MultiPolygon

import step15_generate_geojson_by_state_3checks as mod


# ----------------- helpers -----------------
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


# ----------------- unit tests -----------------

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


@pytest.mark.parametrize(
    "bl,expected",
    [
        ("1403", "bayern"),
        ("1402", "badenwuerttemberg"),  # normalized (no hyphen/underscore/spaces)
        ("1415", "thueringen"),
        ("9999", None),
        (None, None),
    ],
)
def test_bl_code_to_norm_name_cases(bl, expected):
    assert mod.bl_code_to_norm_name(bl) == expected


def test_polygon_state_of_point_detects_inside_and_outside():
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mapping = {"bayern": MultiPolygon([polygon])}
    inside = Point(0.5, 0.5)
    outside = Point(2, 2)
    assert mod.polygon_state_of_point(inside, mapping) == "bayern"
    assert mod.polygon_state_of_point(outside, mapping) is None


def test_to_feature_and_parse_point_valid_and_invalid():
    entry_valid = {"Laengengrad": "10.0", "Breitengrad": "50.0", "Bundesland": "1403", "id": 1}
    p = mod.parse_point(entry_valid)
    assert p is not None
    feat = mod.to_feature(entry_valid, p)
    assert feat["geometry"]["type"] == "Point"
    assert feat["properties"]["Bundesland"] == "1403"
    assert feat["properties"]["id"] == 1
    assert "Laengengrad" not in feat["properties"]
    assert "Breitengrad" not in feat["properties"]

    entry_comma = {"Laengengrad": "10,5", "Breitengrad": "50,5", "Bundesland": "1403"}
    p2 = mod.parse_point(entry_comma)
    assert p2 is not None
    assert pytest.approx(p2.x) == 10.5 and pytest.approx(p2.y) == 50.5

    # invalid inputs -> parse_point returns None (to_feature won't be called)
    assert mod.parse_point({"Laengengrad": "10", "Breitengrad": "95"}) is None
    assert mod.parse_point({"Laengengrad": "200", "Breitengrad": "50"}) is None
    assert mod.parse_point({"Laengengrad": "abc", "Breitengrad": "50"}) is None
    assert mod.parse_point({"name": "no coords"}) is None


# ----------------- integration: convert_with_three_checks -----------------

def test_convert_with_three_checks_creates_valid_geojson(tmp_path: Path, capsys, monkeypatch):
    """
    Dataset:
      - file1.json:
          e1: inside polygon, BL=1403 (Bayern), GS prefix 09 → consistent
          e2: invalid lon → ignored
          e3: inside polygon but BL/GS mapped to Baden-Württemberg → mismatch
          e4: outside polygon but BL/GS set to Bayern → no_polygon_match
      - file2.json:
          e5: inside polygon, BL=1403, GS=09 → consistent
      - bad.json: malformed → warning, no crash
    """
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    in_dir.mkdir()

    # monkeypatch OUTPUT_FOLDER so the function writes into tmp out_dir
    monkeypatch.setattr(mod, "OUTPUT_FOLDER", str(out_dir), raising=False)

    polygons_path = tmp_path / "polygons.json"
    write_tiny_state_polygons(polygons_path)

    # file1 entries
    file1 = [
        # e1: valid/consistent (Bayern)
        {"Laengengrad": "10.2", "Breitengrad": "50.0", "id": 1,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},
        # e2: invalid lon (ignored)
        {"Laengengrad": "181", "Breitengrad": "50.0", "id": 2,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},
        # e3: inside polygon but mismatched BL/GS (Baden-Württemberg)
        {"Laengengrad": "10.3", "Breitengrad": "50.2", "id": 3,
         "Bundesland": "1402", "Gemeindeschluessel": "08111000"},
        # e4: outside polygon but BL/GS for Bayern
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "id": 4,
         "Bundesland": "1403", "Gemeindeschluessel": "09670000"},
    ]
    wjson(in_dir / "file1.json", file1)

    # file2 entries
    file2 = [
        # e5: valid/consistent (Bayern)
        {"Laengengrad": "10.4", "Breitengrad": "49.5", "id": 5,
         "Bundesland": "1403", "Gemeindeschluessel": "09670001"},
    ]
    wjson(in_dir / "file2.json", file2)

    # bad.json
    (in_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")

    # Act
    mod.convert_with_three_checks(
        input_folder=str(in_dir),
        output_folder=str(out_dir),            # ignored by script, we monkeypatched OUTPUT_FOLDER
        polygon_states_path=str(polygons_path)
    )

    # Assert: per-state GeoJSON saved under OUTPUT_FOLDER
    out_files = list(out_dir.glob("*.geojson"))
    assert len(out_files) == 1
    data = rjson(out_files[0])
    assert data["type"] == "FeatureCollection"
    ids = sorted([f["properties"]["id"] for f in data["features"]])
    assert ids == [1, 5]  # only consistent ones

    # Summary file
    summary = rjson(out_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 3
    assert summary["entries_seen"] == 5
    assert summary["consistent"] == 2
    assert summary["no_polygon_match"] == 1    # e4
    assert summary["bundesland_missing_or_unmapped"] == 0
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 0
    assert summary["bundesland_mismatch_count"] == 1  # e3
    assert summary["gemeindeschluessel_mismatch_count"] == 1  # e3

    out = capsys.readouterr().out
    assert "⚠️ Could not load bad.json" in out
    assert "====== SUMMARY ======" in out
    assert "✅ Saved" in out


def test_convert_with_three_checks_handles_invalid_json_only(tmp_path: Path, capsys, monkeypatch):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    # monkeypatch OUTPUT_FOLDER so files land in tmp
    monkeypatch.setattr(mod, "OUTPUT_FOLDER", str(out_dir), raising=False)

    polygons_path = tmp_path / "polygons.json"
    write_tiny_state_polygons(polygons_path)

    mod.convert_with_three_checks(
        input_folder=str(in_dir),
        output_folder=str(out_dir),            # ignored by script, we monkeypatched OUTPUT_FOLDER
        polygon_states_path=str(polygons_path)
    )

    out = capsys.readouterr().out
    assert "⚠️ Could not load bad.json" in out
    assert not list(out_dir.glob("*.geojson"))
    # summary still written with zeros
    summary = rjson(out_dir / "_consistency_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 0
    assert summary["consistent"] == 0


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
