# test_json_to_geojson_batch.py

import json
from pathlib import Path
import io
import builtins
import types
import pytest

import json_to_geojson_batch as mod


def rjson(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Tests for create_feature ----------

def test_create_feature_valid_and_invalid_cases():
    # Valid coordinates
    entry_valid = {"Laengengrad": "10.5", "Breitengrad": "50.1", "name": "plant1"}
    feat = mod.create_feature(entry_valid)
    assert feat["geometry"]["coordinates"] == [10.5, 50.1]
    assert feat["properties"]["name"] == "plant1"

    # Valid but with comma decimal
    entry_comma = {"Laengengrad": "10,5", "Breitengrad": "50,1"}
    feat = mod.create_feature(entry_comma)
    assert feat["geometry"]["coordinates"] == [10.5, 50.1]

    # Invalid: lat out of range
    entry_bad_lat = {"Laengengrad": "10", "Breitengrad": "100"}
    assert mod.create_feature(entry_bad_lat) is None

    # Invalid: lon out of range
    entry_bad_lon = {"Laengengrad": "200", "Breitengrad": "50"}
    assert mod.create_feature(entry_bad_lon) is None

    # Invalid: non-numeric
    entry_non_numeric = {"Laengengrad": "abc", "Breitengrad": "50"}
    assert mod.create_feature(entry_non_numeric) is None

    # Invalid: missing keys
    entry_missing = {"name": "no coords"}
    assert mod.create_feature(entry_missing) is None


# ---------- Tests for convert_all_json_to_geojson ----------

def test_convert_all_json_to_geojson_basic(tmp_path: Path, capsys):
    # Arrange: create two valid JSON files and one invalid
    in_dir = tmp_path / "input"
    in_dir.mkdir()

    data1 = [
        {"Laengengrad": "10.0", "Breitengrad": "50.0", "id": 1},
        {"Laengengrad": "181", "Breitengrad": "50.0", "id": 2},  # invalid lon
    ]
    data2 = [
        {"Laengengrad": "20.0", "Breitengrad": "40.0", "id": 3}
    ]

    (in_dir / "file1.json").write_text(json.dumps(data1), encoding="utf-8")
    (in_dir / "file2.json").write_text(json.dumps(data2), encoding="utf-8")
    (in_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")

    out_geojson = tmp_path / "output.geojson"

    # Act
    mod.convert_all_json_to_geojson(str(in_dir), str(out_geojson))

    # Assert output file exists
    assert out_geojson.exists()
    content = rjson(out_geojson)
    assert content["type"] == "FeatureCollection"
    # Only 2 valid features (id 1 and id 3)
    ids = [f["properties"]["id"] for f in content["features"]]
    assert sorted(ids) == [1, 3]

    # Assert console output mentions scanning files and creation
    out = capsys.readouterr().out
    assert "📂 Scanning: file1.json" in out
    assert "📂 Scanning: file2.json" in out
    assert "⚠️ Could not load bad.json" in out
    assert "✅ Created" in out
    assert "Total 2 features" in out


def test_convert_all_json_to_geojson_empty_folder(tmp_path: Path, capsys):
    in_dir = tmp_path / "input"
    in_dir.mkdir()
    out_geojson = tmp_path / "output.geojson"

    mod.convert_all_json_to_geojson(str(in_dir), str(out_geojson))

    # Output should exist but have empty features
    content = rjson(out_geojson)
    assert content["features"] == []

    out = capsys.readouterr().out
    assert "Processed 0 JSON files" in out
