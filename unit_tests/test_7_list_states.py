# test_7_list_states.py
"""
Unit tests for step7_list_states.list_state_codes.

Covers:
1) Basic listing and deduplication of Bundesland codes.
2) Handling of invalid JSON files.
3) Behavior with empty folder (no JSON files).
"""

import json
from pathlib import Path
import pytest

# ✅ standardized alias
import step7_list_states as list_states


def test_list_state_codes_basic(tmp_path, capsys):
    """Should list unique Bundesland codes from multiple JSON files."""
    # Arrange: create JSON files with Bundesland codes
    file1 = tmp_path / "a.json"
    file2 = tmp_path / "b.json"
    file3 = tmp_path / "ignore.txt"  # non-JSON, should be ignored

    data1 = [
        {"Bundesland": "05"},
        {"Bundesland": "14"},
        {"Bundesland": "05"},  # duplicate
        {"Bundesland": ""},    # empty ignored
        {}
    ]
    data2 = [
        {"Bundesland": "09"}
    ]

    file1.write_text(json.dumps(data1), encoding="utf-8")
    file2.write_text(json.dumps(data2), encoding="utf-8")
    file3.write_text("Ignore me", encoding="utf-8")

    # Act
    list_states.list_state_codes(str(tmp_path))

    # Assert output
    out = capsys.readouterr().out
    # All .json files scanned
    assert "→ Scanning: a.json" in out
    assert "→ Scanning: b.json" in out
    # Codes should be sorted in output
    lines = [line.strip() for line in out.splitlines()]
    codes_listed = [line for line in lines if line.isdigit()]
    assert codes_listed == sorted(["05", "09", "14"])
    assert "✔ Unique Bundesland codes found:" in out


def test_list_state_codes_handles_invalid_json(tmp_path, capsys):
    """Invalid JSON file should be skipped gracefully."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json", encoding="utf-8")

    # Act
    list_states.list_state_codes(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    assert "⚠️ Failed to process bad.json" in out


def test_list_state_codes_empty_folder(tmp_path, capsys):
    """Empty folder should not crash and print empty summary."""
    # Act
    list_states.list_state_codes(str(tmp_path))

    # Assert
    out = capsys.readouterr().out
    assert "✔ Unique Bundesland codes found:" in out
    assert not any(line.strip().isdigit() for line in out.splitlines())


# --- Run standalone ---
if __name__ == "__main__":
    pytest.main(["-v", __file__])
