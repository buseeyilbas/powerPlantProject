"""
Unit tests for step25_generate_geojson_by_landkreis.py
"""

import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step25_generate_geojson_by_landkreis as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    gadm_dir = tmp_path / "gadm"

    input_dir.mkdir()
    output_dir.mkdir()
    gadm_dir.mkdir()

    return {
        "root": tmp_path,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "gadm_dir": gadm_dir,
    }


@pytest.fixture
def sample_gadm_l2_geojson(temp_workspace):
    path = temp_workspace["gadm_dir"] / "gadm41_DEU_2.json"

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME_1": "Bayern", "NAME_2": "Landkreis A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.1, 49.1], [10.9, 49.1], [10.9, 50.9], [10.1, 50.9], [10.1, 49.1]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"NAME_1": "Thüringen", "NAME_2": "Landkreis B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[11.1, 50.1], [11.9, 50.1], [11.9, 50.9], [11.1, 50.9], [11.1, 50.1]]],
                },
            },
        ],
    }

    write_json(path, payload)
    return path


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"Laengengrad": "10.5", "Breitengrad": "50.0"}, (10.5, 50.0)),
        ({"Laengengrad": "10,5", "Breitengrad": "50,0"}, (10.5, 50.0)),
        ({"Laengengrad": "181", "Breitengrad": "50"}, None),
        ({"Laengengrad": "10", "Breitengrad": "91"}, None),
        ({}, None),
    ],
)
def test_parse_point(entry, expected):
    p = mod.parse_point(entry)

    if expected is None:
        assert p is None
    else:
        lon, lat = expected
        assert p.x == pytest.approx(lon)
        assert p.y == pytest.approx(lat)


def test_safe_filename():
    assert mod.safe_filename("Landkreis A") == "Landkreis A"
    assert mod.safe_filename("Landkreis/B") == "Landkreis_B"
    assert mod.safe_filename("A\\B") == "A_B"
    assert mod.safe_filename("") == "unknown"


def test_load_landkreis_polygons(sample_gadm_l2_geojson):
    polygons = mod.load_landkreis_polygons(str(sample_gadm_l2_geojson))

    assert len(polygons) == 2
    assert polygons[0][0] == "Landkreis A"
    assert polygons[0][1]["NAME_1"] == "Bayern"
    assert polygons[0][1]["NAME_2"] == "Landkreis A"
    assert isinstance(polygons[0][2], MultiPolygon)


def test_match_landkreis_via_prepared_geometries(sample_gadm_l2_geojson):
    landkreise = mod.load_landkreis_polygons(str(sample_gadm_l2_geojson))
    prepared = [(name_2, props, mod.prep(geom)) for (name_2, props, geom) in landkreise]

    def _match(point):
        for name_2, props, pgeom in prepared:
            if pgeom.covers(point) if hasattr(pgeom.context, "covers") else pgeom.contains(point):
                return name_2
        return None

    assert _match(Point(10.5, 50.0)) == "Landkreis A"
    assert _match(Point(11.5, 50.5)) == "Landkreis B"
    assert _match(Point(20, 60)) is None


def test_to_feature():
    entry = {
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
        "id": 1,
        "name": "plant",
    }

    point = mod.parse_point(entry)
    feature = mod.to_feature(entry, point)

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [pytest.approx(10.5), pytest.approx(50.0)]
    assert feature["properties"]["id"] == 1
    assert "Laengengrad" not in feature["properties"]
    assert "Breitengrad" not in feature["properties"]


def test_convert_by_landkreis_end_to_end(
    temp_workspace,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    entry_a = {
        "id": 1,
        "Laengengrad": "10.5",
        "Breitengrad": "50.0",
    }

    entry_b = {
        "id": 2,
        "Laengengrad": "11.5",
        "Breitengrad": "50.5",
    }

    invalid = {
        "id": 3,
        "Laengengrad": "181",
        "Breitengrad": "50",
    }

    outside = {
        "id": 4,
        "Laengengrad": "20",
        "Breitengrad": "60",
    }

    write_json(input_dir / "file1.json", [entry_a, entry_b, invalid, outside])

    mod.convert_by_landkreis(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    a_file = output_dir / "Landkreis A.geojson"
    b_file = output_dir / "Landkreis B.geojson"
    summary_file = output_dir / "_landkreis_summary.json"

    assert a_file.exists()
    assert b_file.exists()
    assert summary_file.exists()

    assert len(read_json(a_file)["features"]) == 1
    assert len(read_json(b_file)["features"]) == 1

    summary = read_json(summary_file)

    assert summary["files_processed"] == 1
    assert summary["entries_seen"] == 4
    assert summary["matched_entries"] == 2
    assert summary["unmatched_entries"] == 1
    assert summary["output_folder"] == str(output_dir)
    assert summary["gadm_l2_path"] == str(sample_gadm_l2_geojson)

    out = capsys.readouterr().out
    assert "Saved" in out
    assert "Landkreis A.geojson" in out
    assert "Landkreis B.geojson" in out
    assert "SUMMARY" in out


def test_convert_by_landkreis_handles_bad_json_and_continues(
    temp_workspace,
    sample_gadm_l2_geojson,
    capsys,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    write_json(
        input_dir / "good.json",
        [{"id": 1, "Laengengrad": "10.5", "Breitengrad": "50.0"}],
    )
    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    mod.convert_by_landkreis(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    assert (output_dir / "Landkreis A.geojson").exists()

    summary = read_json(output_dir / "_landkreis_summary.json")
    assert summary["files_processed"] == 2
    assert summary["entries_seen"] == 1
    assert summary["matched_entries"] == 1

    out = capsys.readouterr().out
    assert "Could not load bad.json" in out


def test_convert_by_landkreis_empty_input(
    temp_workspace,
    sample_gadm_l2_geojson,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    mod.convert_by_landkreis(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
        gadm_l2_path=str(sample_gadm_l2_geojson),
    )

    summary = read_json(output_dir / "_landkreis_summary.json")

    assert summary["files_processed"] == 0
    assert summary["entries_seen"] == 0
    assert summary["matched_entries"] == 0
    assert summary["unmatched_entries"] == 0


def test_convert_by_landkreis_raises_with_empty_l2(
    temp_workspace,
):
    input_dir = temp_workspace["input_dir"]
    output_dir = temp_workspace["output_dir"]

    empty = temp_workspace["root"] / "empty.json"
    write_json(empty, {"type": "FeatureCollection", "features": []})

    with pytest.raises(RuntimeError, match="No Landkreis polygons loaded"):
        mod.convert_by_landkreis(
            input_folder=str(input_dir),
            output_folder=str(output_dir),
            gadm_l2_path=str(empty),
        )