"""
Unit tests for step2_2_make_statewise_landkreis_pie_geometries.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_2_make_statewise_landkreis_pie_geometries as mod


def test_scale_linear_basic():
    val = mod.scale_linear(5, 0, 10, 0, 100)
    assert val == pytest.approx(50)


def test_scale_linear_clamps():
    assert mod.scale_linear(-10, 0, 10, 0, 100) == 0
    assert mod.scale_linear(20, 0, 10, 0, 100) == 100


def test_make_pie_basic():
    center = (0, 0)
    parts = [("pv_kw", 100), ("wind_kw", 100)]

    slices, anchor = mod.make_pie(center, 10, parts)

    assert len(slices) == 2
    assert anchor in ["pv_kw", "wind_kw"]


def test_make_pie_zero_total():
    center = (0, 0)
    parts = [("pv_kw", 0), ("wind_kw", 0)]

    slices, anchor = mod.make_pie(center, 10, parts)

    assert slices == []
    assert anchor is None


def test_repulse_centers_moves_overlap():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10},
        {"x": 0.0, "y": 0.0, "r": 10},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"]


def test_process_one_state_basic(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out_file = tmp_path / "de_bayern_landkreis_pie.geojson"
    assert out_file.exists()


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.main()

    out_file = tmp_path / "de_bayern_landkreis_pie.geojson"
    assert out_file.exists()