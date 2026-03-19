import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_3_make_landkreis_pie_inputs_yearly as mod


def test_norm_umlaut():
    assert mod.norm("Thüringen") == "thuringen"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.000,5") == 1000.5


def test_year_to_bin_basic():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"


def test_extract_year_from_row():
    row = pd.Series({"commissioning_date": "2021-05-01"})
    assert mod.extract_year(row) == 2021


def test_scan_geojsons(tmp_path):
    f = tmp_path / "a.geojson"
    f.write_text("{}", encoding="utf-8")

    paths = list(mod.scan_geojsons(tmp_path))
    assert len(paths) == 1


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, state_map, name_map = mod.load_centers()

    assert centers["12345"] == (1.0, 2.0)
    assert state_map["12345"] == "bayern"
    assert name_map["12345"] == "A"


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    file_path = input_root / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_file = tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson"
    assert out_file.exists()