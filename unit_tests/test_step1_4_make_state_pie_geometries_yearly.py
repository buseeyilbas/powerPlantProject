"""
Unit tests for step1_4_make_state_pie_geometries_yearly.py
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_4_make_state_pie_geometries_yearly as mod


def test_scale_linear_basic():
    val = mod.scale_linear(50, 0, 100, 10, 20)
    assert 10 <= val <= 20


def test_scale_linear_edge():
    val = mod.scale_linear(50, 100, 100, 10, 20)
    assert val == 15


def test_ring_pts_returns_points():
    pts = mod.ring_pts((0, 0), 10, 0, 1)
    assert len(pts) > 0
    assert isinstance(pts[0], tuple)


def test_make_pie_basic():
    center = (0, 0)
    radius = 10
    parts = [("pv_kw", 50), ("wind_kw", 50)]

    slices, anchor = mod.make_pie(center, radius, parts)

    assert len(slices) == 2
    assert anchor in ["pv_kw", "wind_kw"]


def test_make_pie_zero_total():
    slices, anchor = mod.make_pie((0, 0), 10, [("pv_kw", 0)])
    assert slices == []
    assert anchor is None


def test_repulse_centers_moves_overlap():
    centers = [
        {"x": 0, "y": 0, "r": 10},
        {"x": 0, "y": 0, "r": 10},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"] or centers[0]["y"] != centers[1]["y"]


def test_pies_from_points_basic(tmp_path):
    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [500],
            "wind_kw": [500],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
            "year_bin_label": ["2020"],
            "year_bin_slug": ["2019_2020"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    out_path = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1000, out_path)

    assert n > 0
    assert out_path.exists()

    out = gpd.read_file(out_path)
    assert len(out) > 0
    assert "energy_type" in out.columns


def test_main_skips_missing_bins(tmp_path, monkeypatch):
    base = tmp_path

    monkeypatch.setattr(mod, "BASE", base)

    # empty base → nothing happens but no crash
    mod.main()


def test_main_basic(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    pts = bin_dir / "de_state_pies_2019_2020.geojson"
    meta = bin_dir / "state_pie_style_meta_2019_2020.json"

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
            "year_bin_label": ["2019–2020"],
            "year_bin_slug": ["2019_2020"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(pts, driver="GeoJSON")

    meta.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 1000}), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out = bin_dir / "de_state_pie_2019_2020.geojson"
    assert out.exists()


def test_main_with_global_meta(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    pts = bin_dir / "de_state_pies_2019_2020.geojson"
    meta = bin_dir / "state_pie_style_meta_2019_2020.json"
    global_meta = base / "_GLOBAL_style_meta.json"

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [1000],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
            "year_bin_label": ["2019–2020"],
            "year_bin_slug": ["2019_2020"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(pts, driver="GeoJSON")

    meta.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 500}), encoding="utf-8")
    global_meta.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 1000}), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_META", global_meta)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)

    mod.main()

    out = bin_dir / "de_state_pie_2019_2020.geojson"
    assert out.exists()