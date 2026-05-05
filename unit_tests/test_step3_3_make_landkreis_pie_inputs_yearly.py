"""
Unit tests for step3_3_make_landkreis_pie_inputs_yearly.py
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

from piechart_layer_scripts import step3_3_make_landkreis_pie_inputs_yearly as mod


def test_norm_umlaut():
    assert mod.norm("Thüringen") == "thuringen"


def test_norm_none_and_spaces():
    assert mod.norm(None) == ""
    assert mod.norm("  Baden-Württemberg  ") == "baden-wurttemberg"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.000,5") == 1000.5


def test_parse_number_invalid_returns_none():
    assert mod.parse_number("abc") is None
    assert mod.parse_number(None) is None


def test_year_to_bin_basic():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"
    assert "2019" in label


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"
    assert "Unknown" in label


def test_extract_year_from_row():
    row = pd.Series({"commissioning_date": "2021-05-01"})
    assert mod.extract_year(row) == 2021


def test_extract_year_from_filename():
    row = pd.Series({})
    assert mod.extract_year(row, "plants_2018.geojson") == 2018


def test_extract_year_returns_none_when_missing():
    row = pd.Series({"commissioning_date": "not_a_date"})
    assert mod.extract_year(row, "plants_without_year.geojson") is None


def test_extract_ags5_from_row():
    row = pd.Series({"Gemeindeschluessel": "12345"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_from_alternative_column():
    row = pd.Series({"AGS": "12 345 678"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_returns_none_when_missing():
    row = pd.Series({"foo": "bar"})
    assert mod.extract_ags5(row) is None


def test_energy_norm_from_code():
    assert mod.energy_norm("2495") == "Photovoltaik"
    assert mod.energy_norm("2497") == "Windenergie Onshore"


def test_energy_norm_from_text():
    assert mod.energy_norm("Photovoltaik") == "Photovoltaik"
    assert mod.energy_norm("Solar") == "Photovoltaik"
    assert mod.energy_norm("Wind") == "Windenergie Onshore"
    assert mod.energy_norm("Hydro") == "Wasserkraft"
    assert mod.energy_norm("Battery Storage") == "Stromspeicher (Battery Storage)"
    assert mod.energy_norm("Biogas") == "Biogas"


def test_energy_norm_from_filename_hint():
    assert mod.energy_norm(None, "plants_pv.geojson") == "Photovoltaik"
    assert mod.energy_norm(None, "plants_battery.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.energy_norm(None, "plants_unknown.geojson") == "Unknown"


def test_scan_geojsons(tmp_path):
    f = tmp_path / "a.geojson"
    f.write_text("{}", encoding="utf-8")

    paths = list(mod.scan_geojsons(tmp_path))
    assert len(paths) == 1


def test_scan_geojsons_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")

    paths = list(mod.scan_geojsons(tmp_path))
    assert len(paths) == 2


def test_choose_label_prefers_most_common():
    labels = ["A", "A", "B"]
    assert mod.choose_label(labels) == "A"


def test_choose_label_prefers_longest_on_tie():
    labels = ["A", "Long Name", "A", "Long Name"]
    assert mod.choose_label(labels) == "Long Name"


def test_choose_label_empty():
    assert mod.choose_label([]) == ""
    assert mod.choose_label([None, ""]) == ""


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, state_map, name_map = mod.load_centers()

    assert centers["12345"] == (1.0, 2.0)
    assert state_map["12345"] == "bayern"
    assert name_map["12345"] == "A"


def test_load_centers_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")

    with pytest.raises(RuntimeError):
        mod.load_centers()


def test_first_power_column_direct():
    cols = ["a", "power_kw", "b"]
    assert mod.first_power_column(cols) == "power_kw"


def test_first_power_column_returns_none_when_missing():
    cols = ["a", "b", "c"]
    assert mod.first_power_column(cols) is None


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    file_path = input_root / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_file = tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["state_slug"] == "bayern"
    assert row["kreis_key"] == "12345"
    assert row["kreis_name"] == "A"
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["total_kw"] == pytest.approx(1000.0)

    state_file = (
        tmp_path / "out" / "bayern" / "2019_2020" / "de_bayern_landkreis_pies_2019_2020.geojson"
    )
    assert state_file.exists()

    meta_file = (
        tmp_path / "out" / "bayern" / "2019_2020" / "landkreis_pie_style_meta_2019_2020.json"
    )
    assert meta_file.exists()

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["state_slug"] == "bayern"
    assert meta["year_bin_slug"] == "2019_2020"
    assert meta["is_cumulative"] is True

    assert (tmp_path / "out" / "_GLOBAL_size_meta.json").exists()
    assert (tmp_path / "out" / "_STATEWISE_size_meta.json").exists()
    assert (tmp_path / "out" / "bayern" / "_STATE_META.json").exists()
    assert (tmp_path / "out" / "de_yearly_totals.json").exists()
    assert (tmp_path / "out" / "de_energy_legend_points.geojson").exists()


def test_main_builds_cumulative_bins(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 500],
            "commissioning_date": ["2020", "2022"],
            "Gemeindeschluessel": ["12345", "12345"],
            "energy_source_label": ["Photovoltaik", "Wind"],
        },
        geometry=[Point(1, 2), Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_2019 = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    out_2021 = gpd.read_file(tmp_path / "out" / "2021_2022" / "de_landkreis_pies_2021_2022.geojson")

    row_2019 = out_2019.iloc[0]
    row_2021 = out_2021.iloc[0]

    assert row_2019["pv_kw"] == pytest.approx(1000.0)
    assert row_2019["wind_kw"] == pytest.approx(0.0)
    assert row_2019["total_kw"] == pytest.approx(1000.0)

    assert row_2021["pv_kw"] == pytest.approx(1000.0)
    assert row_2021["wind_kw"] == pytest.approx(500.0)
    assert row_2021["total_kw"] == pytest.approx(1500.0)


def test_main_aggregates_multiple_energy_types(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 2000, 300],
            "commissioning_date": ["2020", "2020", "2020"],
            "Gemeindeschluessel": ["12345", "12345", "12345"],
            "energy_source_label": ["2495", "2497", "2493"],
        },
        geometry=[Point(1, 2), Point(1, 2), Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
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
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["something_unknown"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["others_kw"] == pytest.approx(700.0)
    assert row["total_kw"] == pytest.approx(700.0)


def test_main_skips_rows_with_unknown_center_ags(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["99999"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson").exists()


def test_main_skips_unknown_year_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["not_a_year"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "_GLOBAL_size_meta.json").exists()


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [100, 200],
            "commissioning_date": ["2020", "2020"],
            "Gemeindeschluessel": ["12345", "12345"],
            "energy_source_label": ["2495", "2495"],
        },
        geometry=[
            MultiPoint([Point(1, 2), Point(1.1, 2.1)]),
            Point(1.2, 2.2),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(400.0)
    assert row["total_kw"] == pytest.approx(400.0)


def test_main_skips_non_positive_power_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [0, -5, 10],
            "commissioning_date": ["2020", "2020", "2020"],
            "Gemeindeschluessel": ["12345", "12345", "12345"],
            "energy_source_label": ["2495", "2495", "2495"],
        },
        geometry=[Point(1, 2), Point(1, 2), Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "2019_2020" / "de_landkreis_pies_2019_2020.geojson")
    assert out.iloc[0]["total_kw"] == pytest.approx(10.0)


def test_main_skips_file_without_power_column(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "_GLOBAL_size_meta.json").exists()


def test_main_writes_one_state_meta_per_state(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 500],
            "commissioning_date": ["2020", "2022"],
            "Gemeindeschluessel": ["12345", "54321"],
            "energy_source_label": ["2495", "2497"],
        },
        geometry=[Point(1, 2), Point(3, 4)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345", "54321"],
            "state_slug": ["bayern", "hessen"],
            "kreis_name": ["A", "B"],
        },
        geometry=[Point(1, 2), Point(3, 4)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    assert (tmp_path / "out" / "bayern" / "_STATE_META.json").exists()
    assert (tmp_path / "out" / "hessen" / "_STATE_META.json").exists()


def test_main_writes_chart_and_legend_outputs(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_dir = tmp_path / "out"
    assert (out_dir / "de_yearly_totals.json").exists()
    assert (out_dir / "de_yearly_totals_chart.geojson").exists()
    assert (out_dir / "de_yearly_totals_chart_guides.geojson").exists()
    assert (out_dir / "de_yearly_totals_chart_frame.geojson").exists()
    assert (out_dir / "de_state_totals_columnChart_bars.geojson").exists()
    assert (out_dir / "de_state_totals_columnChart_labels.geojson").exists()
    assert (out_dir / "de_state_totals_columnChart_frame.geojson").exists()
    assert (out_dir / "de_energy_legend_points.geojson").exists()

def test_radius_and_legend_constants_match_current_step3_setup():
    assert mod.R_MIN_M == 10000.0
    assert mod.R_MAX_M == 50000.0
    assert mod.LEGEND_R_MIN_M == 10000.0
    assert mod.LEGEND_R_MAX_M == 50000.0
    assert mod.PIE_LEGEND_VALUES_GW == [0.5, 1, 2, 5]


def test_state_abbrev_mapping_contains_expected_codes():
    assert mod.STATE_SLUG_TO_ABBREV["bayern"] == "BY"
    assert mod.STATE_SLUG_TO_ABBREV["thueringen"] == "TH"
    assert mod.STATE_SLUG_TO_ABBREV["nordrhein-westfalen"] == "NW"


def test_write_pie_size_legend_outputs_scaled_gw_legend(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.write_pie_size_legend(global_min_kw=500_000.0, global_max_kw=5_000_000.0)

    circles_path = tmp_path / "de_pie_size_legend_circles.geojson"
    labels_path = tmp_path / "de_pie_size_legend_labels.geojson"

    assert circles_path.exists()
    assert labels_path.exists()

    circles = gpd.read_file(circles_path)
    labels = gpd.read_file(labels_path)

    assert len(circles) == len(mod.PIE_LEGEND_VALUES_GW)
    assert set(circles["legend_gw"]) == set(float(v) for v in mod.PIE_LEGEND_VALUES_GW)
    assert set(circles["legend_label"]) == {"0.5 GW", "1 GW", "2 GW", "5 GW"}

    assert circles["radius_m"].min() >= mod.LEGEND_R_MIN_M
    assert circles["radius_m"].max() <= mod.LEGEND_R_MAX_M

    title_rows = labels[labels["kind"] == "title"]
    assert len(title_rows) == 1
    assert title_rows.iloc[0]["legend_label"] == mod.UNIFIED_TITLE_TEXT["pie_size_legend"]


def test_write_legend_frames_outputs_energy_and_pie_frames(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.write_legend_frames()

    frames_path = tmp_path / "de_legend_frames.geojson"
    assert frames_path.exists()

    frames = gpd.read_file(frames_path)
    assert set(frames["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_main_writes_pie_size_legend_and_legend_frames(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [5_000_000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    assert (out_dir / "de_pie_size_legend_circles.geojson").exists()
    assert (out_dir / "de_pie_size_legend_labels.geojson").exists()
    assert (out_dir / "de_legend_frames.geojson").exists()

    circles = gpd.read_file(out_dir / "de_pie_size_legend_circles.geojson")
    labels = gpd.read_file(out_dir / "de_pie_size_legend_labels.geojson")
    frames = gpd.read_file(out_dir / "de_legend_frames.geojson")

    assert set(circles["legend_gw"]) == set(float(v) for v in mod.PIE_LEGEND_VALUES_GW)
    assert mod.UNIFIED_TITLE_TEXT["pie_size_legend"] in set(labels["legend_label"])
    assert set(frames["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_main_global_meta_uses_current_radius_constants(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [5_000_000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    meta = json.loads((out_dir / "_GLOBAL_size_meta.json").read_text(encoding="utf-8"))

    assert meta["r_min_m"] == mod.R_MIN_M
    assert meta["r_max_m"] == mod.R_MAX_M
    assert meta["r_min_m"] == 10000.0
    assert meta["r_max_m"] == 50000.0


def test_column_chart_labels_use_state_abbrev(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

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


def test_energy_legend_has_title_and_expected_labels(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020"],
            "Gemeindeschluessel": ["12345"],
            "energy_source_label": ["Photovoltaik"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    gdf.to_file(input_root / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(1, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    legend = gpd.read_file(out_dir / "de_energy_legend_points.geojson")

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