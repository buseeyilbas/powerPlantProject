# test_6_filter_json_by_active_status.py
"""
Unit tests for step6_filter_json_by_active_status.py

Covers:
1) Filtering logic for active/inactive entries.
2) Handling invalid or missing JSON data.
3) Folder creation.
4) Summary and console output consistency.
5) is_active() helper correctness.
"""

import os
import json
from pathlib import Path
import pytest
import step6_filter_json_by_active_status as filter_active


# ---------- Helper utilities ----------

def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- Core behavior tests ----------

def test_filters_active_entries_correctly(tmp_path, capsys):
    """Ensures that only entries with EinheitBetriebsstatus == '35' are kept."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    data = [
        {"EinheitBetriebsstatus": "35", "Name": "Plant A"},
        {"EinheitBetriebsstatus": "99", "Name": "Plant B"},
        {"EinheitBetriebsstatus": 35, "Name": "Plant C"},  # integer should also pass
        {"Name": "Missing Key"},  # inactive by default
    ]
    write_json(input_dir / "plants.json", data)

    # Patch module globals
    filter_active.input_folder = str(input_dir)
    filter_active.output_folder = str(output_dir)

    # Run
    filter_active.filter_active_jsons()

    # Assertions
    out_file = output_dir / "plants.json"
    assert out_file.exists()
    result = read_json(out_file)

    # Only 2 should remain active
    assert len(result) == 2
    assert all(str(x["EinheitBetriebsstatus"]).strip() == "35" for x in result)

    output_text = capsys.readouterr().out
    assert "✅ plants.json" in output_text
    assert "active saved" in output_text
    assert "inactive found" in output_text
    assert "Summary" in output_text


def test_skips_invalid_json_file(tmp_path, capsys):
    """Should skip files that are not valid JSON."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    filter_active.input_folder = str(input_dir)
    filter_active.output_folder = str(output_dir)

    filter_active.filter_active_jsons()

    output_text = capsys.readouterr().out
    assert "Skipped invalid JSON" in output_text
    assert not any(output_dir.glob("*.json"))


def test_handles_files_with_no_active_entries(tmp_path, capsys):
    """If no entries are active, should not write output but print summary."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    data = [
        {"EinheitBetriebsstatus": "99"},
        {"EinheitBetriebsstatus": "12"},
    ]
    write_json(input_dir / "inactive.json", data)

    filter_active.input_folder = str(input_dir)
    filter_active.output_folder = str(output_dir)

    filter_active.filter_active_jsons()

    output_text = capsys.readouterr().out
    assert "❌ No active entries" in output_text
    assert not any(output_dir.glob("*.json"))


def test_creates_output_folder_if_missing(tmp_path):
    """Output folder should be automatically created if missing."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "does_not_exist"
    write_json(input_dir / "plants.json", [{"EinheitBetriebsstatus": "35"}])

    filter_active.input_folder = str(input_dir)
    filter_active.output_folder = str(output_dir)

    filter_active.filter_active_jsons()
    assert output_dir.exists()


# ---------- Unit-level helper tests ----------

@pytest.mark.parametrize(
    "entry,expected",
    [
        ({"EinheitBetriebsstatus": "35"}, True),
        ({"EinheitBetriebsstatus": 35}, True),
        ({"EinheitBetriebsstatus": " 35 "}, True),
        ({"EinheitBetriebsstatus": "99"}, False),
        ({"EinheitBetriebsstatus": None}, False),
        ({}, False),
    ],
)
def test_is_active_various_cases(entry, expected):
    """Check correctness of is_active() under different data conditions."""
    assert filter_active.is_active(entry) == expected


# ---------- Standalone execution ----------

if __name__ == "__main__":
    pytest.main(["-v", __file__])
