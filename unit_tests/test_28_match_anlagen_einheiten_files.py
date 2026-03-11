"""
Unit tests for step28_match_anlagen_einheiten_files.py
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step28_match_anlagen_einheiten_files as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def temp_workspace(tmp_path):
    base_dir = tmp_path / "json"
    base_dir.mkdir()

    return {
        "root": tmp_path,
        "base_dir": base_dir,
    }


def test_build_key_for_anlagen_file():
    assert mod._build_key_for_anlagen_file("AnlagenSolar_7.json") == "solar_7"
    assert mod._build_key_for_anlagen_file("AnlagenEegSolar_7.json") == "solar_7"
    assert mod._build_key_for_anlagen_file("AnlagenEegGeothermieX.json") == "geothermiex"
    assert mod._build_key_for_anlagen_file("Solar_7.json") == "solar_7"
    assert mod._build_key_for_anlagen_file("AnlagenABC") == "abc"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2720.000", 2720.0),
        ("2720,000", 2720.0),
        (" 15 ", 15.0),
        (15, 15.0),
        (None, None),
        ("", None),
        ("abc", None),
    ],
)
def test_to_float(value, expected):
    assert mod._to_float(value) == expected


def test_load_einheiten_eeg_stats_basic(temp_workspace):
    base_dir = temp_workspace["base_dir"]

    write_json(
        base_dir / "EinheitenSolar.json",
        [
            {
                "EegMaStRNummer": "EEG1",
                "Bruttoleistung": "10.5",
                "Energietraeger": "2495",
            },
            {
                "EegMaStRNummer": "EEG1",
                "Bruttoleistung": "4,5",
                "Energietraeger": "2495",
            },
            {
                "EegMaStRNummer": "EEG2",
                "Bruttoleistung": "3",
                "Energietraeger": "2497",
            },
            {
                "Bruttoleistung": "5",
                "Energietraeger": "2499",
            },
            "not a dict",
        ],
    )

    eeg_stats, meta = mod.load_einheiten_eeg_stats(base_dir)

    assert meta == {
        "total_units": 3,
        "total_eeg_ids": 2,
        "einheiten_files": 1,
    }

    assert eeg_stats["EEG1"]["sum_brutto_kw"] == pytest.approx(15.0)
    assert eeg_stats["EEG1"]["unit_count"] == 2
    assert eeg_stats["EEG1"]["energy_types"] == {"2495"}

    assert eeg_stats["EEG2"]["sum_brutto_kw"] == pytest.approx(3.0)
    assert eeg_stats["EEG2"]["unit_count"] == 1
    assert eeg_stats["EEG2"]["energy_types"] == {"2497"}


def test_load_einheiten_eeg_stats_handles_invalid_json_and_non_list(temp_workspace, capsys):
    base_dir = temp_workspace["base_dir"]

    (base_dir / "EinheitenBad.json").write_text("{ invalid json", encoding="utf-8")
    write_json(base_dir / "EinheitenWrong.json", {"a": 1})

    eeg_stats, meta = mod.load_einheiten_eeg_stats(base_dir)

    assert eeg_stats == {}
    assert meta == {
        "total_units": 0,
        "total_eeg_ids": 0,
        "einheiten_files": 2,
    }

    out = capsys.readouterr().out
    assert "Could not parse EinheitenBad.json" in out
    assert "Unexpected JSON structure in EinheitenWrong.json" in out


def test_chunked_record_writer_writes_chunks(temp_workspace):
    base_dir = temp_workspace["base_dir"]

    writer = mod.ChunkedRecordWriter(
        base_dir=base_dir,
        base_name="records_part",
        max_records_per_chunk=2,
    )

    writer.write_record({"id": 1})
    writer.write_record({"id": 2})
    writer.write_record({"id": 3})
    files = writer.close()

    assert files == ["records_part_001.json", "records_part_002.json"]
    assert read_json(base_dir / "records_part_001.json") == [{"id": 1}, {"id": 2}]
    assert read_json(base_dir / "records_part_002.json") == [{"id": 3}]


def test_chunked_record_writer_close_without_records(temp_workspace):
    base_dir = temp_workspace["base_dir"]

    writer = mod.ChunkedRecordWriter(
        base_dir=base_dir,
        base_name="records_part",
        max_records_per_chunk=2,
    )

    files = writer.close()
    assert files == []
    assert list(base_dir.glob("records_part_*.json")) == []


def test_process_anlagen_with_eeg_basic_statuses(temp_workspace):
    base_dir = temp_workspace["base_dir"]

    write_json(
        base_dir / "AnlagenSolar_7.json",
        [
            {
                "EegMaStRNummer": "EEG_OK",
                "InstallierteLeistung": "15.0",
            },
            {
                "EegMaStRNummer": "EEG_MISMATCH",
                "InstallierteLeistung": "10.0",
            },
            {
                "EegMaStRNummer": "EEG_NO_UNITS",
                "InstallierteLeistung": "5.0",
            },
            {
                "EegMaStRNummer": "EEG_NO_POWER",
                "InstallierteLeistung": "",
            },
            {
                "EegMaStRNummer": "",
                "InstallierteLeistung": "",
            },
            "not a dict",
        ],
    )

    eeg_stats = {
        "EEG_OK": {
            "sum_brutto_kw": 15.0,
            "unit_count": 2,
            "energy_types": {"2495"},
        },
        "EEG_MISMATCH": {
            "sum_brutto_kw": 12.5,
            "unit_count": 1,
            "energy_types": {"2497"},
        },
        "EEG_NO_POWER": {
            "sum_brutto_kw": 7.0,
            "unit_count": 1,
            "energy_types": {"2498"},
        },
    }

    writer = mod.ChunkedRecordWriter(
        base_dir=base_dir,
        base_name="step28_records_part",
        max_records_per_chunk=100,
    )

    summary = mod.process_anlagen_with_eeg(base_dir, eeg_stats, writer)
    files = writer.close()

    assert summary == {
        "total_anlagen": 5,
        "anlagen_with_eeg_id": 4,
        "anlagen_without_eeg_id": 1,
        "anlagen_with_power_field": 3,
        "anlagen_without_power_field": 2,
        "ok_power_count": 1,
        "power_mismatch_count": 1,
        "no_einheiten_for_eeg_count": 1,
        "no_power_and_no_units_count": 1,
    }

    assert files == ["step28_records_part_001.json"]

    records = read_json(base_dir / "step28_records_part_001.json")
    assert len(records) == 5

    by_status = {r["status"]: r for r in records}

    assert by_status["ok"]["pair_key"] == "solar_7"
    assert by_status["ok"]["anlagen_file"] == "AnlagenSolar_7.json"
    assert by_status["ok"]["eeg_mastr_nummer"] == "EEG_OK"
    assert by_status["ok"]["energy_type_codes"] == ["2495"]
    assert by_status["ok"]["einheiten_unit_count"] == 2
    assert by_status["ok"]["installierte_leistung_kw"] == pytest.approx(15.0)
    assert by_status["ok"]["sum_bruttoleistung_kw"] == pytest.approx(15.0)
    assert by_status["ok"]["abs_power_diff_kw"] == pytest.approx(0.0)
    assert by_status["ok"]["has_power_field"] is True

    assert by_status["power_mismatch"]["energy_type_codes"] == ["2497"]
    assert by_status["power_mismatch"]["abs_power_diff_kw"] == pytest.approx(2.5)

    assert by_status["no_einheiten_for_eeg"]["sum_bruttoleistung_kw"] is None
    assert by_status["no_einheiten_for_eeg"]["einheiten_unit_count"] == 0

    assert by_status["no_power_field"]["has_power_field"] is False
    assert by_status["no_power_field"]["sum_bruttoleistung_kw"] == pytest.approx(7.0)

    assert by_status["no_power_and_no_units"]["has_power_field"] is False
    assert by_status["no_power_and_no_units"]["sum_bruttoleistung_kw"] is None


def test_process_anlagen_with_eeg_handles_invalid_json_and_non_list(temp_workspace, capsys):
    base_dir = temp_workspace["base_dir"]

    (base_dir / "AnlagenBad.json").write_text("{ invalid json", encoding="utf-8")
    write_json(base_dir / "AnlagenWrong.json", {"a": 1})

    writer = mod.ChunkedRecordWriter(
        base_dir=base_dir,
        base_name="step28_records_part",
        max_records_per_chunk=100,
    )

    summary = mod.process_anlagen_with_eeg(base_dir, {}, writer)
    files = writer.close()

    assert summary == {
        "total_anlagen": 0,
        "anlagen_with_eeg_id": 0,
        "anlagen_without_eeg_id": 0,
        "anlagen_with_power_field": 0,
        "anlagen_without_power_field": 0,
        "ok_power_count": 0,
        "power_mismatch_count": 0,
        "no_einheiten_for_eeg_count": 0,
        "no_power_and_no_units_count": 0,
    }
    assert files == []

    out = capsys.readouterr().out
    assert "Could not parse AnlagenBad.json" in out
    assert "Unexpected JSON structure in AnlagenWrong.json" in out


def test_main_writes_summary_and_chunk_files(temp_workspace, monkeypatch):
    base_dir = temp_workspace["base_dir"]

    write_json(
        base_dir / "EinheitenSolar.json",
        [
            {
                "EegMaStRNummer": "EEG1",
                "Bruttoleistung": "10.0",
                "Energietraeger": "2495",
            },
            {
                "EegMaStRNummer": "EEG1",
                "Bruttoleistung": "5.0",
                "Energietraeger": "2495",
            },
        ],
    )

    write_json(
        base_dir / "AnlagenSolar_7.json",
        [
            {
                "EegMaStRNummer": "EEG1",
                "InstallierteLeistung": "15.0",
            }
        ],
    )

    monkeypatch.setattr(mod, "BASE_DIR", base_dir)
    monkeypatch.setattr(mod, "MAX_RECORDS_PER_CHUNK", 10)

    mod.main()

    summary_path = base_dir / "step26_main_summary.json"
    records_path = base_dir / "step26_records_part_001.json"

    assert summary_path.exists()
    assert records_path.exists()

    summary = read_json(summary_path)
    assert summary["base_dir"] == str(base_dir)
    assert summary["power_tolerance_kw"] == mod.POWER_TOLERANCE_KW
    assert summary["einheiten_summary"] == {
        "total_units": 2,
        "total_eeg_ids": 1,
        "einheiten_files": 1,
    }
    assert summary["anlagen_summary"]["total_anlagen"] == 1
    assert summary["anlagen_summary"]["ok_power_count"] == 1
    assert summary["record_files"] == ["step26_records_part_001.json"]
    assert summary["max_records_per_chunk"] == 10

    records = read_json(records_path)
    assert len(records) == 1
    assert records[0]["status"] == "ok"


def test_main_returns_early_when_base_dir_missing(tmp_path, monkeypatch, capsys):
    missing_dir = tmp_path / "does_not_exist"
    monkeypatch.setattr(mod, "BASE_DIR", missing_dir)

    mod.main()

    out = capsys.readouterr().out
    assert "Base directory does not exist" in out