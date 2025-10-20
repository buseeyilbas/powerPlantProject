# test_filter_json_by_state_bundesland.py
"""
Unit tests for filter_json_by_state_bundesland.filter_by_state_codes

Covers:
1) Creates output base folder and per-code subfolders.
2) Writes filtered files with correct content and filenames.
3) Ignores non-.json files.
4) Handles bad/corrupted JSON gracefully (prints a warning, continues).
5) Does not write files when there are no matches (though subfolders exist).
6) Supports custom 'state_key' (not only 'Bundesland').
7) Prints progress lines ("Processing" and "Saved") for traceability.
"""

from pathlib import Path
import json
import pytest

import step11_filter_json_by_state_bundesland as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    """Write JSON for test inputs."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    """Read JSON back for assertions."""
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- tests ----------
def test_creates_dirs_and_writes_filtered_files(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    # Two input files with mixed Bundesland codes
    f1 = input_dir / "plants_1.json"
    wjson(f1, [
        {"id": 1, "Bundesland": "1409", "name": "Entry A"},
        {"id": 2, "Bundesland": "1415", "name": "Entry B"},
        {"id": 3, "Bundesland": "XXXX", "name": "Other"},
    ])
    f2 = input_dir / "plants_2.json"
    wjson(f2, [
        {"id": 10, "Bundesland": "1409", "name": "Entry C"},
        {"id": 11, "Bundesland": "1409", "name": "Entry D"},
    ])

    codes = ["1409", "1415"]
    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    # Base + per-code dirs must exist
    d1409 = out_base / "1409"
    d1415 = out_base / "1415"
    assert out_base.exists() and d1409.exists() and d1415.exists()

    # Files written under matching code folders with SAME filenames
    out_1409_1 = d1409 / "plants_1.json"
    out_1415_1 = d1415 / "plants_1.json"
    out_1409_2 = d1409 / "plants_2.json"
    assert out_1409_1.exists() and out_1415_1.exists() and out_1409_2.exists()

    # Contents filtered correctly
    assert rjson(out_1409_1) == [{"id": 1, "Bundesland": "1409", "name": "Entry A"}]
    assert rjson(out_1415_1) == [{"id": 2, "Bundesland": "1415", "name": "Entry B"}]
    assert rjson(out_1409_2) == [
        {"id": 10, "Bundesland": "1409", "name": "Entry C"},
        {"id": 11, "Bundesland": "1409", "name": "Entry D"},
    ]

    # Console output
    out = capsys.readouterr().out
    assert "Processing: plants_1.json" in out and "Processing: plants_2.json" in out
    assert "✔ Saved" in out




def test_ignores_non_json_and_reports_bad_json(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    # Non-JSON files ignored
    (input_dir / "readme.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "plants.json.bak").write_text("ignore", encoding="utf-8")

    # Bad JSON raises JSONDecodeError -> module should print a warning and continue
    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # Good JSON processed
    good = input_dir / "ok.json"
    wjson(good, [{"Bundesland": "1410", "id": 99}])

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", ["1409", "1410"])

    # Good written under 1410; broken should not appear anywhere
    assert (out_base / "1410" / "ok.json").exists()
    assert not (out_base / "1410" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert "✔ Saved" in out



def test_no_output_files_when_no_matches(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    # Data with codes that are NOT in 'codes'
    f = input_dir / "plants.json"
    wjson(f, [
        {"Bundesland": "9999", "id": 1},
        {"Bundesland": "8888", "id": 2},
    ])

    codes = ["1400", "1401"]  # target codes
    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    # Per-code dirs are pre-created, but there must be NO json files inside
    for code in codes:
        code_dir = out_base / code
        assert code_dir.exists()
        assert list(code_dir.glob("*.json")) == []

    # No "Saved" lines in output
    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out



def test_supports_custom_state_key(tmp_path: Path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    # Use a different key name instead of 'Bundesland'
    f = input_dir / "alt_key.json"
    wjson(f, [
        {"state_code": "1414", "id": 1},
        {"state_code": "1415", "id": 2},
        {"state_code": "xxxx", "id": 3},
    ])

    mod.filter_by_state_codes(str(input_dir), str(out_base), "state_code", ["1415"])

    out_file = out_base / "1415" / "alt_key.json"
    assert out_file.exists()
    assert rjson(out_file) == [{"state_code": "1415", "id": 2}]



def test_precreates_all_target_subfolders_even_before_processing(tmp_path: Path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    codes = ["1408", "1409", "1410"]
    # Put a single file that matches only one code
    f = input_dir / "plants.json"
    wjson(f, [{"Bundesland": "1409", "id": 1}])

    mod.filter_by_state_codes(str(input_dir), str(out_base), "Bundesland", codes)

    # All code dirs must exist (even if empty)
    for c in codes:
        d = out_base / c
        assert d.exists()
    # Only 1409 should have a file
    assert (out_base / "1409" / "plants.json").exists()
    assert list((out_base / "1408").glob("*.json")) == []
    assert list((out_base / "1410").glob("*.json")) == []
