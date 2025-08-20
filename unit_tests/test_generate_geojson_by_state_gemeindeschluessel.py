# test_generate_geojson_by_state_gemeindeschluessel.py
"""
Unit tests for generate_geojson_by_state_gemeindeschluessel.py

Covers:
- create_feature: comma decimals, bounds, property filtering.
- convert_jsons_by_state_prefix:
    * recursive walk, ignores non-JSON, reports bad JSON
    * groups by first 2 chars of 'Gemeindeschluessel'
    * creates per-state geojson files with correct mapped names
    * uses fallback name 'state_{prefix}' for unknown prefixes
    * writes only valid coordinate entries; excludes invalid/missing keys
    * prints scanning/saved/summary messages
"""

from pathlib import Path
import json
import pytest

import generate_geojson_by_state_gemeindeschluessel as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: create_feature ----------
def test_create_feature_filters_coords_and_accepts_comma_decimals():
    # Valid numeric strings with comma
    entry = {"Laengengrad": "10,50", "Breitengrad": "50,25", "x": 1}
    feat = mod.create_feature(entry)
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [10.5, 50.25]
    # Coordinates must not appear in properties
    assert "Laengengrad" not in feat["properties"]
    assert "Breitengrad" not in feat["properties"]
    assert feat["properties"]["x"] == 1

    # Out-of-bounds latitude
    assert mod.create_feature({"Laengengrad": "10", "Breitengrad": "91"}) is None
    # Out-of-bounds longitude
    assert mod.create_feature({"Laengengrad": "-181", "Breitengrad": "45"}) is None
    # Non-numeric
    assert mod.create_feature({"Laengengrad": "east", "Breitengrad": "north"}) is None


# ---------- integration tests: convert_jsons_by_state_prefix ----------
def test_convert_groups_and_writes_geojson(tmp_path: Path, capsys):
    # Arrange: input tree with root + subfolder
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    sub = inp / "sub"
    inp.mkdir(); sub.mkdir()

    # Root file: mix of prefixes 05 (NRW), 14 (Sachsen), and unknown XX
    fA = inp / "plants_A.json"
    wjson(fA, [
        {"id": 1, "Gemeindeschluessel": "05170048", "Laengengrad": "6,95", "Breitengrad": "51,45", "name": "A1"},  # 05
        {"id": 2, "Gemeindeschluessel": "14150000", "Laengengrad": "13.75", "Breitengrad": "51.05", "name": "A2"}, # 14
        {"id": 3, "Gemeindeschluessel": "XX000001", "Laengengrad": "10", "Breitengrad": "50", "name": "A3"},       # XX
        {"id": 4, "Gemeindeschluessel": "05179999", "Laengengrad": "200", "Breitengrad": "50"},                    # bad lon -> skip
        {"id": 5, "Laengengrad": "10", "Breitengrad": "50"},                                                       # missing key -> skip
    ])

    # Sub file: more for 05 and 14
    fB = sub / "plants_B.json"
    wjson(fB, [
        {"id": 10, "Gemeindeschluessel": "05170049", "Laengengrad": "7.00", "Breitengrad": "51.50", "extra": "B1"}, # 05
        {"id": 11, "Gemeindeschluessel": "14150001", "Laengengrad": "12.00", "Breitengrad": "50.95", "extra": "B2"},# 14
    ])

    # Non-JSON ignored; bad JSON reported
    (inp / "README.txt").write_text("ignore", encoding="utf-8")
    bad = inp / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # Act
    mod.convert_jsons_by_state_prefix(str(inp), str(outdir))

    # Assert: output directory created
    assert outdir.exists() and outdir.is_dir()

    # Expected file names: "05_nordrhein_westfalen.geojson", "14_sachsen.geojson", "XX_state_XX.geojson"
    out_05 = outdir / "05_nordrhein_westfalen.geojson"
    out_14 = outdir / "14_sachsen.geojson"
    out_xx = outdir / "XX_state_XX.geojson"

    assert out_05.exists() and out_14.exists() and out_xx.exists()

    # Load content and check FeatureCollection structure
    fc05 = rjson(out_05); fc14 = rjson(out_14); fcxx = rjson(out_xx)
    assert fc05["type"] == "FeatureCollection"
    assert fc14["type"] == "FeatureCollection"
    assert fcxx["type"] == "FeatureCollection"

    # 05: entries id=1 (from A) and id=10 (from B) with correct coords, without coord keys in properties
    ids_05 = sorted(f["properties"]["id"] for f in fc05["features"])
    coords_05 = sorted(tuple(f["geometry"]["coordinates"]) for f in fc05["features"])
    assert ids_05 == [1, 10]
    assert coords_05 == [(6.95, 51.45), (7.0, 51.5)]
    assert all("Laengengrad" not in f["properties"] and "Breitengrad" not in f["properties"] for f in fc05["features"])

    # 14: entries id=2 and id=11
    ids_14 = sorted(f["properties"]["id"] for f in fc14["features"])
    assert ids_14 == [2, 11]

    # XX: one entry id=3
    assert [f["properties"]["id"] for f in fcxx["features"]] == [3]

    # Console output: scanning lines for both files, bad JSON warning, saved lines, and summary
    out = capsys.readouterr().out
    assert "📂 Scanning: plants_A.json" in out and "📂 Scanning: plants_B.json" in out
    assert "⚠️ Could not load broken.json" in out
    assert "✅ Saved" in out
    assert "Processed" in out


def test_no_outputs_when_no_valid_entries(tmp_path: Path, capsys):
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    inp.mkdir()

    # All invalid: missing/short Gemeindeschluessel or invalid coordinates
    f = inp / "plants.json"
    wjson(f, [
        {"Gemeindeschluessel": "0", "Laengengrad": "10", "Breitengrad": "50"},      # short prefix -> skip
        {"Gemeindeschluessel": None, "Laengengrad": "10", "Breitengrad": "50"},     # missing -> skip
        {"Laengengrad": "10", "Breitengrad": "50"},                                  # missing key -> skip
        {"Gemeindeschluessel": "0517xxxx", "Laengengrad": "181", "Breitengrad": "0"} # bad lon -> skip
    ])

    mod.convert_jsons_by_state_prefix(str(inp), str(outdir))

    # Outdir exists but should contain no .geojson files
    assert outdir.exists()
    assert list(outdir.glob("*.geojson")) == []

    out = capsys.readouterr().out
    assert "📂 Scanning: plants.json" in out
    assert "✅ Saved" not in out
