# test_18_generate_geojson_by_state_landkreis_yearly.py
"""
Tests aligned to step18_generate_geojson_by_state_landkreis_yearly.py actual API.

Covers:
- extract_year: ISO, short-year, invalid → 'YYYY' or 'unknown'
- safe_filename: preserves case/umlauts; replaces forbidden chars with '_' and collapses multiple underscores
- parse_point: accepts '.' and ',' decimals; rejects invalid/out-of-range
- to_feature: builds a valid GeoJSON Feature (called only with a valid Point)
- convert_state_landkreis_yearly (integration):
  * loads tiny GADM L2 polygons (properties.NAME_1=state, NAME_2=landkreis)
  * groups by state / landkreis / year
  * writes <OUTPUT_ROOT>/<State>/<Landkreis>/<YYYY>.geojson
  * writes _state_landkreis_yearly_summary.json and prints a summary
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


def write_tiny_l2_polygons(path: Path):
    """
    Minimal Level-2 polygons with:
      - NAME_1='Bayern', NAME_2='Bad Kissingen'  (rect: lon[10.0,10.5], lat[50.0,50.5])
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
                "properties": {"NAME_1": "Bayern", "NAME_2": "Bad Kissingen"},
                "geometry": {"type": "Polygon", "coordinates": rect(10.0, 50.0, 10.5, 50.5)},
            }
        ],
    }
    wjson(path, gj)


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
    "inp, expected_contains, forbidden",
    [
        ("München/Stadt", "München_Stadt", ["/", "\\"]),
        ("Region-Name (2024)", "Region-Name _2024", ["(", ")"]),
        ("  Thüringen!", "Thüringen", ["!"]),
        ("A@B#C", "A_B_C", ["@", "#"]),
    ],
)
def test_safe_filename_preserves_umlauts_and_sanitizes(inp, expected_contains, forbidden):
    result = mod.safe_filename(inp)
    # keeps case & umlauts; forbidden chars removed/replaced with underscores
    assert expected_contains in result
    for ch in forbidden:
        assert ch not in result
    assert "__" not in result
    assert result.strip() != ""


# ---------- unit tests: parse_point ----------
def test_parse_point_accepts_dots_and_commas():
    e1 = {"Laengengrad": "10.2", "Breitengrad": "50.5"}
    e2 = {"Laengengrad": "10,2", "Breitengrad": "50,5"}
    p1, p2 = mod.parse_point(e1), mod.parse_point(e2)
    assert isinstance(p1, Point) and isinstance(p2, Point)
    assert round(p2.x, 1) == 10.2 and round(p2.y, 1) == 50.5


@pytest.mark.parametrize(
    "entry",
    [
        {"Laengengrad": "abc", "Breitengrad": "50"},
        {"Laengengrad": "10", "Breitengrad": "95"},
        {"Laengengrad": None, "Breitengrad": "50"},
    ],
)
def test_parse_point_invalid(entry):
    assert mod.parse_point(entry) is None


# ---------- unit tests: to_feature (only with valid point) ----------
def test_to_feature_builds_geojson_feature():
    entry = {
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "Landkreis": "Bad Kissingen",
        "Inbetriebnahmedatum": "2020-05-06",
        "Energietraeger": "2493",
        "id": 99,
    }
    feat = mod.to_feature(entry, Point(10.5, 50.0))
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [pytest.approx(10.5), pytest.approx(50.0)]
    assert feat["properties"]["id"] == 99
    # coordinate fields are not duplicated into properties
    assert "Laengengrad" not in feat["properties"]
    assert "Breitengrad" not in feat["properties"]


# ---------- integration: convert_state_landkreis_yearly ----------
def test_convert_state_landkreis_yearly_creates_expected_tree(tmp_path, capsys):
    # Arrange
    in_dir = tmp_path / "in"
    out_root = tmp_path / "out"
    in_dir.mkdir()

    # two valid points inside polygon (year 2020), one invalid coords, one valid outside polygon
    entries = [
        {"Laengengrad": "10.0", "Breitengrad": "50.0", "Landkreis": "Bad Kissingen", "Inbetriebnahmedatum": "2020-06-15", "id": 1},
        {"Laengengrad": "10.2", "Breitengrad": "50.1", "Landkreis": "Bad Kissingen", "Inbetriebnahmedatum": "2020-12-31", "id": 2},
        {"Laengengrad": "abc",  "Breitengrad": "xyz",  "Landkreis": "Bad Kissingen", "Inbetriebnahmedatum": "2020-01-01", "id": 3},
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "Landkreis": "Bad Kissingen", "Inbetriebnahmedatum": "2020-07-07", "id": 4},
    ]
    wjson(in_dir / "plants.json", entries)

    # tiny L2 polygons
    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    # Act
    mod.convert_state_landkreis_yearly(
        input_folder=str(in_dir),
        output_root=str(out_root),
        gadm_l2_path=str(gadm_path),
        date_field="Inbetriebnahmedatum"
    )

    # Assert output tree: <out_root>/Bayern/Bad Kissingen/2020.geojson
    state_dir = out_root / mod.safe_filename("Bayern")
    lkr_dir = state_dir / mod.safe_filename("Bad Kissingen")
    out_file = lkr_dir / "2020.geojson"

    assert out_file.exists()
    data = rjson(out_file)
    assert data["type"] == "FeatureCollection"
    ids = sorted(f["properties"]["id"] for f in data["features"])
    assert ids == [1, 2]  # inside polygon & valid coords

    # Summary checks
    summary = rjson(out_root / "_state_landkreis_yearly_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 4
    assert summary["matched_entries"] == 2
    assert summary["unmatched_entries"] == 1  # only the valid-but-outside point (id=4)

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out
    assert "✅ Saved" in out


def test_convert_state_landkreis_yearly_handles_invalid_json(tmp_path, capsys):
    in_dir = tmp_path / "in"
    out_root = tmp_path / "out"
    in_dir.mkdir()

    (in_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    # need a valid polygons file even though JSON is broken
    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    mod.convert_state_landkreis_yearly(
        input_folder=str(in_dir),
        output_root=str(out_root),
        gadm_l2_path=str(gadm_path),
        date_field="Inbetriebnahmedatum"
    )

    out = capsys.readouterr().out
    assert "⚠️ Could not load broken.json" in out
    # no geojson files created
    assert not list(out_root.rglob("*.geojson"))

    summary = rjson(out_root / "_state_landkreis_yearly_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 0
    assert summary["matched_entries"] == 0
    assert summary["unmatched_entries"] == 0


# --- run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
