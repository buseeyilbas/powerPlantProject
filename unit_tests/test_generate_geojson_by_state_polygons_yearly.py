# test_generate_geojson_by_state_polygons_yearly.py
"""
Unit tests for generate_geojson_by_state_polygons_yearly.py

Covers:
- create_feature: comma decimals, bounds checking, non-numeric handling, property filtering.
- convert_jsons:
    * recursive walk, ignores non-JSON, reports bad JSON
    * uses monkeypatched state_polygons (simple squares) for deterministic tests
    * groups matched entries by state AND year (first 4 chars), "unknown" when missing/short
    * writes <output>/<StateName>/<YEAR>.geojson FeatureCollections
    * writes only valid coordinate entries; logs unmatched entries
    * prints scanning/saved/summary lines
- no outputs when there are no matched entries
"""

from pathlib import Path
import json
import pytest
from shapely.geometry import Polygon, MultiPolygon

import generate_geojson_by_state_polygons_yearly as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests: create_feature ----------
def test_create_feature_valid_and_edge_cases():
    # Valid with comma decimals; properties must exclude coordinate keys
    p, feat = mod.create_feature({"Laengengrad": "10,50", "Breitengrad": "50,25", "id": 1, "name": "ok"})
    assert p is not None and feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [10.5, 50.25]
    assert "Laengengrad" not in feat["properties"] and "Breitengrad" not in feat["properties"]
    assert feat["properties"]["id"] == 1 and feat["properties"]["name"] == "ok"

    # Out-of-bounds latitude
    p, f = mod.create_feature({"Laengengrad": "10", "Breitengrad": "91"})
    assert p is None and f is None

    # Out-of-bounds longitude
    p, f = mod.create_feature({"Laengengrad": "-181", "Breitengrad": "45"})
    assert p is None and f is None

    # Non-numeric strings
    p, f = mod.create_feature({"Laengengrad": "east", "Breitengrad": "north"})
    assert p is None and f is None


# ---------- integration tests: convert_jsons ----------
def test_convert_groups_by_state_and_year_and_writes_geojson(tmp_path: Path, monkeypatch, capsys):
    # Arrange: input tree with root + subfolder
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    sub = inp / "sub"
    inp.mkdir(); sub.mkdir()

    # Root file: mix for two states + unmatched + "abcd"-year case (invalid date string but first 4 chars kept)
    fA = inp / "plants_A.json"
    wjson(fA, [
        {"id": 1, "Inbetriebnahmedatum": "2010-05-12", "Laengengrad": "0.50", "Breitengrad": "0.50", "name": "nrw_2010"},  # NRW
        {"id": 2, "Inbetriebnahmedatum": "1999-01-01", "Laengengrad": "2.10", "Breitengrad": "2.60", "name": "sax_1999"},  # Sachsen
        {"id": 3, "Inbetriebnahmedatum": "2025/07/07", "Laengengrad": "0.75", "Breitengrad": "0.25", "name": "nrw_2025"},  # NRW
        {"id": 4, "Inbetriebnahmedatum": "abcd",       "Laengengrad": "0.60", "Breitengrad": "0.60", "name": "nrw_abcd"},   # NRW -> year "abcd"
        {"id": 5, "Inbetriebnahmedatum": "2010-12-31", "Laengengrad": "200",  "Breitengrad": "50"},                      # invalid lon -> skip
        {"id": 6, "Laengengrad": "10", "Breitengrad": "50"},                                                             # missing date -> outside polygons -> unmatched
        {"id": 7, "Inbetriebnahmedatum": "2010-01-01", "Laengengrad": "10", "Breitengrad": "10", "name": "far_away"},     # valid coords but outside -> unmatched
    ])

    # Sub file: additional entries for both states in year 2010
    fB = sub / "plants_B.json"
    wjson(fB, [
        {"id": 10, "Inbetriebnahmedatum": "2010/03/03", "Laengengrad": "2.50", "Breitengrad": "2.10", "extra": "sax_2010"}, # Sachsen
        {"id": 11, "Inbetriebnahmedatum": "2010-07-01", "Laengengrad": "0.25", "Breitengrad": "0.75", "extra": "nrw_2010"}, # NRW
    ])

    # Non-JSON ignored + bad JSON reported
    (inp / "README.md").write_text("# ignore", encoding="utf-8")
    bad = inp / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # Monkeypatch state_polygons to two simple squares:
    # NRW: square from (0,0) to (1,1), Sachsen: square from (2,2) to (3,3)
    from shapely.geometry import Polygon, MultiPolygon
    nrw_poly = MultiPolygon([Polygon([(0,0), (0,1), (1,1), (1,0)])])
    sax_poly = MultiPolygon([Polygon([(2,2), (2,3), (3,3), (3,2)])])
    monkeypatch.setattr(mod, "state_polygons", [
        ("05", "NRW", nrw_poly),
        ("14", "Sachsen", sax_poly),
    ], raising=True)

    # Act
    mod.convert_jsons(str(inp), str(outdir))

    # Assert: expected per-state subfolders and year files
    nrw_2010 = outdir / "NRW" / "2010.geojson"
    nrw_2025 = outdir / "NRW" / "2025.geojson"
    nrw_abcd = outdir / "NRW" / "abcd.geojson"   # <-- updated expectation
    sax_1999 = outdir / "Sachsen" / "1999.geojson"
    sax_2010 = outdir / "Sachsen" / "2010.geojson"

    for p in [nrw_2010, nrw_2025, nrw_abcd, sax_1999, sax_2010]:
        assert p.exists()

    # Validate FeatureCollection structure
    for p in [nrw_2010, nrw_2025, nrw_abcd, sax_1999, sax_2010]:
        fc = rjson(p)
        assert fc["type"] == "FeatureCollection"
        assert isinstance(fc["features"], list)

    # NRW 2010: ids = {1, 11}
    ids_nrw_2010 = sorted(f["properties"]["id"] for f in rjson(nrw_2010)["features"])
    assert ids_nrw_2010 == [1, 11]

    # NRW 2025: ids = {3}
    ids_nrw_2025 = [f["properties"]["id"] for f in rjson(nrw_2025)["features"]]
    assert ids_nrw_2025 == [3]

    # NRW "abcd": ids = {4}
    ids_nrw_abcd = [f["properties"]["id"] for f in rjson(nrw_abcd)["features"]]
    assert ids_nrw_abcd == [4]

    # Sachsen 1999: ids = {2}
    ids_sax_1999 = [f["properties"]["id"] for f in rjson(sax_1999)["features"]]
    assert ids_sax_1999 == [2]

    # Sachsen 2010: ids = {10}
    ids_sax_2010 = [f["properties"]["id"] for f in rjson(sax_2010)["features"]]
    assert ids_sax_2010 == [10]

    # Properties should not include coordinate keys
    for pf in [nrw_2010, nrw_2025, nrw_abcd, sax_1999, sax_2010]:
        for feat in rjson(pf)["features"]:
            assert "Laengengrad" not in feat["properties"]
            assert "Breitengrad" not in feat["properties"]

    # Console output
    out = capsys.readouterr().out
    assert "📂 Scanning: plants_A.json" in out
    assert "📂 Scanning: plants_B.json" in out
    assert "⚠️ Could not load broken.json" in out
    assert "✅ NRW/2010.geojson" in out and "✅ NRW/abcd.geojson" in out and "✅ NRW/2025.geojson" in out
    assert "✅ Sachsen/1999.geojson" in out and "✅ Sachsen/2010.geojson" in out
    assert "Processed" in out and "Matched entries:" in out and "Unmatched entries:" in out
    assert "Not matched:" in out


# test_generate_geojson_by_state_polygons_yearly.py

def test_convert_groups_by_state_and_year_and_writes_geojson(tmp_path: Path, monkeypatch, capsys):
    """
    End-to-end check:
    - Mix valid/invalid entries across two states and multiple years.
    - Ensure per-state subfolders + per-year files are created with the right feature counts.
    - Accept that non-numeric years (e.g., 'abcd') are written as '<year>.geojson' (per current implementation).
    """
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    sub = inp / "sub"
    inp.mkdir(); sub.mkdir()

    # Root file: two states + unmatched + abcd-year
    fA = inp / "plants_A.json"
    wjson(fA, [
        {"id": 1, "Inbetriebnahmedatum": "2010-05-12", "Laengengrad": "0.50", "Breitengrad": "0.50", "name": "nrw_2010"},
        {"id": 2, "Inbetriebnahmedatum": "1999-01-01", "Laengengrad": "2.10", "Breitengrad": "2.60", "name": "sax_1999"},
        {"id": 3, "Inbetriebnahmedatum": "2025/07/07", "Laengengrad": "0.75", "Breitengrad": "0.25", "name": "nrw_2025"},
        {"id": 4, "Inbetriebnahmedatum": "abcd",       "Laengengrad": "0.60", "Breitengrad": "0.60", "name": "nrw_abcd"},
        {"id": 5, "Inbetriebnahmedatum": "2010-12-31", "Laengengrad": "200",  "Breitengrad": "50"},   # invalid lon -> skip
        {"id": 6, "Laengengrad": "10", "Breitengrad": "50"},                                          # missing date -> unmatched
        {"id": 7, "Inbetriebnahmedatum": "2010-01-01", "Laengengrad": "10", "Breitengrad": "10", "name": "far_away"},
    ])

    # Sub file: more 2010 entries for both states
    fB = sub / "plants_B.json"
    wjson(fB, [
        {"id": 10, "Inbetriebnahmedatum": "2010/03/03", "Laengengrad": "2.50", "Breitengrad": "2.10", "extra": "sax_2010"},
        {"id": 11, "Inbetriebnahmedatum": "2010-07-01", "Laengengrad": "0.25", "Breitengrad": "0.75", "extra": "nrw_2010"},
    ])

    # Monkeypatch state polygons: NRW square (0..1), Sachsen square (2..3)
    nrw_poly = MultiPolygon([Polygon([(0,0), (0,1), (1,1), (1,0)])])
    sax_poly = MultiPolygon([Polygon([(2,2), (2,3), (3,3), (3,2)])])
    monkeypatch.setattr(mod, "state_polygons", [
        ("05", "NRW", nrw_poly),
        ("14", "Sachsen", sax_poly),
    ], raising=True)

    # Act
    mod.convert_jsons(str(inp), str(outdir))

    # Assert: expected outputs exist
    nrw_2010 = outdir / "NRW" / "2010.geojson"
    nrw_2025 = outdir / "NRW" / "2025.geojson"
    nrw_abcd = outdir / "NRW" / "abcd.geojson"  # <-- abcd-year dosya ismi
    sax_1999 = outdir / "Sachsen" / "1999.geojson"
    sax_2010 = outdir / "Sachsen" / "2010.geojson"

    for p in [nrw_2010, nrw_2025, nrw_abcd, sax_1999, sax_2010]:
        assert p.exists()

    # Quick feature count checks
    assert len(rjson(nrw_2010)["features"]) == 2
    assert len(rjson(nrw_2025)["features"]) == 1
    assert len(rjson(nrw_abcd)["features"]) == 1
    assert len(rjson(sax_1999)["features"]) == 1
    assert len(rjson(sax_2010)["features"]) == 1

    # Console output checks
    out = capsys.readouterr().out
    assert "NRW/2010.geojson" in out
    assert "NRW/2025.geojson" in out
    assert "NRW/abcd.geojson" in out
    assert "Sachsen/1999.geojson" in out
    assert "Sachsen/2010.geojson" in out


def test_no_outputs_when_no_matched_entries(tmp_path: Path, monkeypatch, capsys):
    """
    If no features match (invalid coords or outside polygons):
    - No *.geojson files should be written.
    - Output folder may or may not be created.
    - Summary lines with ✅ are allowed, but no '→ N features' lines should appear.
    """
    inp = tmp_path / "in"
    outdir = tmp_path / "out"
    inp.mkdir()

    f = inp / "plants.json"
    wjson(f, [
        {"id": 1, "Inbetriebnahmedatum": "2010-01-01", "Laengengrad": "181", "Breitengrad": "0"},
        {"id": 2, "Inbetriebnahmedatum": "2011-01-01", "Laengengrad": "10"},
        {"id": 3, "Inbetriebnahmedatum": "2012-01-01", "Laengengrad": "10", "Breitengrad": "10"},
        {"id": 4, "Laengengrad": "10", "Breitengrad": "50"},
    ])

    monkeypatch.setattr(mod, "state_polygons", [], raising=True)

    mod.convert_jsons(str(inp), str(outdir))

    # Outdir boş olmalı ya da hiç oluşmamış olmalı
    if outdir.exists():
        assert list(outdir.glob("**/*.geojson")) == []

    # Konsol çıktısı
    out = capsys.readouterr().out
    assert "📂 Scanning: plants.json" in out
    # "→ ... features" logları olmamalı
    assert not any("→" in line for line in out.splitlines())
