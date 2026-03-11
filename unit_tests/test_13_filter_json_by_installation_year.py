"""
Unit tests for step13_filter_json_by_installation_year.py
"""

import sys
from pathlib import Path
import json
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step13_filter_json_by_installation_year as mod


def wjson(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def rjson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "inp,expected",
    [
        ("2025-07-01", "2025"),
        ("1999", "1999"),
        ("2000/05", "2000"),
        ("201X-01-01", None),
        ("abc", None),
        ("", None),
        (None, None),
        (1234, None),
        (" 2024-12-31", None),
        ("20261231", "2026"),
    ],
)
def test_extract_year_cases(inp, expected):
    assert mod.extract_year(inp) == expected


def test_creates_year_folders_and_writes_filtered_files(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    wjson(
        input_dir / "plants_A.json",
        [
            {"id": 1, "Inbetriebnahmedatum": "2010-05-12"},
            {"id": 2, "Inbetriebnahmedatum": "2010-12-31"},
            {"id": 3, "Inbetriebnahmedatum": "1999-01-01"},
            {"id": 4, "Inbetriebnahmedatum": "1899-01-01"},
            {"id": 5, "Inbetriebnahmedatum": "2026-01-01"},
            {"id": 6, "Inbetriebnahmedatum": None},
            {"id": 7},
        ],
    )

    wjson(
        input_dir / "plants_B.json",
        [
            {"id": 10, "Inbetriebnahmedatum": "2025-07-07"},
            {"id": 11, "Inbetriebnahmedatum": "2010-01-02"},
            {"id": 12, "Inbetriebnahmedatum": "2010/03/03"},
            {"id": 13, "Inbetriebnahmedatum": "abcd"},
        ],
    )

    mod.filter_by_installation_years(str(input_dir), str(out_base))

    for year in ("1900", "1999", "2010", "2025"):
        assert (out_base / year).exists()

    y1999 = out_base / "1999" / "plants_A.json"
    y2010_a = out_base / "2010" / "plants_A.json"
    y2010_b = out_base / "2010" / "plants_B.json"
    y2025_b = out_base / "2025" / "plants_B.json"

    assert y1999.exists()
    assert y2010_a.exists()
    assert y2010_b.exists()
    assert y2025_b.exists()

    assert rjson(y1999) == [{"id": 3, "Inbetriebnahmedatum": "1999-01-01"}]

    ids_2010 = [e["id"] for e in rjson(y2010_a)] + [e["id"] for e in rjson(y2010_b)]
    assert sorted(ids_2010) == [1, 2, 11, 12]

    assert rjson(y2025_b) == [{"id": 10, "Inbetriebnahmedatum": "2025-07-07"}]

    out = capsys.readouterr().out
    assert "Processing: plants_A.json" in out
    assert "Processing: plants_B.json" in out
    assert "✔ Saved" in out
    assert "1899/" not in out
    assert "2026/" not in out


def test_ignores_non_json_and_handles_bad_json(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    (input_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (input_dir / "data.json.bak").write_text("ignore", encoding="utf-8")

    bad = input_dir / "broken.json"
    bad.write_bytes(b"{ not valid json")

    good = input_dir / "ok.json"
    wjson(good, [{"id": 1, "Inbetriebnahmedatum": "1900-01-01"}])

    mod.filter_by_installation_years(str(input_dir), str(out_base))

    assert (out_base / "1900" / "ok.json").exists()
    assert not (out_base / "1900" / "broken.json").exists()

    out = capsys.readouterr().out
    assert "Failed to load broken.json" in out


def test_no_output_when_no_matching_entries(tmp_path, capsys):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    wjson(
        input_dir / "plants.json",
        [
            {"Inbetriebnahmedatum": "1888-01-01"},
            {"Inbetriebnahmedatum": "abcd"},
            {"Inbetriebnahmedatum": None},
        ],
    )

    mod.filter_by_installation_years(str(input_dir), str(out_base))

    json_files = list(out_base.rglob("*.json"))
    assert json_files == []

    out = capsys.readouterr().out
    assert "Processing: plants.json" in out
    assert "✔ Saved" not in out


def test_custom_year_key_supported(tmp_path):
    input_dir = tmp_path / "in"
    out_base = tmp_path / "out"
    input_dir.mkdir()

    wjson(
        input_dir / "alt_key.json",
        [
            {"commissioning_date": "2001-09-09", "id": 1},
            {"commissioning_date": "2001/01/01", "id": 2},
            {"commissioning_date": "1998-12-31", "id": 3},
            {"commissioning_date": "2099-01-01", "id": 4},
        ],
    )

    mod.filter_by_installation_years(str(input_dir), str(out_base), year_key="commissioning_date")

    y2001 = out_base / "2001" / "alt_key.json"
    y1998 = out_base / "1998" / "alt_key.json"

    assert y2001.exists()
    assert y1998.exists()

    ids_2001 = [e["id"] for e in rjson(y2001)]
    assert sorted(ids_2001) == [1, 2]

    assert rjson(y1998) == [{"commissioning_date": "1998-12-31", "id": 3}]