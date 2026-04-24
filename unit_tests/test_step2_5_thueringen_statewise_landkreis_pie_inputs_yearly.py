"""
Unit tests for step2_5_thueringen_statewise_landkreis_pie_inputs_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_5_thueringen_statewise_landkreis_pie_inputs_yearly as mod


def test_norm_umlaut():
    assert mod.norm("Thüringen") == "thuringen"


def test_norm_none_and_spaces():
    assert mod.norm(None) == ""
    assert mod.norm("  Saale-Holzland-Kreis  ") == "saale-holzland-kreis"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.234,5") == 1234.5


def test_parse_number_invalid_returns_none():
    assert mod.parse_number("abc") is None
    assert mod.parse_number(None) is None


def test_year_to_bin():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"
    assert "2019" in label


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"
    assert "Unknown" in label


def test_normalize_energy_from_text():
    assert mod.normalize_energy("Solar") == "Photovoltaik"
    assert mod.normalize_energy("Wind") == "Windenergie Onshore"
    assert mod.normalize_energy("Hydro") == "Wasserkraft"
    assert mod.normalize_energy("Battery Storage") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("Biogas") == "Biogas"


def test_normalize_energy_from_code():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("2497") == "Windenergie Onshore"


def test_normalize_energy_from_filename():
    assert mod.normalize_energy(None, "plants_pv.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "plants_battery.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "plants_unknown.geojson") == "Unknown"


def test_extract_year_from_column():
    row = pd.Series({"commissioning_date": "2020-01-15"})
    assert mod.extract_year(row) == 2020


def test_extract_year_from_filename():
    row = pd.Series({})
    assert mod.extract_year(row, "plants_2018.geojson") == 2018


def test_extract_year_returns_none_when_missing():
    row = pd.Series({"commissioning_date": "not_a_date"})
    assert mod.extract_year(row, "plants_without_year.geojson") is None


def test_ensure_point_geometries_keeps_points_and_multipoints():
    gdf = gpd.GeoDataFrame(
        {"a": [1, 2, 3]},
        geometry=[
            Point(0, 0),
            MultiPoint([Point(1, 1), Point(2, 2)]),
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        ],
        crs="EPSG:4326",
    )

    result = mod.ensure_point_geometries(gdf)
    assert len(result) == 2
    assert set(result.geometry.geom_type) == {"Point", "MultiPoint"}


def test_pick_first_nonempty():
    row = pd.Series({"foo": "", "bar": "A"})
    assert mod.pick_first_nonempty(row, ["foo", "bar"]) == "A"


def test_pick_first_nonempty_returns_none():
    row = pd.Series({"foo": "", "bar": None})
    assert mod.pick_first_nonempty(row, ["foo", "bar"]) is None


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


def test_assign_kreis_slug_leaves_empty_when_no_match():
    gdf = gpd.GeoDataFrame(
        {"Landkreis": [None]},
        geometry=[Point(5, 5)],
        crs="EPSG:4326",
    )

    polys = gpd.GeoDataFrame(
        {"kreis_slug": ["a"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )

    result = mod.assign_kreis_slug_with_fallback(gdf, polys)

    assert result.loc[0, "kreis_slug"] == ""


def test_load_thueringen_centers_accepts_schema_variants(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "landkreis_slug": ["a"],
            "landkreis_name": ["A"],
            "landkreis_number": [1],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, names, numbers = mod.load_thueringen_centers()
    assert centers["a"] == (10.0, 50.0)
    assert names["a"] == "A"
    assert numbers["a"] == 1


def test_load_thueringen_centers_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")

    with pytest.raises(FileNotFoundError):
        mod.load_thueringen_centers()


def test_load_gadm_l2_thueringen_polys_filters_state(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "NAME_1": ["Bayern", "Thüringen"],
            "NAME_2": ["X", "A"],
        },
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 2), (3, 2), (3, 3), (2, 3)]),
        ],
        crs="EPSG:4326",
    )
    path = tmp_path / "gadm.json"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "GADM_L2_PATH", path)

    out = mod.load_gadm_l2_thueringen_polys()
    assert len(out) == 1
    assert out.iloc[0]["kreis_slug"] == "a"


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
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out_dir = tmp_path / "out"
    assert out_dir.exists()

    bin_file = out_dir / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson"
    assert bin_file.exists()

    out = gpd.read_file(bin_file)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["state_name"] == "Thüringen"
    assert row["state_slug"] == "thueringen"
    assert row["state_number"] == 16
    assert row["kreis_slug"] == "a"
    assert row["kreis_key"] == "a"
    assert row["kreis_name"] == "A"
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["total_kw"] == pytest.approx(1000.0)

    assert (out_dir / "_THUERINGEN_GLOBAL_style_meta.json").exists()
    assert (out_dir / "thueringen_landkreis_yearly_totals.json").exists()
    assert (out_dir / "thueringen_landkreis_yearly_totals_chart.geojson").exists()
    assert (out_dir / "thueringen_landkreis_yearly_totals_chart_frame.geojson").exists()
    assert (out_dir / "thueringen_landkreis_energy_legend_points.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_bars.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_labels.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_frame.geojson").exists()


def test_main_builds_cumulative_bins(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 500],
            "commissioning_date": ["2020", "2022"],
            "Landkreis": ["A", "A"],
            "energy_source_label": ["Solar", "Wind"],
        },
        geometry=[Point(0.5, 0.5), Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out_2019 = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    out_2021 = gpd.read_file(tmp_path / "out" / "2021_2022" / "thueringen_landkreis_pies_2021_2022.geojson")

    row_2019 = out_2019.iloc[0]
    row_2021 = out_2021.iloc[0]

    assert row_2019["pv_kw"] == pytest.approx(1000.0)
    assert row_2019["wind_kw"] == pytest.approx(0.0)
    assert row_2019["total_kw"] == pytest.approx(1000.0)

    assert row_2021["pv_kw"] == pytest.approx(1000.0)
    assert row_2021["wind_kw"] == pytest.approx(500.0)
    assert row_2021["total_kw"] == pytest.approx(1500.0)


def test_main_aggregates_multiple_energy_types_into_correct_fields(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 2000, 300],
            "commissioning_date": ["2020", "2020", "2020"],
            "Landkreis": ["A", "A", "A"],
            "energy_source_label": ["2495", "2497", "2493"],
        },
        geometry=[Point(0.5, 0.5), Point(0.5, 0.5), Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["wind_kw"] == pytest.approx(2000.0)
    assert row["biogas_kw"] == pytest.approx(300.0)
    assert row["total_kw"] == pytest.approx(3300.0)


def test_main_puts_unknown_energy_into_others(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [700],
            "commissioning_date": ["2020"],
            "Landkreis": ["A"],
            "energy_source_label": ["something_unknown"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["others_kw"] == pytest.approx(700.0)
    assert row["total_kw"] == pytest.approx(700.0)


def test_main_uses_spatial_fallback_for_kreis_assignment(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [500],
            "commissioning_date": ["2020"],
            "energy_source_label": ["Wind"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    assert out.iloc[0]["wind_kw"] == pytest.approx(500.0)
    assert out.iloc[0]["kreis_slug"] == "a"


def test_main_filters_out_rows_not_in_centers(tmp_path, monkeypatch):
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
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "kreis_slug": ["different"],
            "kreis_name": ["A"],
            "kreis_number": [1],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    poly = gpd.GeoDataFrame(
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_keeps_multipoint_without_exploding(tmp_path, monkeypatch):
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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(300.0)
    assert row["total_kw"] == pytest.approx(300.0)


def test_ensure_point_geometries_keeps_multipoint_without_exploding():
    gdf = gpd.GeoDataFrame(
        {"value": [1, 2]},
        geometry=[
            MultiPoint([Point(0, 0), Point(1, 1)]),
            Point(2, 2),
        ],
        crs="EPSG:4326",
    )

    out = mod.ensure_point_geometries(gdf)

    assert len(out) == 2
    assert list(out.geometry.geom_type) == ["MultiPoint", "Point"]


def test_main_skips_non_positive_power_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [0, -5, 10],
            "commissioning_date": ["2020", "2020", "2020"],
            "Landkreis": ["A", "A", "A"],
            "energy_source_label": ["2495", "2495", "2495"],
        },
        geometry=[Point(0.5, 0.5), Point(0.5, 0.5), Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "thueringen_landkreis_pies_2019_2020.geojson")
    assert out.iloc[0]["total_kw"] == pytest.approx(10.0)


def test_main_skips_unknown_year_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["not_a_year"],
            "Landkreis": ["A"],
            "energy_source_label": ["Solar"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_writes_guides_and_chart_outputs(tmp_path, monkeypatch):
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
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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
        {"NAME_1": ["Thüringen"], "NAME_2": ["A"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    poly_path = tmp_path / "gadm.json"
    poly.to_file(poly_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "out" / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    out_dir = tmp_path / "out"
    assert (out_dir / "thueringen_landkreis_yearly_totals_chart.geojson").exists()
    assert (out_dir / "thueringen_landkreis_yearly_totals_chart_guides.geojson").exists()
    assert (out_dir / "thueringen_landkreis_yearly_totals_chart_frame.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_bars.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_labels.geojson").exists()
    assert (out_dir / "thu_landkreis_totals_columnChart_frame.geojson").exists()
    assert (out_dir / "thueringen_landkreis_energy_legend_points.geojson").exists()


def test_radius_constants_match_manual_thueringen_landkreis_setup():
    assert mod.LEGEND_R_MIN_M == 9000.0
    assert mod.LEGEND_R_MAX_M == 20000.0
    assert mod.PIE_LEGEND_VALUES_MW == [8, 400]


def test_write_pie_size_legend_outputs_scaled_mw_legend(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path)

    mod.write_pie_size_legend(global_min_kw=8_000.0, global_max_kw=400_000.0)

    circles_path = tmp_path / "thueringen_pie_size_legend_circles.geojson"
    labels_path = tmp_path / "thueringen_pie_size_legend_labels.geojson"

    assert circles_path.exists()
    assert labels_path.exists()

    circles = gpd.read_file(circles_path)
    labels = gpd.read_file(labels_path)

    assert len(circles) == len(mod.PIE_LEGEND_VALUES_MW)
    assert set(circles["legend_mw"]) == {8.0, 400.0}
    assert set(circles["legend_label"]) == {"8 MW", "400 MW"}

    assert circles["radius_m"].min() >= mod.LEGEND_R_MIN_M
    assert circles["radius_m"].max() <= mod.LEGEND_R_MAX_M

    title_rows = labels[labels["kind"] == "title"]
    assert len(title_rows) == 1
    assert title_rows.iloc[0]["legend_label"] == mod.UNIFIED_TITLE_TEXT["pie_size_legend"]


def test_write_legend_frames_outputs_energy_and_pie_frames(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path)

    mod.write_legend_frames()

    frames_path = tmp_path / "thueringen_legend_frames.geojson"
    assert frames_path.exists()

    frames = gpd.read_file(frames_path)
    assert set(frames["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_main_writes_pie_size_legend_and_legend_frames(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [400_000],
            "commissioning_date": ["2020"],
            "Landkreis": ["A"],
            "energy_source_label": ["Solar"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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

    out_base = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", out_base / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    circles_path = out_base / "thueringen_pie_size_legend_circles.geojson"
    labels_path = out_base / "thueringen_pie_size_legend_labels.geojson"
    frames_path = out_base / "thueringen_legend_frames.geojson"

    assert circles_path.exists()
    assert labels_path.exists()
    assert frames_path.exists()

    circles = gpd.read_file(circles_path)
    labels = gpd.read_file(labels_path)
    frames = gpd.read_file(frames_path)

    assert set(circles["legend_mw"]) == set(float(v) for v in mod.PIE_LEGEND_VALUES_MW)
    assert "title" in set(labels["kind"])
    assert mod.UNIFIED_TITLE_TEXT["pie_size_legend"] in set(labels["legend_label"])
    assert set(frames["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_main_global_meta_uses_current_radius_constants(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [400_000],
            "commissioning_date": ["2020"],
            "Landkreis": ["A"],
            "energy_source_label": ["Solar"],
        },
        geometry=[Point(0.5, 0.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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

    out_base = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", out_base / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    meta = json.loads((out_base / "_THUERINGEN_GLOBAL_style_meta.json").read_text(encoding="utf-8"))

    assert meta["radius_min_m"] == mod.LEGEND_R_MIN_M
    assert meta["radius_max_m"] == mod.LEGEND_R_MAX_M
    assert meta["radius_min_m"] == 9000.0
    assert meta["radius_max_m"] == 20000.0


def test_main_energy_legend_has_title_and_expected_labels(tmp_path, monkeypatch):
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
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

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

    out_base = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "GADM_L2_PATH", poly_path)
    monkeypatch.setattr(mod, "GLOBAL_META", out_base / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    legend = gpd.read_file(out_base / "thueringen_landkreis_energy_legend_points.geojson")

    assert "legend_title" in set(legend["energy_type"])
    assert mod.UNIFIED_TITLE_TEXT["energy_legend"] in set(legend["legend_label"])
    assert {
        "Photovoltaics",
        "Onshore Wind Energy",
        "Hydropower",
        "Biogas",
        "Battery",
        "Others",
    }.issubset(set(legend["legend_label"]))