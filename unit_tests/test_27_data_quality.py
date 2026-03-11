"""
Unit tests for step27_data_quality.py
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import step27_data_quality as mod


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def temp_workspace(tmp_path):
    all_dir = tmp_path / "json"
    valid_dir = tmp_path / "valid_json"
    active_dir = tmp_path / "active_json"

    all_dir.mkdir()
    valid_dir.mkdir()
    active_dir.mkdir()

    return {
        "root": tmp_path,
        "all_dir": all_dir,
        "valid_dir": valid_dir,
        "active_dir": active_dir,
    }


def test_iter_json_files_returns_only_json_files(temp_workspace):
    all_dir = temp_workspace["all_dir"]

    (all_dir / "a.json").write_text("[]", encoding="utf-8")
    (all_dir / "b.JSON").write_text("[]", encoding="utf-8")
    (all_dir / "note.txt").write_text("x", encoding="utf-8")

    result = sorted(Path(p).name for p in mod._iter_json_files(str(all_dir)))
    assert result == ["a.json", "b.JSON"]


def test_iter_json_files_filters_only_einheiten(temp_workspace):
    all_dir = temp_workspace["all_dir"]

    (all_dir / "EinheitenSolar.json").write_text("[]", encoding="utf-8")
    (all_dir / "EinheitenWind.JSON").write_text("[]", encoding="utf-8")
    (all_dir / "Other.json").write_text("[]", encoding="utf-8")

    result = sorted(Path(p).name for p in mod._iter_json_files(str(all_dir), only_einheiten=True))
    assert result == ["EinheitenSolar.json", "EinheitenWind.JSON"]


def test_iter_json_files_returns_empty_for_missing_directory(tmp_path):
    missing = tmp_path / "does_not_exist"
    result = list(mod._iter_json_files(str(missing)))
    assert result == []


def test_load_entries_from_file_reads_list(temp_workspace):
    path = temp_workspace["all_dir"] / "list.json"
    payload = [{"a": 1}, {"b": 2}]
    write_json(path, payload)

    result = mod._load_entries_from_file(str(path))
    assert result == payload


def test_load_entries_from_file_reads_dict_values(temp_workspace):
    path = temp_workspace["all_dir"] / "dict.json"
    payload = {"x": {"a": 1}, "y": {"b": 2}}
    write_json(path, payload)

    result = mod._load_entries_from_file(str(path))
    assert result == list(payload.values())


def test_load_entries_from_file_returns_empty_for_invalid_json(temp_workspace, capsys):
    path = temp_workspace["all_dir"] / "bad.json"
    path.write_text("{ invalid json", encoding="utf-8")

    result = mod._load_entries_from_file(str(path))

    assert result == []
    out = capsys.readouterr().out
    assert "[WARN] Could not read JSON file:" in out
    assert "bad.json" in out


def test_load_entries_from_file_returns_empty_for_unsupported_structure(temp_workspace):
    path = temp_workspace["all_dir"] / "scalar.json"
    path.write_text('"hello"', encoding="utf-8")

    result = mod._load_entries_from_file(str(path))
    assert result == []


def test_collect_stats_counts_entries_states_and_energy(temp_workspace):
    all_dir = temp_workspace["all_dir"]

    write_json(
        all_dir / "EinheitenA.json",
        [
            {"Bundesland": "1403", "Energietraeger": "2495"},
            {"Bundesland": "1403", "Energietraeger": "2497"},
            {"Bundesland": "1415", "Energietraeger": "2495"},
            {"Bundesland": "", "Energietraeger": ""},
            "not a dict",
        ],
    )

    stats = mod._collect_stats(str(all_dir), only_einheiten=True)

    assert stats["count"] == 4
    assert stats["by_state"] == {"1403": 2, "1415": 1}
    assert stats["by_energy"] == {"2495": 2, "2497": 1}


def test_collect_stats_ignores_non_einheiten_when_requested(temp_workspace):
    all_dir = temp_workspace["all_dir"]

    write_json(
        all_dir / "EinheitenA.json",
        [{"Bundesland": "1403", "Energietraeger": "2495"}],
    )
    write_json(
        all_dir / "Other.json",
        [{"Bundesland": "1415", "Energietraeger": "2497"}],
    )

    stats = mod._collect_stats(str(all_dir), only_einheiten=True)

    assert stats["count"] == 1
    assert stats["by_state"] == {"1403": 1}
    assert stats["by_energy"] == {"2495": 1}


def test_collect_stats_handles_invalid_json_gracefully(temp_workspace, capsys):
    all_dir = temp_workspace["all_dir"]

    (all_dir / "EinheitenBad.json").write_text("{ invalid json", encoding="utf-8")

    stats = mod._collect_stats(str(all_dir), only_einheiten=True)

    assert stats["count"] == 0
    assert stats["by_state"] == {}
    assert stats["by_energy"] == {}

    out = capsys.readouterr().out
    assert "[WARN] Could not read JSON file:" in out


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (0, 0, 0.0),
        (1, 2, 50.0),
        (2, 3, 66.67),
        (5, 4, 125.0),
    ],
)
def test_percent(numerator, denominator, expected):
    assert mod._percent(numerator, denominator) == expected


def test_build_summary_uses_all_valid_active_folders(monkeypatch, temp_workspace):
    all_dir = temp_workspace["all_dir"]
    valid_dir = temp_workspace["valid_dir"]
    active_dir = temp_workspace["active_dir"]

    write_json(
        all_dir / "EinheitenA.json",
        [
            {"Bundesland": "1403", "Energietraeger": "2495"},
            {"Bundesland": "1415", "Energietraeger": "2497"},
            {"Bundesland": "1415", "Energietraeger": "2497"},
        ],
    )
    write_json(
        all_dir / "IgnoreMe.json",
        [
            {"Bundesland": "9999", "Energietraeger": "0000"},
        ],
    )

    write_json(
        valid_dir / "valid_a.json",
        [
            {"Bundesland": "1403", "Energietraeger": "2495"},
            {"Bundesland": "1415", "Energietraeger": "2497"},
        ],
    )

    write_json(
        active_dir / "active_a.json",
        [
            {"Bundesland": "1403", "Energietraeger": "2495"},
        ],
    )

    monkeypatch.setattr(mod, "ALL_JSON_DIR", str(all_dir))
    monkeypatch.setattr(mod, "VALID_JSON_DIR", str(valid_dir))
    monkeypatch.setattr(mod, "ACTIVE_JSON_DIR", str(active_dir))

    summary = mod.build_summary()

    assert summary["overall"]["all"] == 3
    assert summary["overall"]["valid"] == 2
    assert summary["overall"]["active"] == 1
    assert summary["overall"]["valid_over_all"] == 66.67
    assert summary["overall"]["active_over_all"] == 33.33
    assert summary["overall"]["active_over_valid"] == 50.0

    assert summary["all"]["by_state"] == {"1403": 1, "1415": 2}
    assert summary["valid"]["by_state"] == {"1403": 1, "1415": 1}
    assert summary["active"]["by_state"] == {"1403": 1}

    assert summary["all"]["by_energy"] == {"2495": 1, "2497": 2}
    assert summary["valid"]["by_energy"] == {"2495": 1, "2497": 1}
    assert summary["active"]["by_energy"] == {"2495": 1}


def test_build_summary_with_empty_folders(monkeypatch, temp_workspace):
    monkeypatch.setattr(mod, "ALL_JSON_DIR", str(temp_workspace["all_dir"]))
    monkeypatch.setattr(mod, "VALID_JSON_DIR", str(temp_workspace["valid_dir"]))
    monkeypatch.setattr(mod, "ACTIVE_JSON_DIR", str(temp_workspace["active_dir"]))

    summary = mod.build_summary()

    assert summary["overall"] == {
        "all": 0,
        "valid": 0,
        "active": 0,
        "valid_over_all": 0.0,
        "active_over_all": 0.0,
        "active_over_valid": 0.0,
    }
    assert summary["all"]["by_state"] == {}
    assert summary["valid"]["by_state"] == {}
    assert summary["active"]["by_state"] == {}
    assert summary["all"]["by_energy"] == {}
    assert summary["valid"]["by_energy"] == {}
    assert summary["active"]["by_energy"] == {}


def test_print_summary_outputs_expected_lines(capsys):
    summary = {
        "overall": {
            "all": 100,
            "valid": 80,
            "active": 60,
            "valid_over_all": 80.0,
            "active_over_all": 60.0,
            "active_over_valid": 75.0,
        }
    }

    mod.print_summary(summary)

    out = capsys.readouterr().out
    assert "Extended MaStR Data Quality Summary" in out
    assert "All entries:    100" in out
    assert "Valid entries:  80" in out
    assert "Active entries: 60" in out
    assert "Valid / All   : 80.0%" in out
    assert "Active / All  : 60.0%" in out
    assert "Active / Valid: 75.0%" in out