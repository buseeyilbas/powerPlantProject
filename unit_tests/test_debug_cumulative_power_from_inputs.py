"""
Unit tests for debug_cumulative_power_from_inputs.py
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import debug_cumulative_power_from_inputs as mod


def test_find_power_col_returns_first_matching_field():
    cols = ["id", "Bruttoleistung", "power_kw", "year"]
    assert mod.find_power_col(cols) == "power_kw"


def test_find_power_col_returns_none_when_missing():
    cols = ["id", "name", "year"]
    assert mod.find_power_col(cols) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2020-05-01", 2020),
        ("Installed in 1999", 1999),
        ("Year=2015", 2015),
        ("1899", None),
        ("2101", None),
        ("abcd", None),
        ("", None),
        (None, None),
        (2024, 2024),
    ],
)
def test_extract_year(value, expected):
    assert mod.extract_year(value) == expected


@pytest.mark.parametrize(
    ("year_value", "expected"),
    [
        (1980, "pre_1990"),
        (1990, "pre_1990"),
        (1991, "1991_1992"),
        (1992, "1991_1992"),
        (1999, "1999_2000"),
        (2000, "1999_2000"),
        (2025, "2025_2026"),
        (2026, "2025_2026"),
        (2027, "unknown"),
        (None, "unknown"),
    ],
)
def test_year_to_bin(year_value, expected):
    assert mod.year_to_bin(year_value) == expected


def test_scan_root_returns_zero_dataframe_when_no_files(tmp_path):
    result = mod.scan_root(tmp_path)

    assert list(result.columns) == ["bin", "bin_MW", "cumulative_MW"]
    assert result["bin"].tolist() == mod.BIN_ORDER
    assert (result["bin_MW"] == 0.0).all()
    assert (result["cumulative_MW"] == 0.0).all()


def test_scan_root_returns_zero_dataframe_when_all_files_are_empty(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    file1 = root / "a.geojson"
    file1.write_text("x", encoding="utf-8")

    def fake_read_file(path):
        return pd.DataFrame()

    monkeypatch.setattr(mod.gpd, "read_file", fake_read_file)

    result = mod.scan_root(root)

    assert result["bin"].tolist() == mod.BIN_ORDER
    assert (result["bin_MW"] == 0.0).all()
    assert (result["cumulative_MW"] == 0.0).all()


def test_scan_root_skips_files_without_power_column(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    file1 = root / "a.geojson"
    file1.write_text("x", encoding="utf-8")

    def fake_read_file(path):
        return pd.DataFrame(
            [
                {"id": 1, "year": 2020},
                {"id": 2, "year": 2021},
            ]
        )

    monkeypatch.setattr(mod.gpd, "read_file", fake_read_file)

    result = mod.scan_root(root)

    assert result["bin"].tolist() == mod.BIN_ORDER
    assert (result["bin_MW"] == 0.0).all()
    assert (result["cumulative_MW"] == 0.0).all()


def test_scan_root_skips_reader_exceptions_and_continues(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    bad_file = root / "bad.geojson"
    good_file = root / "good.geojson"
    bad_file.write_text("x", encoding="utf-8")
    good_file.write_text("x", encoding="utf-8")

    def fake_read_file(path):
        if Path(path).name == "bad.geojson":
            raise ValueError("boom")
        return pd.DataFrame(
            [
                {"power_kw": 1000, "year": 2020},
            ]
        )

    monkeypatch.setattr(mod.gpd, "read_file", fake_read_file)

    result = mod.scan_root(root)

    row_2020 = result.loc[result["bin"] == "2019_2020"].iloc[0]
    assert row_2020["bin_MW"] == pytest.approx(1.0)
    assert row_2020["cumulative_MW"] == pytest.approx(1.0)


def test_scan_root_uses_first_matching_power_column_and_year_column(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    file1 = root / "a.geojson"
    file1.write_text("x", encoding="utf-8")

    df = pd.DataFrame(
        [
            {
                "power_kw": 1000,
                "Bruttoleistung": 999999,
                "year": 2020,
                "commissioning_date": "1990-01-01",
            },
            {
                "power_kw": 2000,
                "Bruttoleistung": 999999,
                "year": 2021,
                "commissioning_date": "1990-01-01",
            },
        ]
    )

    monkeypatch.setattr(mod.gpd, "read_file", lambda path: df)

    result = mod.scan_root(root)

    row_2019_2020 = result.loc[result["bin"] == "2019_2020"].iloc[0]
    row_2021_2022 = result.loc[result["bin"] == "2021_2022"].iloc[0]

    assert row_2019_2020["bin_MW"] == pytest.approx(1.0)
    assert row_2021_2022["bin_MW"] == pytest.approx(2.0)


def test_scan_root_aggregates_and_cumulates_correctly(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    (root / "a.geojson").write_text("x", encoding="utf-8")
    (root / "b.geojson").write_text("x", encoding="utf-8")

    data_by_file = {
        "a.geojson": pd.DataFrame(
            [
                {"power_kw": 1000, "year": 1990},
                {"power_kw": 2000, "year": 1991},
                {"power_kw": 3000, "year": 2020},
                {"power_kw": -5, "year": 2020},
                {"power_kw": "bad", "year": 2020},
            ]
        ),
        "b.geojson": pd.DataFrame(
            [
                {"power_kw": 4000, "year": 1992},
                {"power_kw": 5000, "year": 2021},
                {"power_kw": 6000, "year": None},
            ]
        ),
    }

    def fake_read_file(path):
        return data_by_file[Path(path).name]

    monkeypatch.setattr(mod.gpd, "read_file", fake_read_file)

    result = mod.scan_root(root)

    r_pre = result.loc[result["bin"] == "pre_1990"].iloc[0]
    r_91 = result.loc[result["bin"] == "1991_1992"].iloc[0]
    r_19 = result.loc[result["bin"] == "2019_2020"].iloc[0]
    r_21 = result.loc[result["bin"] == "2021_2022"].iloc[0]

    assert r_pre["bin_MW"] == pytest.approx(1.0)
    assert r_pre["cumulative_MW"] == pytest.approx(1.0)

    assert r_91["bin_MW"] == pytest.approx(6.0)
    assert r_91["cumulative_MW"] == pytest.approx(7.0)

    assert r_19["bin_MW"] == pytest.approx(3.0)
    assert r_19["cumulative_MW"] == pytest.approx(10.0)

    assert r_21["bin_MW"] == pytest.approx(5.0)
    assert r_21["cumulative_MW"] == pytest.approx(15.0)


def test_scan_root_supports_alternative_power_and_year_columns(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "geo"
    root.mkdir()
    (root / "a.geojson").write_text("x", encoding="utf-8")

    df = pd.DataFrame(
        [
            {"Bruttoleistung": 2500, "Inbetriebnahmedatum": "2015-03-01"},
            {"Bruttoleistung": 3500, "Inbetriebnahmedatum": "2016-07-01"},
        ]
    )

    monkeypatch.setattr(mod.gpd, "read_file", lambda path: df)

    result = mod.scan_root(root)

    row = result.loc[result["bin"] == "2015_2016"].iloc[0]
    assert row["bin_MW"] == pytest.approx(6.0)
    assert row["cumulative_MW"] >= 6.0


def test_main_prints_all_sections(monkeypatch, capsys):
    df1 = pd.DataFrame(
        {
            "bin": mod.BIN_ORDER,
            "bin_MW": [0.0] * len(mod.BIN_ORDER),
            "cumulative_MW": [1.0] * len(mod.BIN_ORDER),
        }
    )
    df2 = pd.DataFrame(
        {
            "bin": mod.BIN_ORDER,
            "bin_MW": [0.0] * len(mod.BIN_ORDER),
            "cumulative_MW": [2.0] * len(mod.BIN_ORDER),
        }
    )
    df3 = pd.DataFrame(
        {
            "bin": mod.BIN_ORDER,
            "bin_MW": [0.0] * len(mod.BIN_ORDER),
            "cumulative_MW": [3.0] * len(mod.BIN_ORDER),
        }
    )

    fake_results = {
        "1_state_yearly_3checks": df1,
        "2_state_landkreis_yearly": df2,
        "3_nationwide_landkreis_yearly": df3,
    }

    def fake_scan_root(root):
        for name, path in mod.INPUTS.items():
            if path == root:
                return fake_results[name]
        raise AssertionError("Unexpected root")

    monkeypatch.setattr(mod, "scan_root", fake_scan_root)

    mod.main()

    out = capsys.readouterr().out
    assert "--- 1_state_yearly_3checks ---" in out
    assert "--- 2_state_landkreis_yearly ---" in out
    assert "--- 3_nationwide_landkreis_yearly ---" in out
    assert "CONSISTENCY CHECK" in out
    assert "[INTERPRETATION]" in out
    assert "[DEBUG DONE]" in out