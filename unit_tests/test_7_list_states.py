"""
Unit tests for step7_list_states.list_state_codes.

Covers:
- basic listing and deduplication of Bundesland codes
- handling invalid JSON files
- behavior with empty folder
- ignoring non-JSON files
- skipping empty or missing Bundesland values
- handling multiple files with mixed content
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step7_list_states as list_states


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_printed_codes(output_text: str):
    return [line.strip() for line in output_text.splitlines() if line.strip().isdigit()]


def test_list_state_codes_basic(tmp_path, capsys):
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"

    data1 = [
        {"Bundesland": "05"},
        {"Bundesland": "14"},
        {"Bundesland": "05"},
        {"Bundesland": ""},
        {},
    ]
    data2 = [
        {"Bundesland": "09"},
    ]

    write_json(file1, data1)
    write_json(file2, data2)
    file3.write_text("Ignore me", encoding="utf-8")

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    assert "→ Scanning: ignore.txt" not in out
    assert "✔ Unique Bundesland codes found:" in out

    codes_listed = extract_printed_codes(out)
    assert codes_listed == ["05", "09", "14"]


def test_list_state_codes_handles_invalid_json(tmp_path, capsys):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json", encoding="utf-8")

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: bad.json" in out
    assert "⚠️ Failed to process bad.json" in out
    assert extract_printed_codes(out) == []


def test_list_state_codes_empty_folder(tmp_path, capsys):
    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "✔ Unique Bundesland codes found:" in out
    assert extract_printed_codes(out) == []


def test_list_state_codes_ignores_non_json_files(tmp_path, capsys):
    write_json(tmp_path / "valid.json", [{"Bundesland": "11"}])
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"PNG")
    (tmp_path / "backup.json.bak").write_text("ignore", encoding="utf-8")

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: valid.json" in out
    assert "notes.txt" not in out
    assert "image.png" not in out
    assert "backup.json.bak" not in out

    codes_listed = extract_printed_codes(out)
    assert codes_listed == ["11"]


def test_list_state_codes_skips_missing_and_empty_codes(tmp_path, capsys):
    write_json(
        tmp_path / "data.json",
        [
            {"Bundesland": ""},
            {"Bundesland": None},
            {},
            {"Bundesland": "08"},
        ],
    )

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    codes_listed = extract_printed_codes(out)
    assert codes_listed == ["08"]


def test_list_state_codes_sorts_unique_codes_across_multiple_files(tmp_path, capsys):
    write_json(
        tmp_path / "file1.json",
        [
            {"Bundesland": "14"},
            {"Bundesland": "03"},
            {"Bundesland": "14"},
        ],
    )
    write_json(
        tmp_path / "file2.json",
        [
            {"Bundesland": "09"},
            {"Bundesland": "01"},
        ],
    )
    write_json(
        tmp_path / "file3.json",
        [
            {"Bundesland": "05"},
            {"Bundesland": "03"},
        ],
    )

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: file1.json" in out
    assert "→ Scanning: file2.json" in out
    assert "→ Scanning: file3.json" in out

    codes_listed = extract_printed_codes(out)
    assert codes_listed == ["01", "03", "05", "09", "14"]


def test_list_state_codes_continues_after_invalid_file(tmp_path, capsys):
    write_json(tmp_path / "good.json", [{"Bundesland": "12"}])
    (tmp_path / "bad.json").write_text("{ invalid json", encoding="utf-8")

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: good.json" in out
    assert "→ Scanning: bad.json" in out
    assert "⚠️ Failed to process bad.json" in out

    codes_listed = extract_printed_codes(out)
    assert codes_listed == ["12"]


def test_list_state_codes_handles_empty_json_list(tmp_path, capsys):
    write_json(tmp_path / "empty.json", [])

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: empty.json" in out
    assert "✔ Unique Bundesland codes found:" in out
    assert extract_printed_codes(out) == []


def test_list_state_codes_handles_non_dict_entries_as_failure(tmp_path, capsys):
    write_json(tmp_path / "mixed.json", ["text", 123, {"Bundesland": "07"}])

    list_states.list_state_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: mixed.json" in out
    assert "⚠️ Failed to process mixed.json" in out
    assert extract_printed_codes(out) == []