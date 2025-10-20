# test_17_generate_geojson_by_state_landkreis.py
"""
Tests aligned to step17_generate_geojson_by_state_landkreis.py actual API.

Covers:
- safe_filename: trims and replaces forbidden path chars with underscore (no lowercasing, umlauts preserved)
- parse_point: decimal/commas and invalid/out-of-range coords
- to_feature: builds a valid Feature (called only with a valid Point)
- convert_by_state_landkreis:
  * uses module-level GADM L2 path → monkeypatched to a tiny test polygon file
  * writes <OUTPUT>/<State>/<Landkreis>.geojson
  * writes _state_landkreis_summary.json
"""

import json
from pathlib import Path
from shapely.geometry import Point
import pytest

import step17_generate_geojson_by_state_landkreis as mod


# ---------- helpers ----------
def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_tiny_l2_polygons(path: Path):
    """
    Create a minimal Level-2 polygons GeoJSON with:
      - NAME_1 = 'Bayern', NAME_2 = 'Bad Kissingen'  (rect: lon[10.0,10.5], lat[50.0,50.5])
      - NAME_1 = 'Bayern', NAME_2 = 'Rhön-Grabfeld' (rect: lon[10.5,11.0], lat[50.0,50.5])
    """
    def rect(lon1, lat1, lon2, lat2):
        return [[
            [lon1, lat1],
            [lon2, lat1],
            [lon2, lat2],
            [lon1, lat2],
            [lon1, lat1],
        ]]

    poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME_1": "Bayern", "NAME_2": "Bad Kissingen"},
                "geometry": {"type": "Polygon", "coordinates": rect(10.0, 50.0, 10.5, 50.5)},
            },
            {
                "type": "Feature",
                "properties": {"NAME_1": "Bayern", "NAME_2": "Rhön-Grabfeld"},
                "geometry": {"type": "Polygon", "coordinates": rect(10.5, 50.0, 11.0, 50.5)},
            },
        ],
    }
    wjson(path, poly)


# ---------- unit tests: safe_filename ----------
@pytest.mark.parametrize(
    "input_name, expected_contains, forbidden_chars",
    [
        ("München-Stadt", "München-Stadt", ["/", "\\", ":", "*", "?", "\"", "<", ">", "|", "@"]),
        ("Baden-Württemberg/2025", "Baden-Württemberg_2025", ["/", "\\"]),
        ("Region@Name!", "Region_Name_", ["@", "!", "/", "\\"]),
        (" Thüringen ", "Thüringen", ["/", "\\"]),
    ],
)
def test_safe_filename_preserves_case_and_umlauts_but_sanitizes(input_name, expected_contains, forbidden_chars):
    safe = mod.safe_filename(input_name)
    # must contain the sanitized shape we expect (no lowercasing/transliteration)
    assert expected_contains in safe
    # must not contain forbidden path chars
    for ch in forbidden_chars:
        assert ch not in safe
    # never empty
    assert safe.strip() != ""


# ---------- unit tests: parse_point ----------
@pytest.mark.parametrize(
    "entry, valid",
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.0"}, True),
        ({"Laengengrad": "10,5", "Breitengrad": "50,0"}, True),
        ({"Laengengrad": "abc", "Breitengrad": "50"}, False),
        ({"Laengengrad": "10", "Breitengrad": "95"}, False),
        ({"Laengengrad": None, "Breitengrad": "50"}, False),
    ],
)
def test_parse_point_various(entry, valid):
    p = mod.parse_point(entry)
    if valid:
        assert isinstance(p, Point)
        assert -180 <= p.x <= 180 and -90 <= p.y <= 90
    else:
        assert p is None


# ---------- unit tests: to_feature (only with valid point) ----------
def test_to_feature_builds_geojson_and_keeps_properties():
    entry = {"Laengengrad": "10.1", "Breitengrad": "50.5", "Bundesland": "1403", "Landkreis": "Bad Kissingen", "id": 7}
    pt = Point(10.1, 50.5)  # valid point
    feat = mod.to_feature(entry, pt)

    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    coords = feat["geometry"]["coordinates"]
    assert coords[0] == pytest.approx(10.1) and coords[1] == pytest.approx(50.5)

    # coord fields should be removed from properties
    props = feat["properties"]
    assert props["Bundesland"] == "1403"
    assert props["Landkreis"] == "Bad Kissingen"
    assert props["id"] == 7
    assert "Laengengrad" not in props
    assert "Breitengrad" not in props


# ---------- integration: convert_by_state_landkreis ----------
def test_convert_by_state_landkreis_creates_per_landkreis_files(tmp_path, capsys, monkeypatch):
    # Arrange input & polygons
    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    in_dir.mkdir()
    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    # IMPORTANT: script reads the GADM path from a module-level constant; point it to our tiny file.
    for attr in ("GADM_L2_PATH", "GADM_L2_FILE", "POLYGON_FILE", "L2_POLYGON_FILE"):
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, str(gadm_path), raising=False)

    # Data: 2 valid (hit two polygons), 1 invalid coords (ignored), 1 valid but outside (unmatched)
    entries = [
        {"Laengengrad": "10.1", "Breitengrad": "50.1", "Bundesland": "1403", "Landkreis": "Bad Kissingen", "id": 1},
        {"Laengengrad": "10.6", "Breitengrad": "50.2", "Bundesland": "1403", "Landkreis": "Rhön-Grabfeld", "id": 2},
        {"Laengengrad": "200",  "Breitengrad": "95",   "Bundesland": "1403", "Landkreis": "Bad Kissingen", "id": 3},
        {"Laengengrad": "12.0", "Breitengrad": "52.0", "Bundesland": "1403", "Landkreis": "Bad Kissingen", "id": 4},
    ]
    wjson(in_dir / "plants.json", entries)

    # Act
    mod.convert_by_state_landkreis(str(in_dir), str(out_dir), gadm_l2_path=str(gadm_path))

    # Assert: state folder exists with per-landkreis files
    state_dir = out_dir / mod.safe_filename("Bayern")
    assert state_dir.exists()

    bk_name = mod.safe_filename("Bad Kissingen") + ".geojson"
    rg_name = mod.safe_filename("Rhön-Grabfeld") + ".geojson"
    bk_path = state_dir / bk_name
    rg_path = state_dir / rg_name

    assert bk_path.exists() and rg_path.exists()

    # Load and check features per landkreis
    bk = rjson(bk_path)
    rg = rjson(rg_path)
    assert bk["type"] == "FeatureCollection" and rg["type"] == "FeatureCollection"

    ids_bk = [f["properties"]["id"] for f in bk["features"]]
    ids_rg = [f["properties"]["id"] for f in rg["features"]]
    assert sorted(ids_bk) == [1]
    assert sorted(ids_rg) == [2]

    # Summary JSON
    summary = rjson(out_dir / "_state_landkreis_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 4
    assert summary["matched_entries"] == 2
    assert summary["unmatched_entries"] == 1  # only the valid-but-outside point
    assert summary["output_folder"] == str(out_dir)

    # Console logs
    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out
    assert "✅ Saved" in out


def test_convert_by_state_landkreis_handles_invalid_json(tmp_path, capsys, monkeypatch):
    # Arrange: invalid JSON but polygons still required for init
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    gadm_path = tmp_path / "gadm_l2.json"
    write_tiny_l2_polygons(gadm_path)

    # point module-level polygon path to our tiny file
    for attr in ("GADM_L2_PATH", "GADM_L2_FILE", "POLYGON_FILE", "L2_POLYGON_FILE"):
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, str(gadm_path), raising=False)

    # Act
    mod.convert_by_state_landkreis(str(in_dir), str(out_dir), gadm_l2_path=str(gadm_path))

    # Assert: warning printed, no .geojson files, summary with zeros
    out = capsys.readouterr().out
    assert "⚠️ Could not load bad.json" in out
    assert not list(out_dir.rglob("*.geojson"))

    summary = rjson(out_dir / "_state_landkreis_summary.json")
    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 0
    assert summary["matched_entries"] == 0
    assert summary["unmatched_entries"] == 0


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
