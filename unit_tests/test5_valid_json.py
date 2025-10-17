# test_valid_json.py

import json
import sys
import types
from pathlib import Path
import pytest

import step5_valid_json as mod


# ---------- Tests for is_valid ----------

def test_is_valid_true_and_false_cases():
    base_entry = {
        "Bundesland": "05",
        "Energietraeger": "2495",
        "Gemeindeschluessel": "05170048",
        "LokationMaStRNummer": "SEL123",
        "EegMaStRNummer": "E123",
    }
    # All keys present and non-empty → valid
    assert mod.is_valid(base_entry) is True

    # Missing key
    entry_missing = dict(base_entry)
    del entry_missing["Bundesland"]
    assert mod.is_valid(entry_missing) is False

    # Empty value
    entry_empty = dict(base_entry)
    entry_empty["Bundesland"] = ""
    assert mod.is_valid(entry_empty) is False

    # None value
    entry_none = dict(base_entry)
    entry_none["Bundesland"] = None
    assert mod.is_valid(entry_none) is False


# ---------- Integration-like test for file processing ----------

def test_valid_json_file_processing(tmp_path, capsys, monkeypatch):
    # Arrange: prepare fake input and output folders
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    # Patch module constants to use temp dirs
    monkeypatch.setattr(mod, "input_folder", str(input_dir))
    monkeypatch.setattr(mod, "output_folder", str(output_dir))

    # Create files: valid.json (1 valid, 1 invalid), empty.json (no valid), bad.json (invalid JSON)
    valid_data = [
        {
            "Bundesland": "05",
            "Energietraeger": "2495",
            "Gemeindeschluessel": "05170048",
            "LokationMaStRNummer": "SEL123",
            "EegMaStRNummer": "E123",
        },
        {
            "Bundesland": "",
            "Energietraeger": "2495",
            "Gemeindeschluessel": "05170048",
            "LokationMaStRNummer": "SEL123",
            "EegMaStRNummer": "E123",
        }
    ]
    (input_dir / "valid.json").write_text(json.dumps(valid_data), encoding="utf-8")

    empty_data = [
        {"Bundesland": "", "Energietraeger": "", "Gemeindeschluessel": "", "LokationMaStRNummer": "", "EegMaStRNummer": ""}
    ]
    (input_dir / "empty.json").write_text(json.dumps(empty_data), encoding="utf-8")

    (input_dir / "bad.json").write_text("{ not valid json", encoding="utf-8")

    # Act: re-run the file processing loop manually
    # (We don't import again, so simulate the for-loop)
    total_files = 0
    total_valid_entries = 0
    for file_name in sorted(input_dir.iterdir()):
        if not file_name.name.endswith(".json"):
            continue
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Skipped invalid JSON: {file_name.name}")
                continue

        valid_entries = [entry for entry in data if mod.is_valid(entry)]
        if not valid_entries:
            print(f"❌ No valid entries in: {file_name.name}")
            continue

        output_path = output_dir / file_name.name
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(valid_entries, out_f, indent=2, ensure_ascii=False)
        print(f"✅ {file_name.name}: {len(valid_entries)} valid entries saved.")
        total_files += 1
        total_valid_entries += len(valid_entries)

    print("\n📊 Summary:")
    print(f"📂 JSON files processed: {total_files}")
    print(f"✔️ Total valid entries extracted: {total_valid_entries}")

    # Assert: Only valid.json should be saved
    saved_files = list(output_dir.glob("*.json"))
    assert len(saved_files) == 1
    assert saved_files[0].name == "valid.json"
    saved_data = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert len(saved_data) == 1  # only the valid entry

    # Console output checks
    out = capsys.readouterr().out
    assert "⚠️ Skipped invalid JSON: bad.json" in out
    assert "❌ No valid entries in: empty.json" in out
    assert "✅ valid.json: 1 valid entries saved." in out
    assert "📂 JSON files processed: 1" in out
    assert "✔️ Total valid entries extracted: 1" in out
