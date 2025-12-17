# test_filter_json_by_state_gemeindeschluessel.py
"""
Unit tests for filter_json_by_state_gemeindeschluessel.py

Covers:
- extract_state_prefix edge cases and happy paths
- Base output folder creation; per-prefix dirs only when matches exist
- Filtering/writing by 2-char state prefix from 'Gemeindeschluessel'
- Ignoring non-JSON files
- Reporting and skipping bad/corrupted JSON
- Preserving filenames and writing correct filtered content
"""

from pathlib import Path
import json
import pytest

import step12_filter_json_by_state_gemeindeschluessel as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests for extract_state_prefix ----------
@pytest.mark.parametrize(
    "inp,expected",
    [
        ("05170048", "05"),     # typical case
        ("14060000", "14"),
        ("99", "99"),           # exactly 2 chars
        ("9", None),            # too short
        ("", None),             # empty
        (None, None),           # None
        (123456, None),         # non-string
        ("XX123", "XX"),        # non-digit but still string → first 2 chars
        (" 5A170048", " 5"),    # leading space is still a char → first 2 chars
    ],
)
def test_extract_state_prefix_cases(inp, expected):
    assert mod.extract_state_prefix(inp) == expected


# ---------- integration tests ----------
def test_creates_base_folder_and_writes_per_prefix_files(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    f1 = input_dir / "plants_A.json"
    wjson(f1, [
        {"id": 1, "Gemeindeschluessel": "05170048", "name": "Entry A"},  # prefix 05
        {"id": 2, "Gemeindeschluessel": "14150000", "name": "Entry B"},  # prefix 14
        {"id": 3, "Gemeindeschluessel": "XX000000", "name": "Other"},    # prefix XX
        {"id": 4, "Gemeindeschluessel": None, "name": "NoGKey"},         # ignored
    ])

    f2 = input_dir / "plants_B.json"
    wjson(f2, [
        {"id": 10, "Gemeindeschluessel": "05179999", "name": "Entry C"}, # prefix 05
        {"id": 11, "Gemeindeschluessel": "14150001", "name": "Entry D"}, # prefix 14
        {"id": 12, "name": "MissingKey"},                                # ignored
    ])

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    # Base output always created
    assert output_base.exists() and output_base.is_dir()

    # Per-prefix directories created only for prefixes that had matches
    d05 = output_base / "05"
    d14 = output_base / "14"
    dXX = output_base / "XX"
    assert d05.exists() and d14.exists() and dXX.exists()

    # Filenames preserved under each prefix
    out_05_A = d05 / "plants_A.json"
    out_05_B = d05 / "plants_B.json"
    out_14_A = d14 / "plants_A.json"
    out_14_B = d14 / "plants_B.json"
    out_xx_A = dXX / "plants_A.json"
    assert out_05_A.exists() and out_05_B.exists()
    assert out_14_A.exists() and out_14_B.exists()
    assert out_xx_A.exists()

    # Content filtered correctly
    assert rjson(out_05_A) == [{"id": 1, "Gemeindeschluessel": "05170048", "name": "Entry A"}]
    assert rjson(out_05_B) == [{"id": 10, "Gemeindeschluessel": "05179999", "name": "Entry C"}]
    assert rjson(out_14_A) == [{"id": 2, "Gemeindeschluessel": "14150000", "name": "Entry B"}]
    assert rjson(out_14_B) == [{"id": 11, "Gemeindeschluessel": "14150001", "name": "Entry D"}]
    assert rjson(out_xx_A) == [{"id": 3, "Gemeindeschluessel": "XX000000", "name": "Other"}]

    # Console output contains progress and save lines
    out = capsys.readouterr().out
    assert "Processing: plants_A.json" in out and "Processing: plants_B.json" in out
    assert "✔ Saved" in out


def test_ignores_non_json_and_reports_bad_json(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    # Non-JSON files ignored
    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "plants.json.bak").write_text("ignore", encoding="utf-8")

    # Bad JSON triggers warning and continue
    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ invalid json")

    # One good JSON
    good = input_dir / "ok.json"
    wjson(good, [{"Gemeindeschluessel": "0517xxxx", "id": 42}])  # prefix 05

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    # Good processed, bad skipped
    assert (output_base / "05" / "ok.json").exists()
    assert not (output_base / "05" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out
    assert "✔ Saved" in out


def test_no_prefix_dirs_when_no_valid_prefixes(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    output_base = tmp_path / "out"
    input_dir.mkdir()

    # All entries missing/invalid Gemeindeschluessel → no per-prefix dirs
    f = input_dir / "plants.json"
    wjson(f, [
        {"Gemeindeschluessel": None, "id": 1},
        {"Gemeindeschluessel": "", "id": 2},
        {"Gemeindeschluessel": "9", "id": 3},   # length < 2
        {"id": 4},                               # missing key
    ])

    mod.filter_by_state_prefix(str(input_dir), str(output_base))

    # Base created, but there should be NO subdirectories/files
    assert output_base.exists() and output_base.is_dir()
    assert list(output_base.iterdir()) == []   # empty

    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out
