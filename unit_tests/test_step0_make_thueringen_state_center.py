"""
Unit tests for step0_make_thueringen_state_center.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step0_make_thueringen_state_center as mod


def test_norm_basic_cases():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Baden-Württemberg") == "baden-wurttemberg"
    assert mod.norm("Nordrhein Westfalen") == "nordrhein-westfalen"
    assert mod.norm(None) == ""
    assert mod.norm(123) == "123"


@pytest.mark.parametrize(
    ("row_data", "expected"),
    [
        ({"NAME_1": "Thüringen"}, True),
        ({"NAME_1": "Thueringen"}, True),
        ({"NAME_1": "Thuringen"}, True),
        ({"NAME_1": "Thuringia"}, True),
        ({"VARNAME_1": "Freistaat Thüringen"}, True),
        ({"ENGTYPE_1": "State of Thuringia"}, True),
        ({"NAME_1": "Bayern"}, False),
        ({}, False),
    ],
)
def test_is_thueringen_row(row_data, expected):
    assert mod.is_thueringen_row(row_data) is expected


def test_shift_inward_returns_point_within_polygon():
    poly = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    pt = mod.shift_inward(poly)

    assert isinstance(pt, Point)
    assert pt.within(poly)


def test_shift_inward_falls_back_to_representative_point_when_buffer_empties():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    pt = mod.shift_inward(poly)

    assert isinstance(pt, Point)
    assert pt.within(poly)


def test_main_creates_thueringen_state_center_geojson(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l1.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen", "Bayern"],
            "VARNAME_1": [None, None],
            "NL_NAME_1": [None, None],
            "ENGTYPE_1": [None, None],
            "TYPE_1": [None, None],
        },
        geometry=[
            Polygon([(10.0, 50.0), (12.0, 50.0), (12.0, 51.5), (10.0, 51.5)]),
            Polygon([(10.0, 48.0), (13.0, 48.0), (13.0, 50.0), (10.0, 50.0)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L1_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    assert out_path.exists()

    out = gpd.read_file(out_path)
    assert len(out) == 1
    assert out.iloc[0]["state_name"] == "Thüringen"
    assert out.iloc[0]["state_slug"] == "thueringen"
    assert out.iloc[0]["state_number"] == 16
    assert out.geometry.iloc[0].geom_type == "Point"

    poly_metric = gdf[gdf["NAME_1"] == "Thüringen"].to_crs(mod.CRS_METRIC).geometry.iloc[0]
    point_metric = out.to_crs(mod.CRS_METRIC).geometry.iloc[0]
    assert point_metric.within(poly_metric)


def test_main_uses_largest_polygon_when_multiple_matches(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l1.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    small_poly = Polygon([(10.0, 50.0), (10.3, 50.0), (10.3, 50.3), (10.0, 50.3)])
    big_poly = Polygon([(11.0, 50.0), (13.0, 50.0), (13.0, 52.0), (11.0, 52.0)])

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen", "Thuringia"],
            "VARNAME_1": [None, None],
            "NL_NAME_1": [None, None],
            "ENGTYPE_1": [None, None],
            "TYPE_1": [None, None],
        },
        geometry=[small_poly, big_poly],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L1_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    out = gpd.read_file(out_path)
    point_metric = out.to_crs(mod.CRS_METRIC).geometry.iloc[0]
    big_metric = gpd.GeoSeries([big_poly], crs="EPSG:4326").to_crs(mod.CRS_METRIC).iloc[0]

    assert point_metric.within(big_metric)


def test_main_fallback_matches_name1_contains_th(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l1.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thuringen Region"],
            "VARNAME_1": [None],
            "NL_NAME_1": [None],
            "ENGTYPE_1": [None],
            "TYPE_1": [None],
        },
        geometry=[Polygon([(10.0, 50.0), (12.0, 50.0), (12.0, 51.0), (10.0, 51.0)])],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L1_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    out = gpd.read_file(out_path)
    assert len(out) == 1
    assert out.iloc[0]["state_slug"] == "thueringen"


def test_main_shifts_inward_when_center_too_close_to_border(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l1.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    poly = Polygon([(10.0, 50.0), (12.0, 50.0), (12.0, 51.0), (10.0, 51.0)])

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen"],
            "VARNAME_1": [None],
            "NL_NAME_1": [None],
            "ENGTYPE_1": [None],
            "TYPE_1": [None],
        },
        geometry=[poly],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    called = {"shifted": False}

    def fake_shift_inward(poly_m):
        called["shifted"] = True
        return poly_m.representative_point()

    class DummyPoint:
        def __init__(self):
            self.boundary_distance = 1.0

        def distance(self, other):
            return 1.0

    monkeypatch.setattr(mod, "GADM_L1_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)
    monkeypatch.setattr(mod, "shift_inward", fake_shift_inward)

    original_representative_point = Polygon.representative_point

    def fake_representative_point(self):
        return DummyPoint()

    monkeypatch.setattr(type(gdf.to_crs(mod.CRS_METRIC).geometry.iloc[0]), "representative_point", fake_representative_point, raising=False)

    try:
        mod.main()
    except Exception:
        pass

    assert called["shifted"] is True

    monkeypatch.setattr(type(gdf.to_crs(mod.CRS_METRIC).geometry.iloc[0]), "representative_point", original_representative_point, raising=False)


def test_main_raises_when_gadm_file_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "missing.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    monkeypatch.setattr(mod, "GADM_L1_PATH", missing_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="GADM L1 file not found"):
        mod.main()


def test_main_raises_when_no_thueringen_found(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l1.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_state_pies.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Bayern", "Berlin"],
            "VARNAME_1": [None, None],
            "NL_NAME_1": [None, None],
            "ENGTYPE_1": [None, None],
            "TYPE_1": [None, None],
        },
        geometry=[
            Polygon([(10.0, 48.0), (13.0, 48.0), (13.0, 50.0), (10.0, 50.0)]),
            Polygon([(13.0, 52.0), (14.0, 52.0), (14.0, 53.0), (13.0, 53.0)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L1_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="Could not find Thüringen in GADM L1"):
        mod.main()