"""
Unit tests for step11_filter_json_by_state_bundesland.filter_by_state_codes

Covers:
- creating output base folder and per-code subfolders
- writing correctly filtered files with original filenames
- ignoring non-JSON files
- handling corrupted JSON gracefully while continuing
- creating no output files when there are no matches
- supporting a custom state key
- precreating all target subfolders
- handling multiple files and multiple matching codes
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step11_filter_json_by_state_bundesland as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_creates_dirs_and_writes_filtered_files(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "plants_1.json",
        [
            {"id": 1, "Bundesland": "1409", "name": "Entry A"},
            {"id": 2, "Bundesland": "1415", "name": "Entry B"},
            {"id": 3, "Bundesland": "XXXX", "name": "Other"},
        ],
    )
    write_json(
        input_dir / "plants_2.json",
        [
            {"id": 10, "Bundesland": "1409", "name": "Entry C"},
            {"id": 11, "Bundesland": "1409", "name": "Entry D"},
        ],
    )

    codes = ["1409", "1415"]

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    d1409 = out_base / "1409"
    d1415 = out_base / "1415"

    assert out_base.exists()
    assert d1409.exists()
    assert d1415.exists()

    out_1409_1 = d1409 / "plants_1.json"
    out_1415_1 = d1415 / "plants_1.json"
    out_1409_2 = d1409 / "plants_2.json"

    assert out_1409_1.exists()
    assert out_1415_1.exists()
    assert out_1409_2.exists()

    assert read_json(out_1409_1) == [{"id": 1, "Bundesland": "1409", "name": "Entry A"}]
    assert read_json(out_1415_1) == [{"id": 2, "Bundesland": "1415", "name": "Entry B"}]
    assert read_json(out_1409_2) == [
        {"id": 10, "Bundesland": "1409", "name": "Entry C"},
        {"id": 11, "Bundesland": "1409", "name": "Entry D"},
    ]

    out = capsys.readouterr().out
    assert "Processing: plants_1.json" in out
    assert "Processing: plants_2.json" in out
    assert "✔ Saved" in out


def test_ignores_non_json_and_reports_bad_json(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "readme.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "plants.json.bak").write_text("ignore", encoding="utf-8")
    (input_dir / "image.png").write_bytes(b"PNG")

    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ not valid json")

    good = input_dir / "ok.json"
    write_json(good, [{"Bundesland": "1410", "id": 99}])

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", ["1409", "1410"])

    assert (out_base / "1410" / "ok.json").exists()
    assert not (out_base / "1410" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert "✔ Saved" in out
    assert "readme.txt" not in out
    assert "plants.json.bak" not in out
    assert "image.png" not in out


def test_no_output_files_when_no_matches(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "plants.json",
        [
            {"Bundesland": "9999", "id": 1},
            {"Bundesland": "8888", "id": 2},
        ],
    )

    codes = ["1400", "1401"]

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    for code in codes:
        code_dir = out_base / code
        assert code_dir.exists()
        assert list(code_dir.glob("*.json")) == []

    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out


def test_supports_custom_state_key(tmp_path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "alt_key.json",
        [
            {"state_code": "1414", "id": 1},
            {"state_code": "1415", "id": 2},
            {"state_code": "xxxx", "id": 3},
        ],
    )

    mod.filter_by_state_codes(str(input_dir), str(out_base), "state_code", ["1415"])

    out_file = out_base / "1415" / "alt_key.json"
    assert out_file.exists()
    assert read_json(out_file) == [{"state_code": "1415", "id": 2}]


def test_precreates_all_target_subfolders_even_before_processing(tmp_path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    codes = ["1408", "1409", "1410"]

    write_json(input_dir / "plants.json", [{"Bundesland": "1409", "id": 1}])

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    for code in codes:
        assert (out_base / code).exists()

    assert (out_base / "1409" / "plants.json").exists()
    assert list((out_base / "1408").glob("*.json")) == []
    assert list((out_base / "1410").glob("*.json")) == []


def test_multiple_files_multiple_codes(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "file1.json",
        [
            {"Bundesland": "1409", "id": 1},
            {"Bundesland": "1410", "id": 2},
            {"Bundesland": "1411", "id": 3},
        ],
    )
    write_json(
        input_dir / "file2.json",
        [
            {"Bundesland": "1410", "id": 4},
            {"Bundesland": "1410", "id": 5},
            {"Bundesland": "1412", "id": 6},
        ],
    )

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", ["1409", "1410", "1412"])

    assert (out_base / "1409" / "file1.json").exists()
    assert (out_base / "1410" / "file1.json").exists()
    assert (out_base / "1410" / "file2.json").exists()
    assert (out_base / "1412" / "file2.json").exists()

    assert read_json(out_base / "1409" / "file1.json") == [{"Bundesland": "1409", "id": 1}]
    assert read_json(out_base / "1410" / "file1.json") == [{"Bundesland": "1410", "id": 2}]
    assert read_json(out_base / "1410" / "file2.json") == [
        {"Bundesland": "1410", "id": 4},
        {"Bundesland": "1410", "id": 5},
    ]
    assert read_json(out_base / "1412" / "file2.json") == [{"Bundesland": "1412", "id": 6}]

    out = capsys.readouterr().out
    assert "Processing: file1.json" in out
    assert "Processing: file2.json" in out


def test_creates_output_base_folder_when_missing(tmp_path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(input_dir / "plants.json", [{"Bundesland": "1415", "id": 1}])

    assert not out_base.exists()

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", ["1415"])

    assert out_base.exists()
    assert (out_base / "1415").exists()
    assert (out_base / "1415" / "plants.json").exists()


def test_empty_input_folder_still_precreates_target_dirs(tmp_path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    codes = ["1401", "1402"]

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    assert out_base.exists()
    assert (out_base / "1401").exists()
    assert (out_base / "1402").exists()
    assert list((out_base / "1401").glob("*.json")) == []
    assert list((out_base / "1402").glob("*.json")) == []