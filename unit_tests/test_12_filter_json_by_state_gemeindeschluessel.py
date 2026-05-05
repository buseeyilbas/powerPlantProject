"""
Unit tests for step12_filter_json_by_state_gemeindeschluessel.py

Covers:
- extract_state_prefix() happy paths and edge cases
- base output folder creation
- per-prefix folder creation only when matches exist
- correct filtering and writing of JSON files
- preserving original filenames
- ignoring non-JSON files
- handling corrupted JSON gracefully while continuing
- behavior when no valid prefixes exist
- handling multiple files and multiple prefixes
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step12_filter_json_by_state_gemeindeschluessel as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("05170048", "05"),
        ("14060000", "14"),
        ("99", "99"),
        ("9", None),
        ("", None),
        (None, None),
        (123456, None),
        ("XX123", "XX"),
        (" 5A170048", " 5"),
    ],
)
def test_extract_state_prefix_cases(value, expected):
    assert mod.extract_state_prefix(value) == expected


def test_creates_base_folder_and_writes_per_prefix_files(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "plants_A.json",
        [
            {"id": 1, "Gemeindeschluessel": "05170048", "name": "Entry A"},
            {"id": 2, "Gemeindeschluessel": "14150000", "name": "Entry B"},
            {"id": 3, "Gemeindeschluessel": "XX000000", "name": "Entry C"},
            {"id": 4, "Gemeindeschluessel": None, "name": "Ignored"},
        ],
    )

    write_json(
        input_dir / "plants_B.json",
        [
            {"id": 10, "Gemeindeschluessel": "05179999", "name": "Entry D"},
            {"id": 11, "Gemeindeschluessel": "14150001", "name": "Entry E"},
            {"id": 12, "name": "MissingKey"},
        ],
    )

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert output_base.exists()
    assert output_base.is_dir()

    d05 = output_base / "05"
    d14 = output_base / "14"
    dxx = output_base / "XX"

    assert d05.exists()
    assert d14.exists()
    assert dxx.exists()

    out_05_a = d05 / "plants_A.json"
    out_05_b = d05 / "plants_B.json"
    out_14_a = d14 / "plants_A.json"
    out_14_b = d14 / "plants_B.json"
    out_xx_a = dxx / "plants_A.json"

    assert out_05_a.exists()
    assert out_05_b.exists()
    assert out_14_a.exists()
    assert out_14_b.exists()
    assert out_xx_a.exists()

    assert read_json(out_05_a) == [{"id": 1, "Gemeindeschluessel": "05170048", "name": "Entry A"}]
    assert read_json(out_05_b) == [{"id": 10, "Gemeindeschluessel": "05179999", "name": "Entry D"}]
    assert read_json(out_14_a) == [{"id": 2, "Gemeindeschluessel": "14150000", "name": "Entry B"}]
    assert read_json(out_14_b) == [{"id": 11, "Gemeindeschluessel": "14150001", "name": "Entry E"}]
    assert read_json(out_xx_a) == [{"id": 3, "Gemeindeschluessel": "XX000000", "name": "Entry C"}]

    out = capsys.readouterr().out
    assert "Processing: plants_A.json" in out
    assert "Processing: plants_B.json" in out
    assert "✔ Saved" in out


def test_ignores_non_json_and_reports_bad_json(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "plants.json.bak").write_text("ignore", encoding="utf-8")
    (input_dir / "image.png").write_bytes(b"PNG")

    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ invalid json")

    good = input_dir / "ok.json"
    write_json(good, [{"Gemeindeschluessel": "0517xxxx", "id": 42}])

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert (output_base / "05" / "ok.json").exists()
    assert not (output_base / "05" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert "notes.txt" not in out
    assert "plants.json.bak" not in out
    assert "image.png" not in out


def test_no_prefix_dirs_when_no_valid_prefixes(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "plants.json",
        [
            {"Gemeindeschluessel": None, "id": 1},
            {"Gemeindeschluessel": "", "id": 2},
            {"Gemeindeschluessel": "9", "id": 3},
            {"id": 4},
        ],
    )

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert output_base.exists()
    assert output_base.is_dir()
    assert list(output_base.iterdir()) == []

    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out


def test_multiple_files_multiple_prefixes(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "file1.json",
        [
            {"Gemeindeschluessel": "05170001", "id": 1},
            {"Gemeindeschluessel": "14150001", "id": 2},
            {"Gemeindeschluessel": "03123456", "id": 3},
        ],
    )

    write_json(
        input_dir / "file2.json",
        [
            {"Gemeindeschluessel": "14150002", "id": 4},
            {"Gemeindeschluessel": "14150003", "id": 5},
            {"Gemeindeschluessel": "05179999", "id": 6},
        ],
    )

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert (output_base / "05" / "file1.json").exists()
    assert (output_base / "14" / "file1.json").exists()
    assert (output_base / "03" / "file1.json").exists()
    assert (output_base / "14" / "file2.json").exists()
    assert (output_base / "05" / "file2.json").exists()

    assert read_json(output_base / "05" / "file1.json") == [{"Gemeindeschluessel": "05170001", "id": 1}]
    assert read_json(output_base / "14" / "file1.json") == [{"Gemeindeschluessel": "14150001", "id": 2}]
    assert read_json(output_base / "03" / "file1.json") == [{"Gemeindeschluessel": "03123456", "id": 3}]
    assert read_json(output_base / "14" / "file2.json") == [
        {"Gemeindeschluessel": "14150002", "id": 4},
        {"Gemeindeschluessel": "14150003", "id": 5},
    ]
    assert read_json(output_base / "05" / "file2.json") == [{"Gemeindeschluessel": "05179999", "id": 6}]

    out = capsys.readouterr().out
    assert "Processing: file1.json" in out
    assert "Processing: file2.json" in out


def test_creates_output_base_folder_when_missing(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(input_dir / "plants.json", [{"Gemeindeschluessel": "14150001", "id": 1}])

    assert not output_base.exists()

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert output_base.exists()
    assert (output_base / "14").exists()
    assert (output_base / "14" / "plants.json").exists()


def test_empty_input_folder_creates_only_base_folder(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    assert output_base.exists()
    assert output_base.is_dir()
    assert list(output_base.iterdir()) == []


def test_preserves_entries_with_same_prefix_in_single_output_file(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "plants.json",
        [
            {"Gemeindeschluessel": "14150001", "id": 1},
            {"Gemeindeschluessel": "14150002", "id": 2},
            {"Gemeindeschluessel": "14150003", "id": 3},
        ],
    )

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    out_file = output_base / "14" / "plants.json"
    assert out_file.exists()
    assert read_json(out_file) == [
        {"Gemeindeschluessel": "14150001", "id": 1},
        {"Gemeindeschluessel": "14150002", "id": 2},
        {"Gemeindeschluessel": "14150003", "id": 3},
    ]