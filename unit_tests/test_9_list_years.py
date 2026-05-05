"""
Unit tests for step9_list_years.list_installation_years and extract_year().

Covers:
- listing installation years across multiple JSON files
- custom key usage
- ignoring non-json files
- handling invalid JSON files
- handling empty folders
- handling empty json lists
- handling mixed valid and invalid entries
- extract_year() correctness
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step9_list_years as list_years


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_list_installation_years_basic(tmp_path, capsys):
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"

    data1 = [
        {"Inbetriebnahmedatum": "2010-05-12"},
        {"Inbetriebnahmedatum": "1999-01-01"},
        {"Inbetriebnahmedatum": "2010/12/31"},
        {"Inbetriebnahmedatum": ""},
        {},
    ]
    data2 = [
        {"Inbetriebnahmedatum": "2025-07-07"},
        {"Inbetriebnahmedatum": "abcd"},
    ]

    write_json(file1, data1)
    write_json(file2, data2)
    file3.write_text("Ignore me", encoding="utf-8")

    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    assert "→ Scanning: ignore.txt" not in out
    assert "✔ Installation years found:" in out

    assert "1999: 1 entries" in out
    assert "2010: 2 entries" in out
    assert "2025: 1 entries" in out
    assert "abcd: 1 entries" in out


def test_list_installation_years_with_custom_key(tmp_path, capsys):
    file1 = tmp_path / "x.json"

    data = [
        {"custom_date": "2001-01-01"},
        {"custom_date": "2001-05-05"},
        {"custom_date": ""},
    ]

    write_json(file1, data)

    list_years.list_installation_years(str(tmp_path), key="custom_date")

    out = capsys.readouterr().out
    assert "→ Scanning: x.json" in out
    assert "2001: 2 entries" in out


def test_list_installation_years_handles_invalid_json(tmp_path, capsys):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json", encoding="utf-8")

    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: bad.json" in out
    assert "⚠️ Failed to process bad.json" in out


def test_list_installation_years_ignores_non_json_files(tmp_path, capsys):
    write_json(tmp_path / "data.json", [{"Inbetriebnahmedatum": "2011-01-01"}])
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"PNG")
    (tmp_path / "backup.json.bak").write_text("ignore", encoding="utf-8")

    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: data.json" in out
    assert "notes.txt" not in out
    assert "image.png" not in out
    assert "backup.json.bak" not in out

    assert "2011: 1 entries" in out


def test_list_installation_years_empty_folder(tmp_path, capsys):
    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "✔ Installation years found:" in out
    assert "entries" not in out.split("✔ Installation years found:")[-1]


def test_list_installation_years_handles_empty_json_list(tmp_path, capsys):
    write_json(tmp_path / "empty.json", [])

    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "→ Scanning: empty.json" in out
    assert "✔ Installation years found:" in out


def test_list_installation_years_handles_mixed_entries(tmp_path, capsys):
    write_json(
        tmp_path / "mixed.json",
        [
            {"Inbetriebnahmedatum": "2015-01-01"},
            {"Inbetriebnahmedatum": None},
            {"Inbetriebnahmedatum": ""},
            {},
            {"Inbetriebnahmedatum": "2015-12-12"},
        ],
    )

    list_years.list_installation_years(str(tmp_path))

    out = capsys.readouterr().out
    assert "2015: 2 entries" in out


def test_extract_year_function():
    assert list_years.extract_year("2020-05-01") == "2020"
    assert list_years.extract_year("abcd-05-01") == "abcd"
    assert list_years.extract_year("2010") == "2010"
    assert list_years.extract_year("") is None
    assert list_years.extract_year(None) is None