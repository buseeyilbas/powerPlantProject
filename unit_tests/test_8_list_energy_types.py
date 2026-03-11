"""
Unit tests for step8_list_energy_types.list_energy_codes.

Covers:
- listing and sorting unique Energietraeger codes
- handling custom JSON keys
- graceful skipping of invalid JSON files
- ignoring non-JSON files
- skipping empty or missing values
- handling mixed valid and invalid files
- handling empty folders
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step8_list_energy_types as list_energy_types


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_printed_values(output_text: str):
    lines = [line.strip() for line in output_text.splitlines()]
    return [
        line for line in lines
        if line and not line.startswith("→") and not line.startswith("⚠️") and not line.startswith("✔")
    ]


def test_list_energy_codes_basic(tmp_path, capsys):
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"

    data1 = [
        {"Energietraeger": "2495"},
        {"Energietraeger": "2497"},
        {"Energietraeger": "2495"},
        {"Energietraeger": ""},
        {},
    ]
    data2 = [
        {"Energietraeger": "2403"},
    ]

    write_json(file1, data1)
    write_json(file2, data2)
    file3.write_text("This should be ignored", encoding="utf-8")

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    assert "→ Scanning: ignore.txt" not in out
    assert "✔ Unique Energieträger codes found:" in out

    values = extract_printed_values(out)
    assert values == ["2403", "2495", "2497"]


def test_list_energy_codes_with_custom_key(tmp_path, capsys):
    file1 = tmp_path / "x.json"
    data = [
        {"energy_code": "AAA"},
        {"energy_code": "BBB"},
        {"energy_code": "AAA"},
        {"energy_code": ""},
        {},
    ]
    write_json(file1, data)

    list_energy_types.list_energy_codes(str(tmp_path), key="energy_code")

    out = capsys.readouterr().out
    assert "→ Scanning: x.json" in out

    values = extract_printed_values(out)
    assert values == ["AAA", "BBB"]


def test_list_energy_codes_handles_invalid_json(tmp_path, capsys):
    file1 = tmp_path / "bad.json"
    file1.write_text("{ not valid json", encoding="utf-8")

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: bad.json" in out
    assert "⚠️ Failed to process bad.json" in out
    assert extract_printed_values(out) == []


def test_list_energy_codes_ignores_non_json_files(tmp_path, capsys):
    write_json(tmp_path / "valid.json", [{"Energietraeger": "2495"}])
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"PNG")
    (tmp_path / "backup.json.bak").write_text("ignore", encoding="utf-8")

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: valid.json" in out
    assert "notes.txt" not in out
    assert "image.png" not in out
    assert "backup.json.bak" not in out

    values = extract_printed_values(out)
    assert values == ["2495"]


def test_list_energy_codes_skips_missing_and_empty_values(tmp_path, capsys):
    write_json(
        tmp_path / "data.json",
        [
            {"Energietraeger": ""},
            {"Energietraeger": None},
            {},
            {"Energietraeger": "2491"},
        ],
    )

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    values = extract_printed_values(out)
    assert values == ["2491"]


def test_list_energy_codes_sorts_unique_values_across_multiple_files(tmp_path, capsys):
    write_json(
        tmp_path / "file1.json",
        [
            {"Energietraeger": "2497"},
            {"Energietraeger": "2403"},
            {"Energietraeger": "2497"},
        ],
    )
    write_json(
        tmp_path / "file2.json",
        [
            {"Energietraeger": "2495"},
            {"Energietraeger": "2493"},
        ],
    )
    write_json(
        tmp_path / "file3.json",
        [
            {"Energietraeger": "2403"},
            {"Energietraeger": "2491"},
        ],
    )

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: file1.json" in out
    assert "→ Scanning: file2.json" in out
    assert "→ Scanning: file3.json" in out

    values = extract_printed_values(out)
    assert values == ["2403", "2491", "2493", "2495", "2497"]


def test_list_energy_codes_continues_after_invalid_file(tmp_path, capsys):
    write_json(tmp_path / "good.json", [{"Energietraeger": "2499"}])
    (tmp_path / "bad.json").write_text("{ invalid json", encoding="utf-8")

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: good.json" in out
    assert "→ Scanning: bad.json" in out
    assert "⚠️ Failed to process bad.json" in out

    values = extract_printed_values(out)
    assert values == ["2499"]


def test_list_energy_codes_empty_folder(tmp_path, capsys):
    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "✔ Unique Energieträger codes found:" in out
    assert extract_printed_values(out) == []


def test_list_energy_codes_handles_empty_json_list(tmp_path, capsys):
    write_json(tmp_path / "empty.json", [])

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: empty.json" in out
    assert "✔ Unique Energieträger codes found:" in out
    assert extract_printed_values(out) == []


def test_list_energy_codes_handles_non_dict_entries_as_failure(tmp_path, capsys):
    write_json(tmp_path / "mixed.json", ["text", 123, {"Energietraeger": "2495"}])

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: mixed.json" in out
    assert "⚠️ Failed to process mixed.json" in out
    assert extract_printed_values(out) == []