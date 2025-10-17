# test_filter_json_by_active_status.py
"""
Unit tests for step6_filter_json_by_active_status.filter_active_jsons

Covers:
1) Filters only entries where EinheitBetriebsstatus == "35".
2) Handles missing or malformed JSON gracefully.
3) Creates output folder if missing.
4) Prints summary of active/inactive counts.
"""

import json
from pathlib import Path
import step6_filter_json_by_active_status as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_filters_active_entries_only(tmp_path, capsys):
    # Arrange
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    # Create a mix of active (35) and inactive (other) entries
    file1 = input_dir / "plants.json"
    data = [
        {"EinheitBetriebsstatus": "35", "name": "ActivePlant"},
        {"EinheitBetriebsstatus": "99", "name": "InactivePlant"},
        {"EinheitBetriebsstatus": "35", "name": "ActivePlant2"},
    ]
    write_json(file1, data)

    # Patch global paths
    mod.input_folder = str(input_dir)
    mod.output_folder = str(output_dir)

    # Act
    mod.filter_active_jsons()

    # Assert
    out_file = output_dir / "plants.json"
    assert out_file.exists()
    result = read_json(out_file)
    assert len(result) == 2
    assert all(item["EinheitBetriebsstatus"] == "35" for item in result)

    out = capsys.readouterr().out
    assert "active" in out.lower()
    assert "inactive" in out.lower()


def test_handles_bad_json_file(tmp_path, capsys):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    bad = input_dir / "broken.json"
    bad.write_text("{ not valid json", encoding="utf-8")

    mod.input_folder = str(input_dir)
    mod.output_folder = str(output_dir)

    mod.filter_active_jsons()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    # No output files should exist
    assert not any(output_dir.glob("*.json"))


def test_creates_output_folder_if_missing(tmp_path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "ok.json").write_text("[]", encoding="utf-8")
    output_dir = tmp_path / "missing"

    mod.input_folder = str(input_dir)
    mod.output_folder = str(output_dir)

    mod.filter_active_jsons()

    assert output_dir.exists()
