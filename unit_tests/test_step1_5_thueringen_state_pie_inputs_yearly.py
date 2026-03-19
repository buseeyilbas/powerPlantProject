"""
Unit tests for step1_5_thueringen_state_pie_inputs_yearly.py
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_5_thueringen_state_pie_inputs_yearly as mod


def test_normalize_text():
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Saale-Holzland-Kreis") == "saale-holzland-kreis"


def test_parse_number():
    assert mod.parse_number("10,5") == 10.5
    assert mod.parse_number("1000") == 1000.0
    assert mod.parse_number("abc") is None


def test_normalize_energy():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"


def test_extract_year():
    row = {"commissioning_date": "2020-01-01"}
    assert mod.extract_year(row) == 2020


def test_year_to_bin():
    slug, _ = mod.year_to_bin(2020)
    assert slug == "2019_2020"


def test_scan_geojsons(tmp_path):
    (tmp_path / "a.geojson").write_text("{}", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 1


def test_load_thueringen_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"landkreis_slug": ["a"]},
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers = mod.load_thueringen_centers()
    assert "a" in centers


def test_load_thueringen_center_fallback(tmp_path, monkeypatch):
    pts = gpd.GeoDataFrame(
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    base = tmp_path
    pts.to_file(base / "thueringen_state_pies.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_FIXED", base)

    center = mod.load_thueringen_center()
    assert isinstance(center, tuple)


def test_load_thueringen_landkreis_polygons(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen"],
            "NAME_2": ["A"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    path = tmp_path / "gadm.json"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", path)

    result = mod.load_thueringen_landkreis_polygons()
    assert len(result) == 1


def test_assign_kreis_slug_with_fallback(tmp_path):
    pts = gpd.GeoDataFrame(
        {
            "Landkreis": ["A"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    poly = gpd.GeoDataFrame(
        {
            "landkreis_slug": ["a"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(pts, poly)
    assert result["kreis_slug"].iloc[0] == "a"


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
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    file_path = input_root / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {"landkreis_slug": ["a"]},
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

    fixed_base = tmp_path / "fixed"
    fixed_base.mkdir()
    fixed_center = gpd.GeoDataFrame(
        {"state_name": ["Thüringen"]},
        geometry=[Point(10.0, 50.0)],
        crs="EPSG:4326",
    )
    fixed_center.to_file(fixed_base / "thueringen_state_pies.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed_base)

    mod.main()

    out_dirs = list((tmp_path / "out").glob("*"))
    assert len(out_dirs) > 0