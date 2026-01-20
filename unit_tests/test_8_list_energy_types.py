# test_8_list_energy_types.py
"""
Unit tests for step8_list_energy_types.list_energy_codes.

Covers:
1) Listing and sorting unique Energieträger codes.
2) Handling of custom JSON keys (e.g. 'energy_code').
3) Graceful skipping of invalid JSON files.
"""

import json
from pathlib import Path
import builtins
import io
import pytest

# ✅ standardized alias
import step8_list_energy_types as list_energy_types


def test_list_energy_codes_basic(tmp_path, capsys):
    """Should correctly list unique Energieträger codes from JSON files."""
    # Arrange
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"  # ignored non-JSON

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
    list_energy_types.list_energy_codes(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out

    lines = [line.strip() for line in out.splitlines()]
    codes_listed = [line for line in lines if line.isdigit()]
    assert codes_listed == sorted(["2495", "2497", "2403"])
    assert "✔ Unique Energieträger codes found:" in out


def test_list_energy_codes_with_custom_key(tmp_path, capsys):
    """Should correctly handle alternate key names (e.g. 'energy_code')."""
    file1 = tmp_path / "x.json"
    data = [
        {"energy_code": "AAA"},
        {"energy_code": "BBB"},
    ]
    file1.write_text(json.dumps(data), encoding="utf-8")

    # Act
    list_energy_types.list_energy_codes(str(tmp_path), key="energy_code")

    # Assert
    out = capsys.readouterr().out
    assert "AAA" in out and "BBB" in out

    lines = [line.strip() for line in out.splitlines()]
    assert "AAA" in lines and "BBB" in lines


def test_list_energy_codes_handles_invalid_json(tmp_path, capsys):
    """Invalid JSON file should be skipped gracefully."""
    file1 = tmp_path / "bad.json"
    file1.write_text("{ not valid json", encoding="utf-8")

    list_energy_types.list_energy_codes(str(tmp_path))

    out = capsys.readouterr().out
    assert "⚠️ Failed to process bad.json" in out


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
