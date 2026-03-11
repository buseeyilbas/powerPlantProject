"""
Unit tests for step10_filter_json_by_energy_code.filter_by_energy_codes

Covers:
- creation of output base folder and per-code subfolders
- correct filtering and writing of JSON files
- ignoring non-JSON files
- handling corrupted JSON gracefully
- behavior when no entries match any code
- custom energy_key support
- multiple input files and multiple energy codes
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step10_filter_json_by_energy_code as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_creates_folders_and_writes_filtered_files(tmp_path, capsys):
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

    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", codes)

    pv_dir = output_base / "2495"
    wind_dir = output_base / "2497"

    assert output_base.exists()
    assert pv_dir.exists()
    assert wind_dir.exists()

    out_pv_1 = pv_dir / "plants_1.json"
    out_wind_1 = wind_dir / "plants_1.json"
    out_pv_2 = pv_dir / "plants_2.json"

    assert out_pv_1.exists()
    assert out_wind_1.exists()
    assert out_pv_2.exists()

    assert read_json(out_pv_1) == [{"id": 1, "Energietraeger": "2495", "name": "PV A"}]
    assert read_json(out_wind_1) == [{"id": 2, "Energietraeger": "2497", "name": "Wind A"}]
    assert read_json(out_pv_2) == [
        {"id": 10, "Energietraeger": "2495", "name": "PV B"},
        {"id": 11, "Energietraeger": "2495", "name": "PV C"},
    ]

    out = capsys.readouterr().out
    assert "Processing: plants_1.json" in out
    assert "Processing: plants_2.json" in out
    assert "✔ Saved" in out


def test_ignores_non_json_and_handles_multiple_files(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "README.txt").write_text("ignore me", encoding="utf-8")
    (input_dir / "data.json.bak").write_text("ignore me", encoding="utf-8")

    file_json = input_dir / "plants.json"
    write_json(file_json, [{"code": "A", "Energietraeger": "2403"}])

    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2403", "2405"])

    a_dir = output_base / "2403"
    b_dir = output_base / "2405"

    assert a_dir.exists()
    assert b_dir.exists()
    assert (a_dir / "plants.json").exists()
    assert list(b_dir.glob("*.json")) == []


def test_bad_json_is_reported_and_other_files_continue(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    bad = input_dir / "broken.json"
    bad.write_bytes(b"{not valid json")

    good = input_dir / "good.json"
    write_json(good, [{"Energietraeger": "2498", "id": 99}])

    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2498"])

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out

    out_dir = output_base / "2498"
    assert (out_dir / "good.json").exists()
    assert not (out_dir / "broken.json").exists()


def test_no_output_file_when_no_matching_entries(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    file1 = input_dir / "plants.json"
    write_json(
        file1,
        [
            {"Energietraeger": "XXXX", "id": 1},
            {"Energietraeger": "YYYY", "id": 2},
        ],
    )

    mod.filter_by_energy_codes(str(input_dir), str(output_base), "Energietraeger", ["2406"])

    code_dir = output_base / "2406"
    assert code_dir.exists()
    assert list(code_dir.glob("*.json")) == []

    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out


def test_custom_energy_key_supported(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    file1 = input_dir / "alt_key.json"
    write_json(
        file1,
        [
            {"energy_code": "2957", "id": 1},
            {"energy_code": "2958", "id": 2},
        ],
    )

    mod.filter_by_energy_codes(str(input_dir), str(output_base), "energy_code", ["2957"])

    code_dir = output_base / "2957"
    assert code_dir.exists()

    out_file = code_dir / "alt_key.json"
    assert out_file.exists()
    assert read_json(out_file) == [{"energy_code": "2957", "id": 1}]


def test_multiple_files_multiple_codes(tmp_path):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    write_json(
        input_dir / "file1.json",
        [
            {"Energietraeger": "2495", "id": 1},
            {"Energietraeger": "2497", "id": 2},
        ],
    )

    write_json(
        input_dir / "file2.json",
        [
            {"Energietraeger": "2497", "id": 3},
            {"Energietraeger": "2498", "id": 4},
        ],
    )

    mod.filter_by_energy_codes(
        str(input_dir),
        str(output_base),
        "Energietraeger",
        ["2495", "2497", "2498"],
    )

    assert (output_base / "2495" / "file1.json").exists()
    assert (output_base / "2497" / "file1.json").exists()
    assert (output_base / "2497" / "file2.json").exists()
    assert (output_base / "2498" / "file2.json").exists()