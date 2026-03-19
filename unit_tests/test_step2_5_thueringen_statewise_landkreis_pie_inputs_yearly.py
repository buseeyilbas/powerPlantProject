import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_5_thueringen_statewise_landkreis_pie_inputs_yearly as mod


def test_norm_umlaut():
    assert mod.norm("Thüringen") == "thuringen"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.234,5") == 1234.5


def test_year_to_bin():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"


def test_normalize_energy_from_text():
    assert mod.normalize_energy("Solar") == "Photovoltaik"
    assert mod.normalize_energy("Wind") == "Windenergie Onshore"


def test_assign_kreis_slug_attribute_only():
    gdf = gpd.GeoDataFrame(
        {"Landkreis": ["A"]},
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    polys = gpd.GeoDataFrame(
        {"kreis_slug": ["a"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(gdf, polys)

    assert result.loc[0, "kreis_slug"] == "a"


def test_assign_kreis_slug_spatial_fallback():
    gdf = gpd.GeoDataFrame(
        {"Landkreis": [None]},
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    polys = gpd.GeoDataFrame(
        {"kreis_slug": ["a"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(gdf, polys)

    assert result.loc[0, "kreis_slug"] == "a"


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
            "Landkreis": ["A"],
            "energy_source_label": ["Solar"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    file_path = input_root / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "kreis_slug": ["a"],
            "kreis_name": ["A"],
            "kreis_number": [1],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    poly = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen"],
            "NAME_2": ["A"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)

    mod.main()

    out_dir = tmp_path / "out"
    assert out_dir.exists()

    bins = list(out_dir.glob("*/thueringen_landkreis_pies_*.geojson"))
    assert len(bins) > 0