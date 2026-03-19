"""
Unit tests for step2_1_make_statewise_landkreis_pie_inputs.py
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_1_make_statewise_landkreis_pie_inputs as mod


def test_norm():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Saale-Holzland-Kreis") == "saale-holzland-kreis"


def test_clean_kreis_label():
    assert mod.clean_kreis_label("Landkreis Weimarer Land") == "Weimarer Land"
    assert mod.clean_kreis_label("kreisfreie stadt Jena") == "Jena"


def test_extract_ags5():
    row = pd.Series({"Gemeindeschluessel": "09670000"})
    assert mod.extract_ags5(row) == "09670"


def test_parse_number():
    assert mod.parse_number("10,5") == 10.5
    assert mod.parse_number("1000") == 1000.0
    assert mod.parse_number("abc") is None


def test_normalize_energy():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"


def test_scan_geojsons(tmp_path):
    (tmp_path / "a.geojson").write_text("{}", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 1


def test_first_power_column():
    cols = ["abc", "power_kw", "xyz"]
    assert mod.first_power_column(cols) == "power_kw"


def test_choose_label():
    labels = ["A", "A", "B"]
    assert mod.choose_label(labels) == "A"


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, states, names = mod.load_centers()

    assert "09670" in centers
    assert states["09670"] == "bayern"


def test_main_returns_without_writing_when_no_input_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [1000],
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_files = list((tmp_path / "out").glob("*.geojson"))
    assert len(out_files) == 1

    meta_files = list((tmp_path / "out").glob("*.json"))
    assert len(meta_files) == 1