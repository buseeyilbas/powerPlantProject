# test_filter_json_by_energy_code.py
"""
Unit tests for filter_json_by_energy_code.filter_by_energy_codes

Covers:
1) Creation of output base folder and per-code subfolders.
2) Writing filtered files with correct content and filename.
3) Ignoring non-.json files.
4) Handling of bad/corrupted JSON gracefully (prints a warning, continues).
5) No output file creation when no entries match any code.
6) Using a custom energy_key works (not just 'Energietraeger').
"""

import json
from pathlib import Path

import pytest

import step10_filter_json_by_energy_code as mod  # module under test


def write_json(path: Path, data) -> None:
    """Helper: write JSON bytes for test inputs."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    """Helper: read JSON back for assertions."""
    return json.loads(path.read_text(encoding="utf-8"))


# Test that creates output folders and writes filtered files
def test_creates_folders_and_writes_filtered_files(tmp_path: Path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    file1 = input_dir / "plants_1.json"
    data1 = [
        {"id": 1, "Energietraeger": "2495", "name": "PV A"},
        {"id": 2, "Energietraeger": "2497", "name": "Wind A"},
        {"id": 3, "Energietraeger": "XXXX", "name": "Other"},
    ]
    write_json(file1, data1)

    file2 = input_dir / "plants_2.json"
    data2 = [
        {"id": 10, "Energietraeger": "2495", "name": "PV B"},
        {"id": 11, "Energietraeger": "2495", "name": "PV C"},
    ]
    write_json(file2, data2)

    codes = ["2495", "2497"]

    # Act
    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", codes)

    # Assert: output base and per-code dirs exist
    pv_dir = output_base / "2495"
    wind_dir = output_base / "2497"
    assert output_base.exists() and pv_dir.exists() and wind_dir.exists()

    # Assert: files created with the SAME names under each matching code folder
    out_pv_1 = pv_dir / "plants_1.json"
    out_wind_1 = wind_dir / "plants_1.json"
    out_pv_2 = pv_dir / "plants_2.json"
    assert out_pv_1.exists() and out_wind_1.exists() and out_pv_2.exists()

    # Assert: contents are filtered correctly
    assert read_json(out_pv_1) == [{"id": 1, "Energietraeger": "2495", "name": "PV A"}]
    assert read_json(out_wind_1) == [{"id": 2, "Energietraeger": "2497", "name": "Wind A"}]
    assert read_json(out_pv_2) == [
        {"id": 10, "Energietraeger": "2495", "name": "PV B"},
        {"id": 11, "Energietraeger": "2495", "name": "PV C"},
    ]

    # Assert: console output contains progress lines
    out = capsys.readouterr().out
    assert "Processing: plants_1.json" in out and "Processing: plants_2.json" in out
    assert "✔ Saved" in out



# Test that ignores non-JSON files and handles multiple files
def test_ignores_non_json_and_handles_multiple_files(tmp_path: Path):
    # Arrange
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    # Non-JSON files should be ignored
    (input_dir / "README.txt").write_text("ignore me", encoding="utf-8")
    (input_dir / "data.json.bak").write_text("ignore me", encoding="utf-8")

    # Valid JSON
    file_json = input_dir / "plants.json"
    write_json(file_json, [{"code": "A", "Energietraeger": "2403"}])

    # Act
    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2403", "2405"])

    # Assert: only plants.json processed; only 2403 folder gets a file
    a_dir = output_base / "2403"
    b_dir = output_base / "2405"
    assert a_dir.exists() and b_dir.exists()
    assert (a_dir / "plants.json").exists()
    assert list(b_dir.glob("*.json")) == []  # no match for 2405



# Test that handles bad/corrupted JSON files gracefully
def test_bad_json_is_reported_and_other_files_continue(tmp_path: Path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    bad = input_dir / "broken.json"
    bad.write_bytes(b"{not valid json")  # will raise JSONDecodeError

    good = input_dir / "good.json"
    write_json(good, [{"Energietraeger": "2498", "id": 99}])

    # Act
    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2498"])

    # Assert: good file processed, bad file reported
    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out

    out_dir = output_base / "2498"
    assert (out_dir / "good.json").exists()
    assert not (out_dir / "broken.json").exists()


# Test that no output file is created when no entries match any code
def test_no_output_file_when_no_matching_entries(tmp_path: Path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    file1 = input_dir / "plants.json"
    write_json(file1, [
        {"Energietraeger": "XXXX", "id": 1},
        {"Energietraeger": "YYYY", "id": 2},
    ])

    # Act
    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2406"])

    # Assert: per-code folder is created, but no file is written
    code_dir = output_base / "2406"
    assert code_dir.exists()
    assert list(code_dir.glob("*.json")) == []

    # Message should not claim "Saved" for this file/code
    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out


# Test that supports a custom energy key instead of 'Energietraeger'
def test_custom_energy_key_supported(tmp_path: Path):
    # Arrange
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    # Use a different key name instead of 'Energietraeger'
    file1 = input_dir / "alt_key.json"
    write_json(file1, [
        {"energy_code": "2957", "id": 1},
        {"energy_code": "2958", "id": 2},
    ])

    # Act
    mod.filter_by_energy_codes(str(input_dir), str(output_base), "energy_code", ["2957"])

    # Assert
    code_dir = output_base / "2957"
    assert code_dir.exists()
    out_file = code_dir / "alt_key.json"
    assert out_file.exists()
    assert read_json(out_file) == [{"energy_code": "2957", "id": 1}]
