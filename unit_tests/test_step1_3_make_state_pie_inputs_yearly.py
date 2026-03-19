"""
Unit tests for step1_3_make_state_pie_inputs_yearly.py
"""

import sys
from pathlib import Path

import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_3_make_state_pie_inputs_yearly as mod


def test_normalize_text_basic():
    assert mod.normalize_text("Bayern") == "bayern"
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Nordrhein-Westfalen") == "nordrhein-westfalen"


def test_parse_number_valid():
    assert mod.parse_number("10") == 10.0
    assert mod.parse_number("10,5") == 10.5
    assert mod.parse_number("1.000,5") == 1000.5


def test_parse_number_invalid():
    assert mod.parse_number(None) is None
    assert mod.parse_number("abc") is None


def test_normalize_energy_from_code():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("2497") == "Windenergie Onshore"


def test_normalize_energy_from_text():
    assert mod.normalize_energy("solar") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"
    assert mod.normalize_energy("hydro") == "Wasserkraft"


def test_extract_year_from_string():
    row = {"commissioning_date": "2020-05-01"}
    assert mod.extract_year(row) == 2020


def test_extract_year_from_year_column():
    row = {"year": 2015}
    assert mod.extract_year(row) == 2015


def test_extract_year_from_filename():
    row = {}
    assert mod.extract_year(row, "plants_2018.geojson") == 2018


def test_year_to_bin_basic():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"


def test_scan_geojsons(tmp_path):
    root = tmp_path
    sub = root / "sub"
    sub.mkdir()

    (root / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")

    files = list(mod.scan_geojsons(root))
    assert len(files) == 2


def test_empty_parts_dict():
    d = mod.empty_parts_dict()
    assert "pv_kw" in d
    assert "others_kw" in d
    assert all(v == 0.0 for v in d.values())


def test_add_parts_inplace():
    a = mod.empty_parts_dict()
    b = mod.empty_parts_dict()

    b["pv_kw"] = 100
    mod.add_parts_inplace(a, b)

    assert a["pv_kw"] == 100


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic_flow(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    out_base = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path)

    mod.main()

    # check at least one bin output exists
    bins = list(out_base.glob("*"))
    assert len(bins) > 0


def test_main_skips_invalid_power(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [None],
            "commissioning_date": ["2020"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()