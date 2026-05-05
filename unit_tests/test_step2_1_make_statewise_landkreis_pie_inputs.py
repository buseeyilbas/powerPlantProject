"""
Unit tests for step2_1_make_statewise_landkreis_pie_inputs.py
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

from piechart_layer_scripts import step2_1_make_statewise_landkreis_pie_inputs as mod


def test_norm():
    assert mod.norm("Thüringen") == "thuringen"
    assert mod.norm("Saale-Holzland-Kreis") == "saale-holzland-kreis"


def test_norm_none_and_spaces():
    assert mod.norm(None) == ""
    assert mod.norm("  Jena  ") == "jena"


def test_clean_kreis_label():
    assert mod.clean_kreis_label("Landkreis Weimarer Land") == "Weimarer Land"
    assert mod.clean_kreis_label("kreisfreie stadt Jena") == "Jena"


def test_clean_kreis_label_empty():
    assert mod.clean_kreis_label("") == ""
    assert mod.clean_kreis_label(None) == ""


def test_extract_ags5():
    row = pd.Series({"Gemeindeschluessel": "09670000"})
    assert mod.extract_ags5(row) == "09670"


def test_extract_ags5_from_alternative_column():
    row = pd.Series({"ags": "12 345 678"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_returns_none_when_missing():
    row = pd.Series({"foo": "bar"})
    assert mod.extract_ags5(row) is None


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
    assert mod.normalize_energy(None, "battery_storage.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "unknown.geojson") == "Unknown"


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


def test_first_power_column():
    cols = ["abc", "power_kw", "xyz"]
    assert mod.first_power_column(cols) == "power_kw"


def test_first_power_column_finds_fuzzy_match():
    cols = ["abc", "Bruttoleistung (kW)", "xyz"]
    assert mod.first_power_column(cols) == "Bruttoleistung (kW)"


def test_first_power_column_returns_none_when_missing():
    cols = ["abc", "def"]
    assert mod.first_power_column(cols) is None


def test_choose_label():
    labels = ["A", "A", "B"]
    assert mod.choose_label(labels) == "A"


def test_choose_label_prefers_longest_on_tie():
    labels = ["Jena", "Stadt Jena", "Jena", "Stadt Jena"]
    assert mod.choose_label(labels) == "Stadt Jena"


def test_choose_label_empty():
    assert mod.choose_label([]) == ""
    assert mod.choose_label([None, ""]) == ""


def test_load_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, states, names = mod.load_centers()

    assert centers["09670"] == (10.0, 50.0)
    assert states["09670"] == "bayern"
    assert names["09670"] == "A"


def test_load_centers_sets_crs_when_missing(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    ).set_crs(None, allow_override=True)

    path = tmp_path / "centers.geojson"
    gdf.to_file(path, driver="GeoJSON")

    monkeypatch.setattr(mod, "CENTERS_PATH", path)

    centers, _, _ = mod.load_centers()
    assert centers["09670"] == (10.0, 50.0)


def test_load_centers_raises_when_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")

    with pytest.raises(RuntimeError):
        mod.load_centers()


def test_main_returns_without_writing_when_no_input_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    out_dir = tmp_path / "out"

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not out_dir.exists() or list(out_dir.iterdir()) == []


def test_main_raises_when_input_root_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path / "missing")
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "centers.geojson")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [1000],
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out_file = tmp_path / "out" / "de_bayern_landkreis_pies.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["state_slug"] == "bayern"
    assert row["kreis_key"] == "09670"
    assert row["kreis_name"] == "A"
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["wind_kw"] == pytest.approx(0.0)
    assert row["others_kw"] == pytest.approx(0.0)
    assert row["total_kw"] == pytest.approx(1000.0)

    meta_file = tmp_path / "out" / "bayern_landkreis_pie_style_meta.json"
    assert meta_file.exists()

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["min_total_kw"] == pytest.approx(1000.0)
    assert meta["max_total_kw"] == pytest.approx(1000.0)
    assert meta["name_field"] == "kreis_name"


def test_main_aggregates_multiple_energy_types(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000", "09670000", "09670000"],
            "power_kw": [1000, 2000, 300],
            "Energietraeger": ["2495", "2497", "2493"],
            "Landkreis": ["A", "A", "A"],
        },
        geometry=[Point(10, 50), Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_bayern_landkreis_pies.geojson")
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
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [700],
            "Energietraeger": ["something_unknown"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_bayern_landkreis_pies.geojson")
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
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "de_bayern_landkreis_pies.geojson").exists()


def test_main_uses_center_state_slug_not_folder_name(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "wrong_folder_name"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [1000],
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    assert (tmp_path / "out" / "de_bayern_landkreis_pies.geojson").exists()


def test_main_prefers_attribute_label_over_center_label(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [1000],
            "Energietraeger": ["2495"],
            "Landkreis": ["Landkreis Weimarer Land"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["Center Label"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_bayern_landkreis_pies.geojson")
    assert out.iloc[0]["kreis_name"] == "Weimarer Land"


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000", "09670000"],
            "power_kw": [100, 200],
            "Energietraeger": ["2495", "2495"],
            "Landkreis": ["A", "A"],
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
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_bayern_landkreis_pies.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(400.0)
    assert row["total_kw"] == pytest.approx(400.0)


def test_main_skips_file_without_power_column(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    result = mod.main()

    assert result is None
    assert not (tmp_path / "out" / "de_bayern_landkreis_pies.geojson").exists()


def test_main_skips_non_positive_power_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000", "09670000", "09670000"],
            "power_kw": [0, -5, 10],
            "Energietraeger": ["2495", "2495", "2495"],
            "Landkreis": ["A", "A", "A"],
        },
        geometry=[Point(10, 50), Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670"],
            "state_slug": ["bayern"],
            "kreis_name": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_bayern_landkreis_pies.geojson")
    assert out.iloc[0]["total_kw"] == pytest.approx(10.0)


def test_main_writes_one_file_per_state(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    (input_root / "bayern").mkdir(parents=True)
    (input_root / "hessen").mkdir(parents=True)

    gdf_bayern = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["09670000"],
            "power_kw": [1000],
            "Energietraeger": ["2495"],
            "Landkreis": ["A"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf_bayern.to_file(input_root / "bayern" / "plants.geojson", driver="GeoJSON")

    gdf_hessen = gpd.GeoDataFrame(
        {
            "Gemeindeschluessel": ["06431000"],
            "power_kw": [500],
            "Energietraeger": ["2497"],
            "Landkreis": ["B"],
        },
        geometry=[Point(9, 51)],
        crs="EPSG:4326",
    )
    gdf_hessen.to_file(input_root / "hessen" / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["09670", "06431"],
            "state_slug": ["bayern", "hessen"],
            "kreis_name": ["A", "B"],
        },
        geometry=[Point(10, 50), Point(9, 51)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)

    mod.main()

    assert (tmp_path / "out" / "de_bayern_landkreis_pies.geojson").exists()
    assert (tmp_path / "out" / "de_hessen_landkreis_pies.geojson").exists()
    assert (tmp_path / "out" / "bayern_landkreis_pie_style_meta.json").exists()
    assert (tmp_path / "out" / "hessen_landkreis_pie_style_meta.json").exists()