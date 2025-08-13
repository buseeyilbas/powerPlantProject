# test_list_energy_types.py

import json
from pathlib import Path
import builtins
import io
import pytest

import list_energy_types as mod


def test_list_energy_codes_basic(tmp_path, capsys):
    # Arrange: create valid JSON files
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"  # should be ignored

    data1 = [
        {"Energietraeger": "2495"},
        {"Energietraeger": "2497"},
        {"Energietraeger": "2495"},  # duplicate
        {"Energietraeger": ""},      # empty ignored
        {}
    ]
    data2 = [
        {"Energietraeger": "2403"}
    ]

    file1.write_text(json.dumps(data1), encoding="utf-8")
    file2.write_text(json.dumps(data2), encoding="utf-8")
    file3.write_text("This should be ignored", encoding="utf-8")

    # Act
    mod.list_energy_codes(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    # All .json files scanned
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    # Codes should appear sorted
    lines = [line.strip() for line in out.splitlines()]
    codes_listed = [line for line in lines if line.isdigit()]
    assert codes_listed == sorted(["2495", "2497", "2403"])
    # Intro message present
    assert "✔ Unique Energieträger codes found:" in out


def test_list_energy_codes_with_custom_key(tmp_path, capsys):
    # Arrange: file with a custom key instead of Energietraeger
    file1 = tmp_path / "x.json"
    data = [
        {"energy_code": "AAA"},
        {"energy_code": "BBB"},
    ]
    file1.write_text(json.dumps(data), encoding="utf-8")

    # Act
    mod.list_energy_codes(str(tmp_path), key="energy_code")

    # Assert
    out = capsys.readouterr().out
    assert "AAA" in out and "BBB" in out
    # İsim farklı olsa bile kod listesinde görünüyor olmalı
    lines = [line.strip() for line in out.splitlines()]
    assert "AAA" in lines and "BBB" in lines



def test_list_energy_codes_handles_invalid_json(tmp_path, capsys):
    # Arrange: bad JSON file
    file1 = tmp_path / "bad.json"
    file1.write_text("{ not valid json", encoding="utf-8")

    # Act
    mod.list_energy_codes(str(tmp_path))

    # Assert: error message printed, but function completes
    out = capsys.readouterr().out
    assert "⚠️ Failed to process bad.json" in out
