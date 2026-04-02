"""
Unit tests for step1_5_thueringen_state_pie_inputs_yearly.py
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon, MultiPoint

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_5_thueringen_state_pie_inputs_yearly as mod


def test_normalize_text():
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Saale-Holzland-Kreis") == "saale-holzland-kreis"


def test_normalize_text_none_and_spaces():
    assert mod.normalize_text(None) == ""
    assert mod.normalize_text("  Saalfeld-Rudolstadt  ") == "saalfeld-rudolstadt"


def test_parse_number():
    assert mod.parse_number("10,5") == 10.5
    assert mod.parse_number("1000") == 1000.0
    assert mod.parse_number("abc") is None


def test_parse_number_with_thousands_separator():
    assert mod.parse_number("1.234,56") == 1234.56
    assert mod.parse_number("1 234,56") == 1234.56
    assert mod.parse_number(42) == 42.0


def test_normalize_energy():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"


def test_normalize_energy_from_filename_hint():
    assert mod.normalize_energy(None, "my_pv_file.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "battery_storage_plants.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "unknown_file.geojson") == "Unknown"


def test_extract_year():
    row = {"commissioning_date": "2020-01-01"}
    assert mod.extract_year(row) == 2020


def test_extract_year_from_filename_hint():
    row = {}
    assert mod.extract_year(row, "plants_2018.geojson") == 2018


def test_extract_year_returns_none_when_missing():
    row = {"commissioning_date": "not_a_date"}
    assert mod.extract_year(row, "plants_without_year.geojson") is None


def test_year_to_bin():
    slug, _ = mod.year_to_bin(2020)
    assert slug == "2019_2020"


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"
    assert "Unknown" in label


def test_scan_geojsons(tmp_path):
    (tmp_path / "a.geojson").write_text("{}", encoding="utf-8")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 1


def test_scan_geojsons_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 2


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
    assert centers == {"a": (10.0, 50.0)}


def test_load_thueringen_centers_raises_when_missing_column(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    with pytest.raises(RuntimeError):
        mod.load_thueringen_centers()


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
    assert center == (10.0, 50.0)


def test_load_thueringen_center_prefers_polygon_file(tmp_path, monkeypatch):
    base = tmp_path

    poly = gpd.GeoDataFrame(
        {"state_name": ["Thüringen"]},
        geometry=[Polygon([(10, 50), (11, 50), (11, 51), (10, 51), (10, 50)])],
        crs="EPSG:4326",
    )
    poly.to_file(base / "thueringen_state_pie.geojson", driver="GeoJSON")

    pts = gpd.GeoDataFrame(
        geometry=[Point(99, 99)],
        crs="EPSG:4326",
    )
    pts.to_file(base / "thueringen_state_pies.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_FIXED", base)

    center = mod.load_thueringen_center()
    assert isinstance(center, tuple)
    assert center != (99.0, 99.0)


def test_load_thueringen_landkreis_polygons(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Thüringen"],
            "NAME_2": ["A"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )
    path = tmp_path / "gadm.json"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", path)

    result = mod.load_thueringen_landkreis_polygons()
    assert len(result) == 1
    assert "landkreis_slug" in result.columns
    assert result["landkreis_slug"].iloc[0] == "a"


def test_load_thueringen_landkreis_polygons_filters_to_thueringen(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Bayern", "Thüringen"],
            "NAME_2": ["X", "A"],
        },
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
            Polygon([(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)]),
        ],
        crs="EPSG:4326",
    )
    path = tmp_path / "gadm.json"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", path)

    result = mod.load_thueringen_landkreis_polygons()
    assert len(result) == 1
    assert result["landkreis_name"].iloc[0] == "A"


def test_pick_landkreis_from_row():
    row = pd.Series({"Landkreis": "A"})
    assert mod.pick_landkreis_from_row(row) == "A"


def test_pick_landkreis_from_row_returns_none():
    row = pd.Series({"foo": "bar"})
    assert mod.pick_landkreis_from_row(row) is None


def test_assign_kreis_slug_with_fallback_attribute_wins():
    pts = gpd.GeoDataFrame(
        {
            "Landkreis": ["A"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    poly = gpd.GeoDataFrame(
        {
            "landkreis_slug": ["different"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(pts, poly)
    assert result["kreis_slug"].iloc[0] == "a"


def test_assign_kreis_slug_with_fallback_polygon_fallback():
    pts = gpd.GeoDataFrame(
        {
            "Landkreis": [None],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )

    poly = gpd.GeoDataFrame(
        {
            "landkreis_slug": ["a"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(pts, poly)
    assert result["kreis_slug"].iloc[0] == "a"


def test_assign_kreis_slug_with_fallback_leaves_empty_when_no_match():
    pts = gpd.GeoDataFrame(
        {
            "Landkreis": [None],
        },
        geometry=[Point(5, 5)],
        crs="EPSG:4326",
    )

    poly = gpd.GeoDataFrame(
        {
            "landkreis_slug": ["a"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(pts, poly)
    assert result["kreis_slug"].iloc[0] == ""


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_raises_when_no_usable_features(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    bad = gpd.GeoDataFrame(
        {
            "foo": [1],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    bad.to_file(input_root / "bad.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path / "fixed")

    with pytest.raises(RuntimeError):
        mod.main()


# def test_main_basic(tmp_path, monkeypatch):
#     input_root = tmp_path / "input"
#     input_root.mkdir()

#     gdf = gpd.GeoDataFrame(
#         {
#             "power_kw": [1000],
#             "commissioning_date": ["2020"],
#             "Landkreis": ["A"],
#             "energy_source_label": ["2495"],
#         },
#         geometry=[Point(0.5, 0.5)],
#         crs="EPSG:4326",
#     )

#     file_path = input_root / "plants.geojson"
#     gdf.to_file(file_path, driver="GeoJSON")

#     centers = gpd.GeoDataFrame(
#         {"landkreis_slug": ["a"]},
#         geometry=[Point(0.5, 0.5)],
#         crs="EPSG:4326",
#     )
#     centers_path = tmp_path / "centers.geojson"
#     centers.to_file(centers_path, driver="GeoJSON")

#     poly = gpd.GeoDataFrame(
#         {
#             "NAME_1": ["Thüringen"],
#             "NAME_2": ["A"],
#         },
#         geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
#         crs="EPSG:4326",
#     )
#     poly_path = tmp_path / "gadm.json"
#     poly.to_file(poly_path, driver="GeoJSON")

#     fixed_base = tmp_path / "fixed"
#     fixed_base.mkdir()
#     fixed_center = gpd.GeoDataFrame(
#         {"state_name": ["Thüringen"]},
#         geometry=[Point(10.0, 50.0)],
#         crs="EPSG:4326",
#     )
#     fixed_center.to_file(fixed_base / "thueringen_state_pies.geojson", driver="GeoJSON")

#     monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
#     monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
#     monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
#     monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
#     monkeypatch.setattr(mod, "BASE_FIXED", fixed_base)

#     mod.main()

#     out_base = tmp_path / "out"
#     assert out_base.exists()

#     bin_file = out_base / "2019_2020" / "thueringen_state_pies_2019_2020.geojson"
#     assert bin_file.exists()

#     bin_gdf = gpd.read_file(bin_file)
#     assert len(bin_gdf) == 1
#     row = bin_gdf.iloc[0]
#     assert row["state_name"] == "Thüringen"
#     assert row["state_slug"] == "thueringen"
#     assert row["state_number"] == 16
#     assert row["pv_kw"] == pytest.approx(1000.0)
#     assert row["total_kw"] == pytest.approx(1000.0)

#     global_meta = out_base / "_GLOBAL_style_meta.json"
#     assert global_meta.exists()

#     meta_obj = json.loads(global_meta.read_text(encoding="utf-8"))
#     assert meta_obj["min_total_kw"] == pytest.approx(1000.0)
#     assert meta_obj["max_total_kw"] == pytest.approx(1000.0)

#     legend_path = out_base / "thueringen_energy_legend_points.geojson"
#     assert legend_path.exists()

#     chart_path = out_base / "thueringen_yearly_totals_chart.geojson"
#     assert chart_path.exists()

#     totals_path = out_base / "thueringen_yearly_totals.json"
#     assert totals_path.exists()


def test_main_uses_polygon_fallback_for_landkreis_assignment(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [500],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2497"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
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

    bin_file = tmp_path / "out" / "2019_2020" / "thueringen_state_pies_2019_2020.geojson"
    out = gpd.read_file(bin_file)
    assert out.iloc[0]["wind_kw"] == pytest.approx(500.0)
    assert out.iloc[0]["total_kw"] == pytest.approx(500.0)


def test_main_filters_out_rows_not_in_centers(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Landkreis": ["A"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {"landkreis_slug": ["different-slug"]},
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
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
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

    bin_file = tmp_path / "out" / "2019_2020" / "thueringen_state_pies_2019_2020.geojson"
    out = gpd.read_file(bin_file)
    assert out.iloc[0]["total_kw"] == pytest.approx(0.0)


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [100, 200],
            "commissioning_date": ["2020", "2020"],
            "Landkreis": ["A", "A"],
            "energy_source_label": ["2495", "2495"],
        },
        geometry=[
            MultiPoint([Point(0.2, 0.2), Point(0.3, 0.3)]),
            Point(0.4, 0.4),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])],
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

    bin_file = tmp_path / "out" / "2019_2020" / "thueringen_state_pies_2019_2020.geojson"
    out = gpd.read_file(bin_file)
    assert out.iloc[0]["pv_kw"] == pytest.approx(400.0)
    assert out.iloc[0]["total_kw"] == pytest.approx(400.0)


# def test_main_uses_mean_center_when_fixed_center_missing(tmp_path, monkeypatch):
#     input_root = tmp_path / "input"
#     input_root.mkdir()

#     gdf = gpd.GeoDataFrame(
#         {
#             "power_kw": [1000],
#             "commissioning_date": ["2020"],
#             "Landkreis": ["A"],
#             "energy_source_label": ["2495"],
#         },
#         geometry=[Point(1.0, 2.0)],
#         crs="EPSG:4326",
#     )
#     gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

#     centers = gpd.GeoDataFrame(
#         {"landkreis_slug": ["a"]},
#         geometry=[Point(1.0, 2.0)],
#         crs="EPSG:4326",
#     )
#     centers_path = tmp_path / "centers.geojson"
#     centers.to_file(centers_path, driver="GeoJSON")

#     poly = gpd.GeoDataFrame(
#         {
#             "NAME_1": ["Thüringen"],
#             "NAME_2": ["A"],
#         },
#         geometry=[Polygon([(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)])],
#         crs="EPSG:4326",
#     )
#     poly_path = tmp_path / "gadm.json"
#     poly.to_file(poly_path, driver="GeoJSON")

#     fixed_base = tmp_path / "fixed"
#     fixed_base.mkdir()

#     monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
#     monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
#     monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
#     monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
#     monkeypatch.setattr(mod, "BASE_FIXED", fixed_base)

#     mod.main()

#     bin_file = tmp_path / "out" / "2019_2020" / "thueringen_state_pies_2019_2020.geojson"
#     out = gpd.read_file(bin_file)
#     geom = out.geometry.iloc[0]
#     assert geom.x == pytest.approx(1.0)
#     assert geom.y == pytest.approx(2.0)