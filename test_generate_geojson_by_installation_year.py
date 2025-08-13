# test_generate_geojson_by_installation_year.py
"""
Unit tests for generate_geojson_by_installation_year.py

Covers:
- extract_year: happy paths and edge cases (non-str, short, out-of-range).
- create_feature: numeric strings with comma, bounds checking, property filtering.
- convert_jsons_by_year:
    * walks nested folders, ignores non-JSON, reports bad JSON
    * creates output folder and per-year .geojson files
    * writes valid Features only; excludes invalid coords/years
    * preserves properties except coordinates
    * prints progress and summary lines
    * writes nothing when no valid entries
"""

from pathlib import Path
import json
import pytest

import generate_geojson_by_installation_year as mod


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: extract_year ----------
@pytest.mark.parametrize(
    "inp,expected",
    [
        ("2025-07-01", "2025"),
        ("1999", "1999"),
        ("2000/05", "2000"),
        ("20261231", None),     # > 2025 -> None
        ("1899-01-01", None),   # < 1900 -> None
        ("20X5-01-01", None),   # first 4 not digits
        ("", None),
        (None, None),
        (1234, None),           # non-str
        (" 2024-01-01", None),  # leading space makes first 4 non-digits
    ],
)
def test_extract_year_cases(inp, expected):
    assert mod.extract_year(inp) == expected


# ---------- unit tests: create_feature ----------
def test_create_feature_accepts_comma_decimal_and_filters_coords():
    # Valid with comma decimals
    entry = {"Laengengrad": "10,5", "Breitengrad": "50,25", "x": 1}
    feat = mod.create_feature(entry)
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [10.5, 50.25]
    # Properties should NOT include the coordinate fields
    assert "Laengengrad" not in feat["properties"]
    assert "Breitengrad" not in feat["properties"]
    assert feat["properties"]["x"] == 1

    # Out-of-bounds lat
    bad_lat = {"Laengengrad": "10", "Breitengrad": "91"}
    assert mod.create_feature(bad_lat) is None

    # Out-of-bounds lon
    bad_lon = {"Laengengrad": "-181", "Breitengrad": "45"}
    assert mod.create_feature(bad_lon) is None

    # Non-numeric
    bad_num = {"Laengengrad": "east", "Breitengrad": "north"}
    assert mod.create_feature(bad_num) is None


# ---------- integration tests: convert_jsons_by_year ----------
def test_convert_groups_and_writes_geojson(tmp_path: Path, capsys):
    # Arrange: nested structure and mixed validity
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    sub = inp / "sub"
    inp.mkdir()
    sub.mkdir()

    # File A (root): mix of valid/invalid; expect 2010 and 1999
    fA = inp / "plants_A.json"
    wjson(fA, [
        {"id": 1, "Inbetriebnahmedatum": "2010-05-12", "Laengengrad": "10,0", "Breitengrad": "50,0", "name": "okA1"},
        {"id": 2, "Inbetriebnahmedatum": "1999-01-01", "Laengengrad": "9.5",  "Breitengrad": "49.5", "name": "okA2"},
        {"id": 3, "Inbetriebnahmedatum": "2010-12-31", "Laengengrad": "200",  "Breitengrad": "50"},   # bad lon
        {"id": 4, "Inbetriebnahmedatum": "abcd",       "Laengengrad": "10",   "Breitengrad": "50"},   # bad year
        {"id": 5, "Laengengrad": "10", "Breitengrad": "50"},                                           # missing year
    ])

    # File B (subfolder): valid 2025 + valid 2010 with comma decimals
    fB = sub / "plants_B.json"
    wjson(fB, [
        {"id": 10, "Inbetriebnahmedatum": "2025-07-07", "Laengengrad": "11,25", "Breitengrad": "51,75", "extra": "okB1"},
        {"id": 11, "Inbetriebnahmedatum": "2010/03/03", "Laengengrad": "12,0",  "Breitengrad": "48,0",  "extra": "okB2"},
    ])

    # Non-JSON ignored + bad JSON reported
    (inp / "README.txt").write_text("ignore", encoding="utf-8")
    bad = inp / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # Act
    mod.convert_jsons_by_year(str(inp), str(outdir))

    # Assert: output directory created
    assert outdir.exists()

    # Expect geojson files for 1999, 2010, 2025
    g1999 = outdir / "1999.geojson"
    g2010 = outdir / "2010.geojson"
    g2025 = outdir / "2025.geojson"
    assert g1999.exists() and g2010.exists() and g2025.exists()

    # Load and validate FeatureCollections
    fc1999 = rjson(g1999)
    fc2010 = rjson(g2010)
    fc2025 = rjson(g2025)
    assert fc1999["type"] == "FeatureCollection"
    assert fc2010["type"] == "FeatureCollection"
    assert fc2025["type"] == "FeatureCollection"

    # Check features count and that coordinates are correct & properties exclude lat/lon
    # 1999: one valid entry (id=2)
    assert len(fc1999["features"]) == 1
    f2 = fc1999["features"][0]
    assert f2["geometry"]["coordinates"] == [9.5, 49.5]
    assert "Laengengrad" not in f2["properties"] and "Breitengrad" not in f2["properties"]
    assert f2["properties"]["id"] == 2 and f2["properties"]["name"] == "okA2"

    # 2010: two valid entries (id=1 from A, id=11 from B)
    ids_2010 = sorted(f["properties"]["id"] for f in fc2010["features"])
    coords_2010 = sorted(tuple(f["geometry"]["coordinates"]) for f in fc2010["features"])
    assert ids_2010 == [1, 11]
    assert coords_2010 == [(10.0, 50.0), (12.0, 48.0)]

    # 2025: one valid entry (id=10)
    assert len(fc2025["features"]) == 1
    f10 = fc2025["features"][0]
    assert f10["geometry"]["coordinates"] == [11.25, 51.75]
    assert f10["properties"]["extra"] == "okB1"

    # Console output: scanning lines, bad json warning, save lines, summary
    out = capsys.readouterr().out
    assert "📂 Scanning: plants_A.json" in out and "📂 Scanning: plants_B.json" in out
    assert "⚠️ Could not load broken.json" in out
    assert "✅ Saved" in out
    assert "Processed" in out and "Valid year + coordinate entries" in out and "Skipped entries" in out


def test_no_outputs_when_no_valid_entries(tmp_path: Path, capsys):
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    inp.mkdir()

    # All invalid: years out of range / invalid formats / bad coords
    f = inp / "plants.json"
    wjson(f, [
        {"Inbetriebnahmedatum": "1889-01-01", "Laengengrad": "10", "Breitengrad": "50"},
        {"Inbetriebnahmedatum": "2099-01-01", "Laengengrad": "10", "Breitengrad": "50"},
        {"Inbetriebnahmedatum": "abcd",       "Laengengrad": "10", "Breitengrad": "50"},
        {"Inbetriebnahmedatum": "2010-01-01", "Laengengrad": "181", "Breitengrad": "50"},  # bad lon
        {"Inbetriebnahmedatum": "2010-01-01", "Laengengrad": "10",  "Breitengrad": "91"},  # bad lat
        {"Laengengrad": "10", "Breitengrad": "50"},                                         # missing year
    ])

    mod.convert_jsons_by_year(str(inp), str(outdir))

    # Outdir exists, but no .geojson files written
    assert outdir.exists()
    assert list(outdir.glob("*.geojson")) == []

    out = capsys.readouterr().out
    assert "Processing" not in out  # module prints "📂 Scanning:" not "Processing:"
    assert "📂 Scanning: plants.json" in out
    assert "✅ Saved" not in out
