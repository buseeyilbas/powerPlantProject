# test_19_generate_geojson_by_landkreis.py
"""
Unit & integration tests for step19_generate_geojson_by_landkreis.py

Aligned with the script's real behavior:
- safe_filename: preserves case & umlauts; replaces forbidden chars with '_' and collapses multiple underscores
- parse_point: accepts '.' and ',' decimals; rejects invalid/out-of-range
- to_feature: only called with a valid shapely Point
- convert_by_landkreis:
  * loads GADM L2 polygons (properties.NAME_2)
  * groups features by matched polygon NAME_2
  * writes <OUTPUT>/<NAME_2>.geojson and a _landkreis_summary.json
  * logs with "⚠️ Could not load ..." on JSON errors and prints a summary
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


def write_tiny_l2_polygons(path: Path):
    """
    Minimal GADM L2-like polygons with NAME_2:
      - NAME_2='Bad Kissingen'  rect: lon[10.0,10.5], lat[50.0,50.5]
      - NAME_2='Rhön-Grabfeld'  rect: lon[10.5,11.0], lat[50.0,50.5]
    """
    def rect(lon1, lat1, lon2, lat2):
        return [[
            [lon1, lat1],
            [lon2, lat1],
            [lon2, lat2],
            [lon1, lat2],
            [lon1, lat1],
        ]]
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME_2": "Bad Kissingen", "NAME_1": "Bayern"},
                "geometry": {"type": "Polygon", "coordinates": rect(10.0, 50.0, 10.5, 50.5)},
            },
            {
                "type": "Feature",
                "properties": {"NAME_2": "Rhön-Grabfeld", "NAME_1": "Bayern"},
                "geometry": {"type": "Polygon", "coordinates": rect(10.5, 50.0, 11.0, 50.5)},
            },
        ],
    }
    wjson(path, gj)


# ---------- unit tests: safe_filename ----------
@pytest.mark.parametrize(
    "inp, expected_contains, forbidden",
    [
        ("München-Stadt", "München-Stadt", ["/", "\\", ":", "*", "?", "\"", "<", ">", "|", "@"]),
        ("Baden-Württemberg/2025", "Baden-Württemberg_2025", ["/", "\\"]),
        ("Landkreis@Name!", "Landkreis_Name_", ["@", "!"]),
        ("  Thüringen  ", "Thüringen", []),
    ],
)
def test_safe_filename_preserves_case_and_umlauts_but_sanitizes(inp, expected_contains, forbidden):
    out = mod.safe_filename(inp)
    assert expected_contains in out
    for ch in forbidden:
        assert ch not in out
    assert "__" not in out
    assert out.strip() != ""


# ---------- unit tests: parse_point ----------
def test_parse_point_valid_and_comma_decimal():
    dot = {"Laengengrad": "10.5", "Breitengrad": "50.1"}
    comma = {"Laengengrad": "10,5", "Breitengrad": "50,1"}
    p1, p2 = mod.parse_point(dot), mod.parse_point(comma)
    assert isinstance(p1, Point) and isinstance(p2, Point)
    assert round(p2.x, 1) == 10.5 and round(p2.y, 1) == 50.1


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


# ---------- unit tests: to_feature (only with valid point) ----------
def test_to_feature_builds_valid_geojson():
    entry = {
        "Laengengrad": "10.2",
        "Breitengrad": "50.3",
        "Bundesland": "1403",
        "Landkreis": "Bad Kissingen",
        "Energietraeger": "2493",
        "id": "X1",
    }
    f = mod.to_feature(entry, Point(10.2, 50.3))
    assert f["type"] == "Feature"
    assert f["geometry"]["type"] == "Point"
    assert f["geometry"]["coordinates"] == [pytest.approx(10.2), pytest.approx(50.3)]
    # coord fields not duplicated in properties
    props = f["properties"]
    assert props["id"] == "X1"
    assert "Laengengrad" not in props and "Breitengrad" not in props


# ---------- integration: convert_by_landkreis ----------
def test_convert_by_landkreis_creates_expected_files_and_summary(tmp_path, capsys):
    # Arrange: input data
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()

    entries = [
        # inside Bad Kissingen
        {"Laengengrad": "10.1", "Breitengrad": "50.1", "id": 1, "Landkreis": "Bad Kissingen"},
        # inside Rhön-Grabfeld
        {"Laengengrad": "10.6", "Breitengrad": "50.2", "id": 2, "Landkreis": "Rhön-Grabfeld"},
        # invalid coords → skipped
        {"Laengengrad": "200", "Breitengrad": "95", "id": 3, "Landkreis": "Bad Kissingen"},
        # outside any polygon → unmatched
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "id": 4, "Landkreis": "Bad Kissingen"},
    ]
    wjson(in_dir / "plants.json", entries)

    # Tiny polygons file
    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    # Act
    mod.convert_by_landkreis(str(in_dir), str(out_dir), gadm_l2_path=str(gadm_path))

    # Assert: per-Landkreis files
    bk_path = out_dir / (mod.safe_filename("Bad Kissingen") + ".geojson")
    rg_path = out_dir / (mod.safe_filename("Rhön-Grabfeld") + ".geojson")
    assert bk_path.exists() and rg_path.exists()

    bk = rjson(bk_path)
    rg = rjson(rg_path)
    assert bk["type"] == "FeatureCollection" and rg["type"] == "FeatureCollection"

    ids_bk = sorted(f["properties"].get("id") for f in bk["features"])
    ids_rg = sorted(f["properties"].get("id") for f in rg["features"])
    assert ids_bk == [1]
    assert ids_rg == [2]

    # Summary
    summary = rjson(out_dir / "_landkreis_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 4
    assert summary["matched_entries"] == 2
    assert summary["unmatched_entries"] == 1  # the valid-but-outside one
    assert summary["output_folder"] == str(out_dir)
    assert summary["gadm_l2_path"] == str(gadm_path)

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out
    assert "✅ Saved" in out


def test_convert_by_landkreis_handles_invalid_json(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    # polygons still required for init
    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    # Act
    mod.convert_by_landkreis(str(in_dir), str(out_dir), gadm_l2_path=str(gadm_path))

    # Assert: warning printed, no .geojsons
    out = capsys.readouterr().out
    assert "⚠️ Could not load broken.json" in out
    assert not list(out_dir.rglob("*.geojson"))

    # Summary with zeros
    summary = rjson(out_dir / "_landkreis_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 0
    assert summary["matched_entries"] == 0
    assert summary["unmatched_entries"] == 0


# --- run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
