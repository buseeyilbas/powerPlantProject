"""
Unit tests for step1_6_thueringen_state_pie_geometries_yearly.py
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_6_thueringen_state_pie_geometries_yearly as mod


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


def test_pies_from_points_basic(tmp_path):
    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    out = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 2000, out)

    assert n > 0
    assert out.exists()


def test_pies_from_points_empty(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"state_name": []},
        geometry=[],
        crs="EPSG:4326",
    )

    out = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1, out)

    assert n == 0
    assert not out.exists()


def test_main_skips_missing_inputs(tmp_path, monkeypatch):
    base = tmp_path
    monkeypatch.setattr(mod, "BASE", base)

    # create empty bin dir
    (base / "bin1").mkdir()

    mod.main()  # should not crash


def test_main_basic(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    pts_path = bin_dir / "thueringen_state_pies_2019_2020.geojson"
    gdf.to_file(pts_path, driver="GeoJSON")

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
    }
    meta_path = bin_dir / "thueringen_state_pie_style_meta_2019_2020.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert out_file.exists()


def test_main_global_scaling(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    pts_path = bin_dir / "thueringen_state_pies_2019_2020.geojson"
    gdf.to_file(pts_path, driver="GeoJSON")

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
    }
    meta_path = bin_dir / "thueringen_state_pie_style_meta_2019_2020.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    global_meta = {
        "min_total_kw": 0,
        "max_total_kw": 5000,
    }
    global_meta_path = base / "_GLOBAL_style_meta.json"
    global_meta_path.write_text(json.dumps(global_meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)
    monkeypatch.setattr(mod, "GLOBAL_META", global_meta_path)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert out_file.exists()