# test_filter_json_by_installation_year.py
"""
Unit tests for filter_json_by_installation_year.py

Covers:
- extract_year edge cases and happy paths
- Creating year folders (1900..2025)
- Grouping entries by installation year (first 4 digits of string)
- Ignoring non-JSON files
- Handling of bad/corrupted JSON (warning + continue)
- Skipping invalid/out-of-range years and None
- Using a custom year_key argument
- Not writing output files when a year has zero matches
"""

from pathlib import Path
import json
import re
import pytest

import filter_json_by_installation_year as mod  # module under test


# ---------- helpers ----------
def wjson(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- unit tests for extract_year ----------
@pytest.mark.parametrize(
    "inp,expected",
    [
        ("2025-07-01", "2025"),
        ("1999", "1999"),
        ("2000/05", "2000"),
        ("201X-01-01", None),     # first 4 not all digits
        ("abc", None),
        ("", None),
        (None, None),
        (1234, None),             # non-str
        (" 2024-12-31", None),    # leading space -> first 4 chars are " 202" (invalid)
        ("20261231", "2026"),
    ],
)
def test_extract_year_cases(inp, expected):
    assert mod.extract_year(inp) == expected


# ---------- integration tests for filter_by_installation_years ----------
def test_creates_year_folders_and_writes_filtered_files(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    file1 = input_dir / "plants_A.json"
    wjson(file1, [
        {"id": 1, "Inbetriebnahmedatum": "2010-05-12"},
        {"id": 2, "Inbetriebnahmedatum": "2010-12-31"},
        {"id": 3, "Inbetriebnahmedatum": "1999-01-01"},
        {"id": 4, "Inbetriebnahmedatum": "1899-01-01"},  # out of range -> ignored
        {"id": 5, "Inbetriebnahmedatum": "2026-01-01"},  # out of range -> ignored
        {"id": 6, "Inbetriebnahmedatum": None},          # ignored
        {"id": 7},                                        # missing key -> ignored
    ])

    file2 = input_dir / "plants_B.json"
    wjson(file2, [
        {"id": 10, "Inbetriebnahmedatum": "2025-07-07"},
        {"id": 11, "Inbetriebnahmedatum": "2010-01-02"},
        {"id": 12, "Inbetriebnahmedatum": "2010/03/03"},
        {"id": 13, "Inbetriebnahmedatum": "abcd"},       # invalid -> ignored
    ])

    mod.filter_by_installation_years(str(input_dir), str(out_base))

    # Folders for 1900..2025 must exist (spot-check a few)
    for y in ("1900", "1999", "2010", "2025"):
        assert (out_base / y).exists() and (out_base / y).is_dir()

    # Verify written files and content
    y1999 = out_base / "1999" / "plants_A.json"
    y2010_a = out_base / "2010" / "plants_A.json"
    y2010_b = out_base / "2010" / "plants_B.json"
    y2025_b = out_base / "2025" / "plants_B.json"

    assert y1999.exists()
    assert y2010_a.exists() and y2010_b.exists()
    assert y2025_b.exists()

    assert rjson(y1999) == [{"id": 3, "Inbetriebnahmedatum": "1999-01-01"}]
    # 2010 collects two from A and two from B
    ids_2010 = [e["id"] for e in rjson(y2010_a)] + [e["id"] for e in rjson(y2010_b)]
    assert sorted(ids_2010) == [1, 2, 11, 12]  # order within files preserved; combined sorted for assertion
    assert rjson(y2025_b) == [{"id": 10, "Inbetriebnahmedatum": "2025-07-07"}]

    # Console output includes Processing and Saved lines
    out = capsys.readouterr().out
    assert "Processing: plants_A.json" in out and "Processing: plants_B.json" in out
    assert "✔ Saved" in out
    # Should not mention saving for 1899 or 2026
    assert "1899/" not in out and "2026/" not in out



def test_ignores_non_json_and_handles_bad_json(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    # Non-JSON files to be ignored
    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "data.json.bak").write_text("ignore", encoding="utf-8")

    # Bad JSON file to trigger warning and continue
    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ not valid json")

    # One good JSON
    good = input_dir / "ok.json"
    wjson(good, [{"id": 1, "Inbetriebnahmedatum": "1900-01-01"}])

    mod.filter_by_installation_years(str(input_dir), str(out_base))

    # Good file should be processed
    assert (out_base / "1900" / "ok.json").exists()
    # Bad file should be reported, not written
    assert not (out_base / "1900" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out



def test_no_output_when_no_matching_entries_for_a_year(tmp_path: Path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    f = input_dir / "plants.json"
    # Years out of allowed range or invalid formats
    wjson(f, [
        {"Inbetriebnahmedatum": "1888-01-01"},
        {"Inbetriebnahmedatum": "abcd"},
        {"Inbetriebnahmedatum": None},
    ])

    mod.filter_by_installation_years(str(input_dir), str(out_base))
    # Year folders exist (pre-created), but no file should be written into 1888
    json_files = list(out_base.rglob("*.json")) if out_base.exists() else []
    assert json_files == []  # no JSON files should be written anywhere
    # And there should be no files anywhere in 1900..2025
    any_written = any(f.is_file() for f in out_base.rglob("*.json"))
    assert not any_written

    out = capsys.readouterr().out
    # It processed the file but should not say "Saved"
    assert "Processing: plants.json" in out and "✔ Saved" not in out



def test_custom_year_key_supported(tmp_path: Path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    g = input_dir / "alt_key.json"
    wjson(g, [
        {"commissioning_date": "2001-09-09", "id": 1},
        {"commissioning_date": "2001/01/01", "id": 2},
        {"commissioning_date": "1998-12-31", "id": 3},
        {"commissioning_date": "2099-01-01", "id": 4},  # out of range
    ])

    mod.filter_by_installation_years(str(input_dir), str(out_base), year_key="commissioning_date")

    y2001 = out_base / "2001" / "alt_key.json"
    y1998 = out_base / "1998" / "alt_key.json"
    assert y2001.exists() and y1998.exists()
    ids_2001 = [e["id"] for e in rjson(y2001)]
    assert sorted(ids_2001) == [1, 2]
    assert rjson(y1998) == [{"commissioning_date": "1998-12-31", "id": 3}]
