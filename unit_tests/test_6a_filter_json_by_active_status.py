"""
Unit tests for step6a_filter_json_by_active_status.py

Covers:
- active filtering logic
- invalid JSON handling
- output folder creation
- multiple file summary correctness
- ignoring non-JSON files
- empty input folder behavior
- helper function correctness
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step6a_filter_json_by_active_status as filter_active


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_filters_active_entries_correctly(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    data = [
        {"EinheitBetriebsstatus": "35", "Name": "Plant A"},
        {"EinheitBetriebsstatus": "99", "Name": "Plant B"},
        {"EinheitBetriebsstatus": 35, "Name": "Plant C"},
        {"Name": "Missing Key"},
    ]
    write_json(input_dir / "plants.json", data)

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    out_file = output_dir / "plants.json"
    assert out_file.exists()

    result = read_json(out_file)
    assert len(result) == 2
    assert all(str(x["EinheitBetriebsstatus"]).strip() == "35" for x in result)

    output_text = capsys.readouterr().out
    assert "✅ plants.json: 2 active saved, 2 inactive found." in output_text
    assert "📂 JSON files processed: 1" in output_text
    assert "✔️ Total active entries saved: 2" in output_text
    assert "⚫ Total inactive entries detected: 2" in output_text


def test_skips_invalid_json_file(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "broken.json").write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    output_text = capsys.readouterr().out
    assert "⚠️ Skipped invalid JSON: broken.json" in output_text
    assert output_dir.exists()
    assert list(output_dir.glob("*.json")) == []
    assert "📂 JSON files processed: 0" in output_text
    assert "✔️ Total active entries saved: 0" in output_text
    assert "⚫ Total inactive entries detected: 0" in output_text


def test_handles_files_with_no_active_entries(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    data = [
        {"EinheitBetriebsstatus": "99"},
        {"EinheitBetriebsstatus": "12"},
    ]
    write_json(input_dir / "inactive.json", data)

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    output_text = capsys.readouterr().out
    assert "❌ No active entries in: inactive.json (2 inactive)" in output_text
    assert output_dir.exists()
    assert list(output_dir.glob("*.json")) == []
    assert "📂 JSON files processed: 0" in output_text
    assert "✔️ Total active entries saved: 0" in output_text
    assert "⚫ Total inactive entries detected: 2" in output_text


def test_creates_output_folder_if_missing(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "does_not_exist"

    write_json(input_dir / "plants.json", [{"EinheitBetriebsstatus": "35"}])

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    assert not output_dir.exists()

    filter_active.filter_active_jsons()

    assert output_dir.exists()
    assert output_dir.is_dir()
    assert (output_dir / "plants.json").exists()


def test_ignores_non_json_files(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    write_json(input_dir / "plants.json", [{"EinheitBetriebsstatus": "35"}])
    (input_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    (input_dir / "image.png").write_bytes(b"PNG")
    (input_dir / "backup.json.bak").write_text("not real json input", encoding="utf-8")

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    saved_files = sorted(p.name for p in output_dir.glob("*"))
    assert saved_files == ["plants.json"]

    output_text = capsys.readouterr().out
    assert "✅ plants.json: 1 active saved, 0 inactive found." in output_text
    assert "notes.txt" not in output_text
    assert "image.png" not in output_text
    assert "backup.json.bak" not in output_text


def test_counts_multiple_files_correctly(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    write_json(
        input_dir / "file1.json",
        [
            {"EinheitBetriebsstatus": "35"},
            {"EinheitBetriebsstatus": "99"},
        ],
    )
    write_json(
        input_dir / "file2.json",
        [
            {"EinheitBetriebsstatus": "35"},
            {"EinheitBetriebsstatus": "35"},
            {"EinheitBetriebsstatus": "12"},
        ],
    )
    write_json(
        input_dir / "file3.json",
        [
            {"EinheitBetriebsstatus": "99"},
        ],
    )

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    saved_files = sorted(p.name for p in output_dir.glob("*.json"))
    assert saved_files == ["file1.json", "file2.json"]

    file1_result = read_json(output_dir / "file1.json")
    file2_result = read_json(output_dir / "file2.json")

    assert len(file1_result) == 1
    assert len(file2_result) == 2

    output_text = capsys.readouterr().out
    assert "✅ file1.json: 1 active saved, 1 inactive found." in output_text
    assert "✅ file2.json: 2 active saved, 1 inactive found." in output_text
    assert "❌ No active entries in: file3.json (1 inactive)" in output_text
    assert "📂 JSON files processed: 2" in output_text
    assert "✔️ Total active entries saved: 3" in output_text
    assert "⚫ Total inactive entries detected: 3" in output_text


def test_empty_input_folder_produces_zero_summary(tmp_path, capsys, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    monkeypatch.setattr(filter_active, "input_folder", str(input_dir))
    monkeypatch.setattr(filter_active, "output_folder", str(output_dir))

    filter_active.filter_active_jsons()

    output_text = capsys.readouterr().out
    assert output_dir.exists()
    assert list(output_dir.glob("*.json")) == []
    assert "📂 JSON files processed: 0" in output_text
    assert "✔️ Total active entries saved: 0" in output_text
    assert "⚫ Total inactive entries detected: 0" in output_text


@pytest.mark.parametrize(
    ("entry", "expected"),
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
    assert filter_active.is_active(entry) == expected