"""
Unit tests for step1_2_make_state_pie_geometries.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_2_make_state_pie_geometries as mod


def test_meters_per_deg():
    lon, lat = mod.meters_per_deg(50)
    assert lon > 0
    assert lat == pytest.approx(111320.0)


def test_circle_point_returns_valid_coords():
    x, y = mod.circle_point(10.0, 50.0, 1000, 0)
    assert isinstance(x, float)
    assert isinstance(y, float)


def test_slice_polygon_returns_polygon():
    poly = mod.slice_polygon(10.0, 50.0, 1000, 0, 1.0, n=10)
    assert poly.is_valid
    assert poly.geom_type == "Polygon"


def test_linear_radius_basic():
    r = mod.linear_radius(50, 0, 100)
    assert mod.MIN_RADIUS_M <= r <= mod.MAX_RADIUS_M


def test_linear_radius_edge_case_same_min_max():
    r = mod.linear_radius(50, 100, 100)
    expected = (mod.MIN_RADIUS_M + mod.MAX_RADIUS_M) / 2
    assert r == expected


def test_repel_centers_moves_overlapping_points():
    pts = [(10.0, 50.0), (10.0, 50.0)]
    result = mod.repel_centers(pts)

    assert result[0] != result[1]


def test_repel_centers_no_change_when_far():
    pts = [(10.0, 50.0), (20.0, 60.0)]
    result = mod.repel_centers(pts)

    assert result == [[10.0, 50.0], [20.0, 60.0]]


def test_main_creates_output(tmp_path, monkeypatch):
    base = tmp_path
    in_file = base / "de_state_pies.geojson"
    meta_file = base / "state_pie_style_meta.json"
    out_file = base / "de_state_pie.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A", "B"],
            "total_kw": [1000, 2000],
            "pv_kw": [500, 1000],
            "wind_kw": [500, 1000],
            "battery_kw": [0, 0],
            "hydro_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
        },
        geometry=[Point(10, 50), Point(11, 51)],
        crs="EPSG:4326",
    )
    gdf.to_file(in_file, driver="GeoJSON")

    meta_file.write_text(
        '{"min_total_kw": 1000, "max_total_kw": 2000}',
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "IN_FILE", in_file)
    monkeypatch.setattr(mod, "META_FILE", meta_file)
    monkeypatch.setattr(mod, "OUT_FILE", out_file)

    mod.main()

    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) > 0
    assert all(out.geometry.geom_type == "Polygon")
    assert "energy_type" in out.columns


def test_main_raises_for_zero_total_only(tmp_path, monkeypatch):
    base = tmp_path
    in_file = base / "de_state_pies.geojson"
    out_file = base / "de_state_pie.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A"],
            "total_kw": [0],
            "pv_kw": [0],
            "wind_kw": [0],
            "battery_kw": [0],
            "hydro_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(in_file, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "IN_FILE", in_file)
    monkeypatch.setattr(mod, "OUT_FILE", out_file)

    with pytest.raises(ValueError, match="Unknown column geometry"):
        mod.main()


def test_main_raises_when_input_missing(tmp_path, monkeypatch):
    base = tmp_path
    in_file = base / "missing.geojson"
    out_file = base / "out.geojson"

    monkeypatch.setattr(mod, "IN_FILE", in_file)
    monkeypatch.setattr(mod, "OUT_FILE", out_file)

    with pytest.raises(FileNotFoundError):
        mod.main()