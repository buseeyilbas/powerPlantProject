# test_list_years.py

import json
from pathlib import Path
import pytest
import step9_list_years as mod


def test_list_installation_years_basic(tmp_path, capsys):
    # Arrange: create JSON files with various year formats
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"  # should be ignored

    data1 = [
        {"Inbetriebnahmedatum": "2010-05-12"},
        {"Inbetriebnahmedatum": "1999-01-01"},
        {"Inbetriebnahmedatum": "2010/12/31"},  # still gets year 2010
        {"Inbetriebnahmedatum": ""},  # ignored
        {}
    ]
    data2 = [
        {"Inbetriebnahmedatum": "2025-07-07"},
        {"Inbetriebnahmedatum": "abcd"}  # still takes 'abcd'[:4] = 'abcd'
    ]

    file1.write_text(json.dumps(data1), encoding="utf-8")
    file2.write_text(json.dumps(data2), encoding="utf-8")
    file3.write_text("Ignore me", encoding="utf-8")

    # Act
    mod.list_installation_years(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    assert "✔ Installation years found:" in out
    # Years should be sorted
    assert "1999: 1 entries" in out
    assert "2010: 2 entries" in out
    assert "2025: 1 entries" in out
    assert "abcd: 1 entries" in out


def test_list_installation_years_with_custom_key(tmp_path, capsys):
    # Arrange: file with a different date key
    file1 = tmp_path / "x.json"
    data = [
        {"custom_date": "2001-01-01"},
        {"custom_date": "2001-05-05"},
    ]
    file1.write_text(json.dumps(data), encoding="utf-8")

    # Act
    mod.list_installation_years(str(tmp_path), key="custom_date")

    # Assert
    out = capsys.readouterr().out
    assert "2001: 2 entries" in out


def test_list_installation_years_handles_invalid_json(tmp_path, capsys):
    # Arrange: bad JSON file
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json", encoding="utf-8")

    # Act
    mod.list_installation_years(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    assert "⚠️ Failed to process bad.json" in out


def test_extract_year_function():
    assert mod.extract_year("2020-05-01") == "2020"
    assert mod.extract_year("abcd-05-01") == "abcd"
    assert mod.extract_year("") is None
    assert mod.extract_year(None) is None
