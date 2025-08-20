# test_generate_geojson_by_state_polygons.py
"""
Unit tests for generate_geojson_by_state_polygons.py

Covers:
- create_feature: comma decimals, bounds checking, non-numeric handling, properties filter.
- convert_jsons:
    * walks recursively, ignores non-JSON, reports bad JSON
    * uses monkeypatched state_polygons for deterministic tests
    * groups matched entries by state name and writes <state>.geojson
    * writes only valid coordinate entries; logs unmatched entries
    * prints scanning/saved/summary lines
"""

from pathlib import Path
import json
import pytest
from shapely.geometry import Polygon, MultiPolygon

import generate_geojson_by_state_polygons as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: create_feature ----------
def test_create_feature_valid_and_edge_cases():
    # Valid with comma decimals; properties must exclude coord keys
    f_point, feat = mod.create_feature({"Laengengrad": "10,50", "Breitengrad": "50,25", "id": 1, "name": "ok"})
    assert f_point is not None and feat["type"] == "Feature"
    assert feat["geometry"]["coordinates"] == [10.5, 50.25]
    assert "Laengengrad" not in feat["properties"] and "Breitengrad" not in feat["properties"]
    assert feat["properties"]["id"] == 1 and feat["properties"]["name"] == "ok"

    # Out-of-bounds latitude
    p, f = mod.create_feature({"Laengengrad": "10", "Breitengrad": "91"})
    assert p is None and f is None

    # Out-of-bounds longitude
    p, f = mod.create_feature({"Laengengrad": "-181", "Breitengrad": "45"})
    assert p is None and f is None

    # Non-numeric inputs
    p, f = mod.create_feature({"Laengengrad": "east", "Breitengrad": "north"})
    assert p is None and f is None


# ---------- integration tests: convert_jsons ----------
def test_convert_groups_and_writes_geojson(tmp_path: Path, monkeypatch, capsys):
    # Arrange input tree
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    sub = inp / "sub"
    inp.mkdir(); sub.mkdir()

    # Root file: mix of matched (NRW, Sachsen) + unmatched + invalids
    fA = inp / "plants_A.json"
    wjson(fA, [
        # Inside NRW square (lon/lat in [0,1])
        {"EinheitMastrNummer": "A1", "Laengengrad": "0.50", "Breitengrad": "0.50", "name": "in_nrw"},
        # Inside Sachsen square (2..3)
        {"EinheitMastrNummer": "A2", "Laengengrad": "2.10", "Breitengrad": "2.60", "name": "in_sachsen"},
        # Unmatched far away
        {"EinheitMastrNummer": "A3", "Laengengrad": "10", "Breitengrad": "10", "name": "unmatched"},
        # Invalid coord -> skipped
        {"EinheitMastrNummer": "A4", "Laengengrad": "200", "Breitengrad": "50"},
        # Missing coord -> skipped
        {"EinheitMastrNummer": "A5", "Breitengrad": "50"},
    ])

    # Sub file: more matched entries
    fB = sub / "plants_B.json"
    wjson(fB, [
        {"EinheitMastrNummer": "B1", "Laengengrad": "0.75", "Breitengrad": "0.25", "extra": "ok"},
        {"EinheitMastrNummer": "B2", "Laengengrad": "2.50", "Breitengrad": "2.10", "extra": "ok"},
    ])

    # Non-JSON ignored + bad JSON reported
    (inp / "README.md").write_text("# ignore", encoding="utf-8")
    bad = inp / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # Monkeypatch state_polygons to two simple squares:
    # NRW: square from (0,0) to (1,1), Sachsen: square from (2,2) to (3,3)
    nrw_poly = MultiPolygon([Polygon([(0,0), (0,1), (1,1), (1,0)])])
    sax_poly = MultiPolygon([Polygon([(2,2), (2,3), (3,3), (3,2)])])
    monkeypatch.setattr(mod, "state_polygons", [
        ("05", "NRW", nrw_poly),
        ("14", "Sachsen", sax_poly),
    ], raising=True)

    # Act
    mod.convert_jsons(str(inp), str(outdir))

    # Assert: outdir and expected state files exist
    assert outdir.exists() and outdir.is_dir()
    f_nrw = outdir / "NRW.geojson"
    f_sax = outdir / "Sachsen.geojson"
    assert f_nrw.exists() and f_sax.exists()

    # Validate FeatureCollections
    fc_nrw = rjson(f_nrw)
    fc_sax = rjson(f_sax)
    assert fc_nrw["type"] == "FeatureCollection"
    assert fc_sax["type"] == "FeatureCollection"

    # NRW: features from A1 and B1
    ids_nrw = sorted(feat["properties"]["EinheitMastrNummer"] for feat in fc_nrw["features"])
    coords_nrw = sorted(tuple(feat["geometry"]["coordinates"]) for feat in fc_nrw["features"])
    assert ids_nrw == ["A1", "B1"]
    assert coords_nrw == [(0.5, 0.5), (0.75, 0.25)]

    # Sachsen: features from A2 and B2
    ids_sax = sorted(feat["properties"]["EinheitMastrNummer"] for feat in fc_sax["features"])
    assert ids_sax == ["A2", "B2"]

    # Console output lines
    out = capsys.readouterr().out
    assert "📂 Scanning: plants_A.json" in out and "📂 Scanning: plants_B.json" in out
    assert "⚠️ Could not load broken.json" in out
    assert "✅ Saved" in out
    assert "Processed" in out and "Matched entries" in out and "Unmatched entries" in out
    # Unmatched log should mention EinheitMastrNummer A3
    assert "Not matched: A3" in out


def test_no_outputs_when_no_matches_or_only_invalid(tmp_path: Path, monkeypatch, capsys):
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    inp.mkdir()

    # All invalid or outside polygons → no outputs
    f = inp / "plants.json"
    wjson(f, [
        {"EinheitMastrNummer": "X1", "Laengengrad": "181", "Breitengrad": "0"},  # bad lon
        {"EinheitMastrNummer": "X2", "Laengengrad": "10"},                       # missing lat
        {"EinheitMastrNummer": "X3", "Laengengrad": "100", "Breitengrad": "89.9"},  # far away
    ])

    # Empty polygons list → nothing can match
    monkeypatch.setattr(mod, "state_polygons", [], raising=True)

    mod.convert_jsons(str(inp), str(outdir))

    assert outdir.exists()
    # No .geojson written
    assert list(outdir.glob("*.geojson")) == []

    out = capsys.readouterr().out
    assert "📂 Scanning: plants.json" in out
    assert "✅ Saved" not in out
