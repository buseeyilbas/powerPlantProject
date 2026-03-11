"""
Unit tests for step14_json_to_geojson_batch module
"""

import sys
from pathlib import Path
import json
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step14_json_to_geojson_batch as batch


def rjson(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_polygon_states(path: Path):
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


# ---------- parse_point ----------

@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.1"}, (10.5, 50.1)),
        ({"Laengengrad": "10,5", "Breitengrad": "50,1"}, (10.5, 50.1)),
        ({"Laengengrad": "200", "Breitengrad": "50"}, None),
        ({"Laengengrad": "10", "Breitengrad": "100"}, None),
        ({"Laengengrad": "abc", "Breitengrad": "50"}, None),
        ({"name": "no coords"}, None),
    ],
)
def test_parse_point(entry, expected):
    p = batch.parse_point(entry)

    if expected is None:
        assert p is None
    else:
        lon, lat = expected
        assert pytest.approx(p.x) == lon
        assert pytest.approx(p.y) == lat


# ---------- to_feature ----------

def test_to_feature_builds_geojson_feature():
    entry = {
        "Laengengrad": "10.0",
        "Breitengrad": "50.0",
        "id": 42,
        "name": "plant"
    }

    point = batch.parse_point(entry)
    feature = batch.to_feature(entry, point)

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [pytest.approx(10.0), pytest.approx(50.0)]

    props = feature["properties"]
    assert props["id"] == 42
    assert props["name"] == "plant"
    assert "Laengengrad" not in props
    assert "Breitengrad" not in props


# ---------- convert_all_germany_with_three_checks ----------

def test_convert_all_germany_basic(tmp_path, capsys):

    in_dir = tmp_path / "input"
    in_dir.mkdir()

    polygons = tmp_path / "polygons.json"
    _write_polygon_states(polygons)

    out_geojson = tmp_path / "out.geojson"
    summary_path = tmp_path / "summary.json"

    file1 = [
        {"Laengengrad": "10.2", "Breitengrad": "50.0", "id": 1,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},

        {"Laengengrad": "181", "Breitengrad": "50.0", "id": 2,
         "Bundesland": "1403", "Gemeindeschluessel": "09672121"},

        {"Laengengrad": "10.3", "Breitengrad": "50.2", "id": 3,
         "Bundesland": "1402", "Gemeindeschluessel": "08111000"},

        {"Laengengrad": "12.0", "Breitengrad": "52.0", "id": 4,
         "Bundesland": "1403", "Gemeindeschluessel": "09670000"},
    ]

    (in_dir / "file1.json").write_text(json.dumps(file1), encoding="utf-8")

    file2 = [
        {"Laengengrad": "10.4", "Breitengrad": "49.5", "id": 5,
         "Bundesland": "1403", "Gemeindeschluessel": "09670001"},
    ]

    (in_dir / "file2.json").write_text(json.dumps(file2), encoding="utf-8")

    (in_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    batch.convert_all_germany_with_three_checks(
        input_folder=str(in_dir),
        polygon_states_path=str(polygons),
        output_geojson=str(out_geojson),
        summary_path=str(summary_path),
    )

    assert out_geojson.exists()
    gj = rjson(out_geojson)

    assert gj["type"] == "FeatureCollection"

    ids = sorted([f["properties"]["id"] for f in gj["features"]])
    assert ids == [1, 5]

    summary = rjson(summary_path)

    assert summary["files_processed"] == 3
    assert summary["entries_seen"] == 5
    assert summary["consistent_written"] == 2
    assert summary["no_polygon_match"] == 1
    assert summary["bundesland_mismatch_count"] == 1
    assert summary["gemeindeschluessel_mismatch_count"] == 1
    assert summary["bundesland_missing_or_unmapped"] == 0
    assert summary["gemeindeschluessel_missing_or_unmapped"] == 0

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out
    assert "====== SUMMARY ======" in out
    assert "Created" in out


def test_convert_all_germany_empty_input(tmp_path, capsys):

    in_dir = tmp_path / "input"
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

    gj = rjson(out_geojson)
    assert gj["type"] == "FeatureCollection"
    assert gj["features"] == []

    summary = rjson(summary_path)
    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["consistent_written"] == 0

    out = capsys.readouterr().out
    assert "====== SUMMARY ======" in out
    assert "Created" in out


if __name__ == "__main__":
    pytest.main(["-v", __file__])