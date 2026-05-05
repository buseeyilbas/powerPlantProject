"""
Unit tests for step2_3_make_statewise_landkreis_pie_inputs_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_3_make_statewise_landkreis_pie_inputs_yearly as mod


def test_norm_basic():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Bayern Süd") == "bayern-sud"


def test_norm_none_and_spaces():
    assert mod.norm(None) == ""
    assert mod.norm("  Sachsen-Anhalt  ") == "sachsen-anhalt"


def test_parse_number_variants():
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.500,5") == 1500.5
    assert mod.parse_number(1000) == 1000.0


def test_parse_number_invalid_returns_none():
    assert mod.parse_number("abc") is None
    assert mod.parse_number(None) is None


def test_energy_norm_from_code():
    assert mod.energy_norm("2495") == "Photovoltaik"


def test_energy_norm_from_text():
    assert mod.energy_norm("solar") == "Photovoltaik"
    assert mod.energy_norm("windkraft") == "Windenergie Onshore"
    assert mod.energy_norm("hydro") == "Wasserkraft"
    assert mod.energy_norm("battery storage") == "Stromspeicher (Battery Storage)"
    assert mod.energy_norm("biogas") == "Biogas"


def test_energy_norm_from_filename_hint():
    assert mod.energy_norm(None, "my_pv_file.geojson") == "Photovoltaik"
    assert mod.energy_norm(None, "windkraft_2020.geojson") == "Windenergie Onshore"
    assert mod.energy_norm(None, "unknown_file.geojson") == "Unknown"


def test_extract_year_from_column():
    row = pd.Series({"commissioning_date": "2020-05-01"})
    assert mod.extract_year(row) == 2020


def test_extract_year_from_filename():
    row = pd.Series({})
    assert mod.extract_year(row, "plants_2019.geojson") == 2019


def test_extract_year_returns_none_when_missing():
    row = pd.Series({"commissioning_date": "not_a_date"})
    assert mod.extract_year(row, "plants_without_year.geojson") is None


def test_year_to_bin():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"
    assert "2019" in label


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"
    assert "Unknown" in label


def test_extract_ags5():
    row = pd.Series({"Gemeindeschluessel": "16055000"})
    assert mod.extract_ags5(row) == "16055"


def test_extract_ags5_from_alternative_column():
    row = pd.Series({"ags": "12 345 678"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_returns_none_when_missing():
    row = pd.Series({"foo": "bar"})
    assert mod.extract_ags5(row) is None


def test_scan_geojsons(tmp_path):
    (tmp_path / "a.geojson").write_text("{}", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.geojson").write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 2


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, state_map = mod.load_centers()

    assert centers["12345"] == (10.0, 50.0)
    assert state_map["12345"] == "bayern"


def test_load_centers_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")

    with pytest.raises(RuntimeError):
        mod.load_centers()


def test_main_returns_without_outputs_when_no_input_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    result = mod.main()

    assert result is None
    assert not out_dir.exists() or list(out_dir.rglob("*")) == []


def test_main_raises_when_input_root_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path / "missing")
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "centers.geojson")
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out_file = tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["state_slug"] == "bayern"
    assert row["kreis_key"] == "12345"
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["total_kw"] == pytest.approx(1000.0)

    state_file = (
        tmp_path
        / "out"
        / "bayern"
        / "2019_2020"
        / "de_bayern_landkreis_pies_2019_2020.geojson"
    )
    assert state_file.exists()

    meta_file = (
        tmp_path
        / "out"
        / "bayern"
        / "2019_2020"
        / "landkreis_pie_style_meta_2019_2020.json"
    )
    assert meta_file.exists()

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["state_slug"] == "bayern"
    assert meta["year_bin_slug"] == "2019_2020"
    assert meta["is_cumulative"] is True

    statewise_meta = tmp_path / "out" / "_STATEWISE_size_meta.json"
    assert statewise_meta.exists()

    legend_file = tmp_path / "out" / "de_energy_legend_points.geojson"
    assert legend_file.exists()

    yearly_totals_file = tmp_path / "out" / "de_yearly_totals.json"
    assert yearly_totals_file.exists()


def test_main_builds_cumulative_bins(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000", "12345000"],
            "power_kw": [1000, 500],
            "commissioning_date": ["2020", "2022"],
            "energy_source_label": ["solar", "wind"],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out_2019 = gpd.read_file(
        tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson"
    )
    out_2021 = gpd.read_file(
        tmp_path / "out" / "2021_2022" / "de_landkreis_pies_2021_2022.geojson"
    )

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
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000", "12345000", "12345000"],
            "power_kw": [1000, 2000, 300],
            "commissioning_date": ["2020", "2020", "2020"],
            "energy_source_label": ["2495", "2497", "2493"],
        },
        geometry=[Point(10, 50), Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["wind_kw"] == pytest.approx(2000.0)
    assert row["biogas_kw"] == pytest.approx(300.0)
    assert row["total_kw"] == pytest.approx(3300.0)


def test_main_puts_unknown_energy_into_others(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [700],
            "commissioning_date": ["2020"],
            "energy_source_label": ["something_unknown"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["others_kw"] == pytest.approx(700.0)
    assert row["total_kw"] == pytest.approx(700.0)


def test_main_skips_rows_with_unknown_center_ags(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["99999000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson").exists()


def test_main_uses_center_state_slug_not_folder_name(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "wrong_folder_name"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    state_file = (
        tmp_path
        / "out"
        / "bayern"
        / "2019_2020"
        / "de_bayern_landkreis_pies_2019_2020.geojson"
    )
    assert state_file.exists()


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000", "12345000"],
            "power_kw": [100, 200],
            "commissioning_date": ["2020", "2020"],
            "energy_source_label": ["2495", "2495"],
        },
        geometry=[
            MultiPoint([Point(10, 50), Point(10.1, 50.1)]),
            Point(10.2, 50.2),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(400.0)
    assert row["total_kw"] == pytest.approx(400.0)


def test_main_skips_non_positive_power_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000", "12345000", "12345000"],
            "power_kw": [0, -5, 10],
            "commissioning_date": ["2020", "2020", "2020"],
            "energy_source_label": ["2495", "2495", "2495"],
        },
        geometry=[Point(10, 50), Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    assert out.iloc[0]["total_kw"] == pytest.approx(10.0)


def test_main_skips_unknown_year_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["not_a_year"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "de_yearly_totals.json").exists()


def test_main_writes_one_state_meta_per_state(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    (input_root / "bayern").mkdir(parents=True)
    (input_root / "hessen").mkdir(parents=True)

    gdf_bayern = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf_bayern.to_file(input_root / "bayern" / "plants.geojson", driver="GeoJSON")

    gdf_hessen = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["54321000"],
            "power_kw": [500],
            "commissioning_date": ["2022"],
            "energy_source_label": ["2497"],
        },
        geometry=[Point(9, 51)],
        crs="EPSG:4326",
    )
    gdf_hessen.to_file(input_root / "hessen" / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345", "54321"],
            "state_slug": ["bayern", "hessen"],
        },
        geometry=[Point(10, 50), Point(9, 51)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    assert (tmp_path / "out" / "bayern" / "_STATE_META.json").exists()
    assert (tmp_path / "out" / "hessen" / "_STATE_META.json").exists()


def test_main_writes_chart_and_legend_outputs(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    assert (tmp_path / "out" / "de_yearly_totals_chart.geojson").exists()
    assert (tmp_path / "out" / "de_yearly_totals_chart_frame.geojson").exists()
    assert (tmp_path / "out" / "de_energy_legend_points.geojson").exists()
    assert (tmp_path / "out" / "de_state_totals_columnChart_bars.geojson").exists()
    assert (tmp_path / "out" / "de_state_totals_columnChart_labels.geojson").exists()
    assert (tmp_path / "out" / "de_state_totals_columnChart_frame.geojson").exists()


def test_main_writes_guides_when_chart_exists(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    mod.main()

    guides = tmp_path / "out" / "de_yearly_totals_chart_guides.geojson"
    assert guides.exists()


def test_main_writes_pie_size_legend_and_frames(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1_000_000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    mod.main()

    circles_path = out_dir / "de_pie_size_legend_circles.geojson"
    labels_path = out_dir / "de_pie_size_legend_labels.geojson"
    frames_path = out_dir / "de_legend_frames.geojson"

    assert circles_path.exists()
    assert labels_path.exists()
    assert frames_path.exists()

    circles = gpd.read_file(circles_path)
    labels = gpd.read_file(labels_path)
    frames = gpd.read_file(frames_path)

    assert len(circles) == len(mod.PIE_LEGEND_VALUES_GW)
    assert set(circles["legend_gw"]) == set(float(v) for v in mod.PIE_LEGEND_VALUES_GW)
    assert circles["radius_m"].min() >= mod.LEGEND_R_MIN_M
    assert circles["radius_m"].max() <= mod.LEGEND_R_MAX_M

    assert "title" in set(labels["kind"])
    assert mod.UNIFIED_TITLE_TEXT["pie_size_legend"] in set(labels["legend_label"])

    assert set(frames["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_main_energy_legend_has_title_and_expected_labels(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    mod.main()

    legend = gpd.read_file(out_dir / "de_energy_legend_points.geojson")

    assert "legend_title" in set(legend["energy_type"])
    assert mod.UNIFIED_TITLE_TEXT["energy_legend"] in set(legend["legend_label"])
    assert {"Photovoltaics", "Onshore Wind Energy", "Hydropower", "Biogas", "Battery", "Others"}.issubset(
        set(legend["legend_label"])
    )


def test_column_chart_labels_use_state_abbrev_not_only_numbers(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["12345000"],
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "energy_source_label": ["2495"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    mod.main()

    labels = gpd.read_file(out_dir / "de_state_totals_columnChart_labels.geojson")

    state_rows = labels[
        (labels["kind"] == "state_label")
        & (labels["state_number"] == 2)
    ]

    assert len(state_rows) >= 1
    assert set(state_rows["state_abbrev"]) == {"BY"}

    title_rows = labels[labels["kind"] == "title"]
    assert len(title_rows) == 1
    assert title_rows.iloc[0]["year_bin_label"] == mod.UNIFIED_TITLE_TEXT["column_chart"]


def test_radius_constants_match_manual_landkreis_setup():
    assert mod.R_MIN_M == 5000.0
    assert mod.R_MAX_M == 30000.0
    assert mod.LEGEND_R_MIN_M == 5000.0
    assert mod.LEGEND_R_MAX_M == 30000.0