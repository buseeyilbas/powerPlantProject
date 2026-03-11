"""
Unit tests for step5_valid_json module.

Covers:
- is_valid() behavior
- process_all_jsons() end-to-end file processing
- output folder creation
- invalid JSON handling
- skipping files with no valid entries
- ignoring non-JSON files
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step5_valid_json as valid_json


@pytest.fixture
def valid_entry():
    """Return a fully valid sample entry."""
    return {
        "Bundesland": "05",
        "Energietraeger": "2495",
        "Gemeindeschluessel": "05170048",
        "LokationMaStRNummer": "SEL123",
        "EegMaStRNummer": "E123",
    }


# ---------- Tests for is_valid ----------

def test_is_valid_returns_true_for_complete_entry(valid_entry):
    """Should return True when all required keys are present and non-empty."""
    assert valid_json.is_valid(valid_entry) is True


@pytest.mark.parametrize("missing_key", valid_json.REQUIRED_KEYS)
def test_is_valid_returns_false_when_required_key_is_missing(valid_entry, missing_key):
    """Should return False when any required key is missing."""
    entry = dict(valid_entry)
    del entry[missing_key]

    assert valid_json.is_valid(entry) is False


@pytest.mark.parametrize("empty_value", ["", None])
@pytest.mark.parametrize("target_key", valid_json.REQUIRED_KEYS)
def test_is_valid_returns_false_when_required_value_is_empty(valid_entry, target_key, empty_value):
    """Should return False when any required key has an empty or None value."""
    entry = dict(valid_entry)
    entry[target_key] = empty_value

    assert valid_json.is_valid(entry) is False


def test_is_valid_allows_extra_keys(valid_entry):
    """Should still return True when extra non-required keys are present."""
    entry = dict(valid_entry)
    entry["ExtraField"] = "extra"

    assert valid_json.is_valid(entry) is True


# ---------- Tests for process_all_jsons ----------

def test_process_all_jsons_end_to_end(tmp_path, capsys, monkeypatch, valid_entry):
    """Should save only valid entries, skip bad JSON, and print correct summary."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    valid_data = [
        valid_entry,
        {
            "Bundesland": "",
            "Energietraeger": "2495",
            "Gemeindeschluessel": "05170048",
            "LokationMaStRNummer": "SEL123",
            "EegMaStRNummer": "E123",
        },
    ]
    (input_dir / "valid.json").write_text(json.dumps(valid_data), encoding="utf-8")

    empty_data = [
        {
            "Bundesland": "",
            "Energietraeger": "",
            "Gemeindeschluessel": "",
            "LokationMaStRNummer": "",
            "EegMaStRNummer": "",
        }
    ]
    (input_dir / "empty.json").write_text(json.dumps(empty_data), encoding="utf-8")

    (input_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")
    (input_dir / "notes.txt").write_text("ignore me", encoding="utf-8")

    valid_json.process_all_jsons()

    saved_files = sorted(output_dir.glob("*.json"))
    assert len(saved_files) == 1
    assert saved_files[0].name == "valid.json"

    saved_data = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert saved_data == [valid_entry]

    out = capsys.readouterr().out
    assert "⚠️ Skipped invalid JSON: bad.json" in out
    assert "❌ No valid entries in: empty.json" in out
    assert "✅ valid.json: 1 valid entries saved." in out
    assert "📂 JSON files processed: 1" in out
    assert "✔️ Total valid entries extracted: 1" in out


def test_process_all_jsons_creates_output_folder_when_missing(tmp_path, monkeypatch, valid_entry):
    """Should create the output folder automatically if it does not exist."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "valid.json").write_text(json.dumps([valid_entry]), encoding="utf-8")

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    assert not output_dir.exists()

    valid_json.process_all_jsons()

    assert output_dir.exists()
    assert output_dir.is_dir()
    assert (output_dir / "valid.json").exists()


def test_process_all_jsons_ignores_non_json_files(tmp_path, monkeypatch, capsys, valid_entry):
    """Should ignore files that do not end with .json."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "valid.json").write_text(json.dumps([valid_entry]), encoding="utf-8")
    (input_dir / "image.png").write_bytes(b"PNG")
    (input_dir / "notes.txt").write_text("hello", encoding="utf-8")
    (input_dir / "backup.json.bak").write_text("not json", encoding="utf-8")

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    valid_json.process_all_jsons()

    saved_files = sorted(output_dir.glob("*"))
    assert [p.name for p in saved_files] == ["valid.json"]

    out = capsys.readouterr().out
    assert "✅ valid.json: 1 valid entries saved." in out
    assert "backup.json.bak" not in out
    assert "image.png" not in out
    assert "notes.txt" not in out


def test_process_all_jsons_skips_file_when_no_valid_entries(tmp_path, monkeypatch, capsys):
    """Should not create an output file when a JSON file contains no valid entries."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    invalid_only_data = [
        {
            "Bundesland": "",
            "Energietraeger": "2495",
            "Gemeindeschluessel": "05170048",
            "LokationMaStRNummer": "SEL123",
            "EegMaStRNummer": "E123",
        }
    ]
    (input_dir / "invalid_only.json").write_text(json.dumps(invalid_only_data), encoding="utf-8")

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    valid_json.process_all_jsons()

    assert output_dir.exists()
    assert list(output_dir.glob("*.json")) == []

    out = capsys.readouterr().out
    assert "❌ No valid entries in: invalid_only.json" in out
    assert "📂 JSON files processed: 0" in out
    assert "✔️ Total valid entries extracted: 0" in out


def test_process_all_jsons_skips_invalid_json_file(tmp_path, monkeypatch, capsys):
    """Should skip invalid JSON files and continue processing."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "bad.json").write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    valid_json.process_all_jsons()

    assert output_dir.exists()
    assert list(output_dir.glob("*.json")) == []

    out = capsys.readouterr().out
    assert "⚠️ Skipped invalid JSON: bad.json" in out
    assert "📂 JSON files processed: 0" in out
    assert "✔️ Total valid entries extracted: 0" in out


def test_process_all_jsons_counts_multiple_valid_files(tmp_path, monkeypatch, capsys, valid_entry):
    """Should correctly count processed files and total valid entries across multiple files."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    second_valid_entry = dict(valid_entry)
    second_valid_entry["LokationMaStRNummer"] = "SEL999"
    second_valid_entry["EegMaStRNummer"] = "E999"

    (input_dir / "file1.json").write_text(json.dumps([valid_entry]), encoding="utf-8")
    (input_dir / "file2.json").write_text(json.dumps([valid_entry, second_valid_entry]), encoding="utf-8")

    monkeypatch.setattr(valid_json, "input_folder", str(input_dir))
    monkeypatch.setattr(valid_json, "output_folder", str(output_dir))

    valid_json.process_all_jsons()

    saved_files = sorted(p.name for p in output_dir.glob("*.json"))
    assert saved_files == ["file1.json", "file2.json"]

    file1_data = json.loads((output_dir / "file1.json").read_text(encoding="utf-8"))
    file2_data = json.loads((output_dir / "file2.json").read_text(encoding="utf-8"))

    assert len(file1_data) == 1
    assert len(file2_data) == 2

    out = capsys.readouterr().out
    assert "📂 JSON files processed: 2" in out
    assert "✔️ Total valid entries extracted: 3" in out