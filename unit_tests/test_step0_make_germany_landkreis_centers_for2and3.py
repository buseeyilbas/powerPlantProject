"""
Unit tests for step0_make_germany_landkreis_centers_for2and3.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step0_make_germany_landkreis_centers_for2and3 as mod


@pytest.fixture
def sample_polygon():
    return Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])


def test_norm_basic_cases():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Baden-Württemberg") == "baden-wurttemberg"
    assert mod.norm("Nordrhein Westfalen") == "nordrhein-westfalen"
    assert mod.norm(None) == ""
    assert mod.norm(123) == "123"


def test_clean_kreis_label_basic_cases():
    assert mod.clean_kreis_label("Landkreis Weimarer Land") == "Weimarer Land"
    assert mod.clean_kreis_label("kreisfreie stadt Jena") == "Jena"
    assert mod.clean_kreis_label("Saale-Holzland-Kreis") == "Saale-holzland-"
    assert mod.clean_kreis_label("") == ""
    assert mod.clean_kreis_label(None) == ""


def test_extract_ags5_from_supported_fields():
    assert mod.extract_ags5({"Gemeindeschluessel": "09670000"}) == "09670"
    assert mod.extract_ags5({"gemeindeschluessel": "16055000"}) == "16055"
    assert mod.extract_ags5({"AGS": "09162000"}) == "09162"
    assert mod.extract_ags5({"ags": "09 162 000"}) == "09162"
    assert mod.extract_ags5({"ags_id": "16055"}) == "16055"
    assert mod.extract_ags5({"kreisschluessel": "16055"}) == "16055"
    assert mod.extract_ags5({"rs": "160550000000"}) == "16055"


def test_extract_ags5_returns_none_for_missing_or_short_values():
    assert mod.extract_ags5({"Gemeindeschluessel": ""}) is None
    assert mod.extract_ags5({"AGS": "1234"}) is None
    assert mod.extract_ags5({}) is None


def test_scan_geojsons_finds_geojsons_recursively(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()

    (root / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.GEOJSON").write_text("{}", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")

    found = sorted(p.relative_to(root).as_posix() for p in mod.scan_geojsons(root))
    assert found == ["a.geojson", "sub/b.GEOJSON"]


def test_choose_label_prefers_most_common_then_longest():
    assert mod.choose_label(["Jena", "Jena", "Weimar"]) == "Jena"
    assert mod.choose_label(["AB", "CD"]) == "AB"
    assert mod.choose_label(["A", "Longer"]) == "Longer"
    assert mod.choose_label(["", None, ""]) == ""
    assert mod.choose_label([]) == ""


def test_shift_inward_returns_point_within_polygon(sample_polygon):
    pt = mod.shift_inward(sample_polygon)
    assert isinstance(pt, Point)
    assert pt.within(sample_polygon)


def test_main_creates_centers_geojson(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    polygons_path = tmp_path / "gadm_l2.geojson"
    centers_dir = tmp_path / "centers"
    centers_path = centers_dir / "de_landkreis_centers.geojson"

    gadm_gdf = gpd.GeoDataFrame(
        {
            "NAME_2": ["Kreis A", "Kreis B"],
        },
        geometry=[
            Polygon([(10.0, 49.0), (11.0, 49.0), (11.0, 50.0), (10.0, 50.0)]),
            Polygon([(11.0, 50.0), (12.0, 50.0), (12.0, 51.0), (11.0, 51.0)]),
        ],
        crs="EPSG:4326",
    )
    gadm_gdf.to_file(polygons_path, driver="GeoJSON")

    plant_gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000", "16055000"],
            "Landkreis": ["Landkreis A", "Landkreis B"],
        },
        geometry=[Point(10.5, 49.5), Point(11.5, 50.5)],
        crs="EPSG:4326",
    )
    plant_gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "LANDKREIS_POLYGONS_PATH", polygons_path)
    monkeypatch.setattr(mod, "CENTERS_DIR", centers_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    assert centers_path.exists()

    out = gpd.read_file(centers_path)
    assert len(out) == 2
    assert sorted(out["ags5"].tolist()) == ["09670", "16055"]
    assert sorted(out["kreis_name"].tolist()) == ["A", "B"]
    assert sorted(out["state_name"].tolist()) == ["Bayern", "Bayern"]
    assert all(out.geometry.geom_type == "Point")


def test_main_uses_representative_point_when_average_point_outside_polygon(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "thueringen"
    state_dir.mkdir(parents=True)

    polygons_path = tmp_path / "gadm_l2.geojson"
    centers_dir = tmp_path / "centers"
    centers_path = centers_dir / "de_landkreis_centers.geojson"

    u_shape = Polygon(
        [
            (0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4), (0, 0)
        ]
    )
    gadm_gdf = gpd.GeoDataFrame(
        {"NAME_2": ["Kreis U"]},
        geometry=[u_shape],
        crs="EPSG:4326",
    )
    gadm_gdf.to_file(polygons_path, driver="GeoJSON")

    plant_gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["16055000", "16055001"],
            "Landkreis": ["Kreis U", "Kreis U"],
        },
        geometry=[Point(3.5, 0.5), Point(0.5, 3.5)],
        crs="EPSG:4326",
    )
    plant_gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "LANDKREIS_POLYGONS_PATH", polygons_path)
    monkeypatch.setattr(mod, "CENTERS_DIR", centers_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "DEBUG_PRINT", False)

    mod.main()

    out = gpd.read_file(centers_path)
    assert len(out) == 1
    poly_metric = gadm_gdf.to_crs(mod.CRS_METRIC).geometry.iloc[0]
    center_metric = out.to_crs(mod.CRS_METRIC).geometry.iloc[0]
    assert center_metric.within(poly_metric)


def test_main_raises_when_polygon_file_missing(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    missing_polygons = tmp_path / "missing.geojson"
    centers_dir = tmp_path / "centers"
    centers_path = centers_dir / "de_landkreis_centers.geojson"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "LANDKREIS_POLYGONS_PATH", missing_polygons)
    monkeypatch.setattr(mod, "CENTERS_DIR", centers_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    with pytest.raises(RuntimeError, match="GADM polygons not found"):
        mod.main()