"""
Unit tests for step0_make_thueringen_landkreis_centers.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step0_make_thueringen_landkreis_centers as mod


def test_norm_basic_cases():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Thuringia") == "thuringia"
    assert mod.norm("Baden-Württemberg") == "baden-wurttemberg"
    assert mod.norm("Nordrhein Westfalen") == "nordrhein-westfalen"
    assert mod.norm(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Thüringen", True),
        ("Thueringen", True),
        ("Thuringen", True),
        ("Thuringia", True),
        ("Freistaat Thüringen", True),
        ("State of Thuringia", True),
        ("Bayern", False),
        ("Berlin", False),
        (None, False),
    ],
)
def test_is_thueringen_state(value, expected):
    assert mod.is_thueringen_state(value) is expected


def test_safe_name():
    assert mod.safe_name("Jena") == "Jena"
    assert mod.safe_name("  Weimar  ") == "Weimar"
    assert mod.safe_name("") == "unknown"
    assert mod.safe_name(None) == "unknown"
    assert mod.safe_name(None, fallback="fallback") == "fallback"


def test_shift_inward_returns_point_within_polygon():
    poly = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    pt = mod.shift_inward(poly)

    assert isinstance(pt, Point)
    assert pt.within(poly)


def test_shift_inward_falls_back_to_representative_point_for_tiny_polygon():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    pt = mod.shift_inward(poly)

    assert isinstance(pt, Point)
    assert pt.within(poly)


def test_main_creates_thueringen_centers_geojson(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l2.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen", "Thuringia", "Bayern"],
            "NAME_2": ["Jena", "Weimar", "München"],
            "GID_1": ["DEU.16_1", "DEU.16_1", "DEU.09_1"],
            "GID_2": ["DEU.16.1_1", "DEU.16.2_1", "DEU.09.1_1"],
            "HASC_2": ["DE.TH.JE", "DE.TH.WE", "DE.BY.MU"],
        },
        geometry=[
            Polygon([(10.8, 50.8), (11.2, 50.8), (11.2, 51.2), (10.8, 51.2)]),
            Polygon([(11.2, 50.8), (11.6, 50.8), (11.6, 51.2), (11.2, 51.2)]),
            Polygon([(11.0, 48.0), (11.5, 48.0), (11.5, 48.5), (11.0, 48.5)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    assert out_path.exists()

    out = gpd.read_file(out_path)
    assert len(out) == 2
    assert sorted(out["landkreis_name"].tolist()) == ["Jena", "Weimar"]
    assert sorted(out["landkreis_slug"].tolist()) == ["jena", "weimar"]
    assert sorted(out["state_name"].tolist()) == ["Thüringen", "Thüringen"]
    assert sorted(out["state_slug"].tolist()) == ["thueringen", "thueringen"]
    assert sorted(out["gid_1"].tolist()) == ["DEU.16_1", "DEU.16_1"]
    assert sorted(out["gid_2"].tolist()) == ["DEU.16.1_1", "DEU.16.2_1"]
    assert sorted(out["hasc_2"].tolist()) == ["DE.TH.JE", "DE.TH.WE"]
    assert all(out.geometry.geom_type == "Point")


def test_main_skips_empty_geometries_and_still_writes_valid_centers(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l2.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen", "Thüringen"],
            "NAME_2": ["Valid LK", "Empty LK"],
        },
        geometry=[
            Polygon([(10.8, 50.8), (11.2, 50.8), (11.2, 51.2), (10.8, 51.2)]),
            None,
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    out = gpd.read_file(out_path)
    assert len(out) == 1
    assert out.iloc[0]["landkreis_name"] == "Valid LK"


def test_main_raises_when_gadm_file_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "missing.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    monkeypatch.setattr(mod, "GADM_L2_PATH", missing_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="GADM L2 file not found"):
        mod.main()


def test_main_raises_when_required_fields_missing(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l2.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "WRONG_STATE": ["Thüringen"],
            "WRONG_LK": ["Jena"],
        },
        geometry=[Polygon([(10.8, 50.8), (11.2, 50.8), (11.2, 51.2), (10.8, 51.2)])],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="Expected fields missing in GADM L2"):
        mod.main()


def test_main_raises_when_no_thueringen_rows_found(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l2.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Bayern", "Berlin"],
            "NAME_2": ["München", "Berlin"],
        },
        geometry=[
            Polygon([(11.0, 48.0), (11.5, 48.0), (11.5, 48.5), (11.0, 48.5)]),
            Polygon([(13.0, 52.3), (13.7, 52.3), (13.7, 52.7), (13.0, 52.7)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="No Thüringen rows found in GADM L2"):
        mod.main()


def test_main_raises_when_no_centers_produced(tmp_path, monkeypatch):
    gadm_path = tmp_path / "gadm_l2.geojson"
    out_dir = tmp_path / "out"
    out_path = out_dir / "thueringen_landkreis_centers.geojson"

    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen"],
            "NAME_2": ["Jena"],
        },
        geometry=[None],
        crs="EPSG:4326",
    )
    gdf.to_file(gadm_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", gadm_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "OUT_PATH", out_path)

    with pytest.raises(RuntimeError, match="No centers produced"):
        mod.main()