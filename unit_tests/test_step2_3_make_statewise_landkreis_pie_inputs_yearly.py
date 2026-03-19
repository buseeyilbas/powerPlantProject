import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_3_make_statewise_landkreis_pie_inputs_yearly as mod


def test_norm_basic():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Bayern Süd") == "bayern-sud"


def test_parse_number_variants():
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.500,5") == 1500.5
    assert mod.parse_number(1000) == 1000.0


def test_energy_norm_from_code():
    assert mod.energy_norm("2495") == "Photovoltaik"


def test_energy_norm_from_text():
    assert mod.energy_norm("solar") == "Photovoltaik"
    assert mod.energy_norm("windkraft") == "Windenergie Onshore"


def test_extract_year_from_column():
    row = pd.Series({"commissioning_date": "2020-05-01"})
    assert mod.extract_year(row) == 2020


def test_extract_year_from_filename():
    row = pd.Series({})
    assert mod.extract_year(row, "plants_2019.geojson") == 2019


def test_year_to_bin():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"
    assert "2019" in label


def test_extract_ags5():
    row = pd.Series({"Gemeindeschluessel": "16055000"})
    assert mod.extract_ags5(row) == "16055"


def test_scan_geojsons(tmp_path):
    (tmp_path / "a.geojson").write_text("{}", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.geojson").write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 2


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, state_map = mod.load_centers()

    assert centers["12345"] == (10.0, 50.0)
    assert state_map["12345"] == "bayern"


def test_main_returns_without_outputs_when_no_input_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    result = mod.main()

    assert result is None
    assert not out_dir.exists() or list(out_dir.rglob("*")) == []


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out_file = (
        tmp_path
        / "out"
        / "2019_2020"
        / "de_landkreis_pies_2019_2020.geojson"
    )

    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert out.iloc[0]["total_kw"] == 1000