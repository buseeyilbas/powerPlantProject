"""
Unit tests for step3_1_make_landkreis_pie_inputs.py
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

from piechart_layer_scripts import step3_1_make_landkreis_pie_inputs as mod


def test_normalize_text_basic():
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Hello World!") == "hello world"


def test_normalize_text_none_and_spaces():
    assert mod.normalize_text(None) == ""
    assert mod.normalize_text("  Bayern Süd  ") == "bayern sud"


def test_normalize_energy_from_code():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("2497") == "Windenergie Onshore"


def test_normalize_energy_from_text():
    assert mod.normalize_energy("Solar") == "Photovoltaik"
    assert mod.normalize_energy("Wind") == "Windenergie Onshore"
    assert mod.normalize_energy("Hydro") == "Wasserkraft"
    assert mod.normalize_energy("Battery Storage") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("Biogas") == "Biogas"


def test_normalize_energy_from_filename_hint():
    assert mod.normalize_energy(None, "plants_pv.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "plants_battery.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "plants_unknown.geojson") == "Unknown"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.234,5") == 1234.5


def test_parse_number_invalid_returns_none():
    assert mod.parse_number("abc") is None
    assert mod.parse_number(None) is None


def test_extract_ags5():
    row = pd.Series({"AGS": "12345678"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_from_alternative_column():
    row = pd.Series({"gemeindeschluessel": "12 345 678"})
    assert mod.extract_ags5(row) == "12345"


def test_extract_ags5_returns_none_when_missing():
    row = pd.Series({"foo": "bar"})
    assert mod.extract_ags5(row) is None


def test_first_power_column_direct():
    cols = ["a", "power_kw", "b"]
    assert mod.first_power_column(cols) == "power_kw"


def test_first_power_column_fallback():
    cols = ["Leistung_total"]
    assert mod.first_power_column(cols) == "Leistung_total"


def test_first_power_column_returns_none():
    cols = ["a", "b", "c"]
    assert mod.first_power_column(cols) is None


def test_scan_geojsons(tmp_path):
    f = tmp_path / "a.geojson"
    f.write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 1
    assert files[0].name == "a.geojson"


def test_scan_geojsons_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 2


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)
    monkeypatch.setattr(mod, "CENTERS_PATH", tmp_path / "missing.geojson")
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "energy_source_label": ["Solar"],
            "AGS": ["12345"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out_dir = tmp_path / "out"
    assert out_dir.exists()

    nationwide = out_dir / "de_landkreis_pies.geojson"
    assert nationwide.exists()

    g = gpd.read_file(nationwide)
    assert len(g) == 1
    row = g.iloc[0]
    assert row["kreis_key"] == "12345"
    assert row["kreis_name"] == "Testkreis"
    assert row["state_slug"] == "test"
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["total_kw"] == pytest.approx(1000.0)

    meta_file = out_dir / "landkreis_pie_style_meta.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["min_total_kw"] == pytest.approx(1000.0)
    assert meta["max_total_kw"] == pytest.approx(1000.0)
    assert meta["name_field"] == "kreis_name"

    per_state = out_dir / "test" / "de_test_landkreis_pies.geojson"
    assert per_state.exists()


def test_main_aggregates_multiple_energy_types(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 2000, 300],
            "energy_source_label": ["2495", "2497", "2493"],
            "AGS": ["12345", "12345", "12345"],
        },
        geometry=[Point(0, 0), Point(0, 0), Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_landkreis_pies.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(1000.0)
    assert row["wind_kw"] == pytest.approx(2000.0)
    assert row["biogas_kw"] == pytest.approx(300.0)
    assert row["total_kw"] == pytest.approx(3300.0)


def test_main_puts_unknown_energy_into_others(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [700],
            "energy_source_label": ["something_unknown"],
            "AGS": ["12345"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_landkreis_pies.geojson")
    row = out.iloc[0]
    assert row["others_kw"] == pytest.approx(700.0)
    assert row["total_kw"] == pytest.approx(700.0)


def test_main_skips_unknown_ags_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "energy_source_label": ["Solar"],
            "AGS": ["99999"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_skips_non_positive_power_rows(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [0, -5, 10],
            "energy_source_label": ["Solar", "Solar", "Solar"],
            "AGS": ["12345", "12345", "12345"],
        },
        geometry=[Point(0, 0), Point(0, 0), Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_landkreis_pies.geojson")
    assert out.iloc[0]["total_kw"] == pytest.approx(10.0)


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [100, 200],
            "energy_source_label": ["2495", "2495"],
            "AGS": ["12345", "12345"],
        },
        geometry=[
            MultiPoint([Point(0, 0), Point(0.1, 0.1)]),
            Point(0.2, 0.2),
        ],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out = gpd.read_file(tmp_path / "out" / "de_landkreis_pies.geojson")
    row = out.iloc[0]
    assert row["pv_kw"] == pytest.approx(400.0)
    assert row["total_kw"] == pytest.approx(400.0)


def test_main_skips_file_without_power_column(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "energy_source_label": ["Solar"],
            "AGS": ["12345"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_writes_one_per_state_subset_per_slug(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    (input_root / "state1").mkdir(parents=True)
    (input_root / "state2").mkdir(parents=True)

    gdf1 = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "energy_source_label": ["2495"],
            "AGS": ["12345"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf1.to_file(input_root / "state1" / "plants.geojson", driver="GeoJSON")

    gdf2 = gpd.GeoDataFrame(
        {
            "power_kw": [500],
            "energy_source_label": ["2497"],
            "AGS": ["54321"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    gdf2.to_file(input_root / "state2" / "plants.geojson", driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345", "54321"],
            "state_slug": ["bayern", "hessen"],
            "kreis_name": ["A", "B"],
        },
        geometry=[Point(1, 1), Point(2, 2)],
        crs="EPSG:4326",
    )
    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    assert (tmp_path / "out" / "de_landkreis_pies.geojson").exists()
    assert (tmp_path / "out" / "bayern" / "de_bayern_landkreis_pies.geojson").exists()
    assert (tmp_path / "out" / "hessen" / "de_hessen_landkreis_pies.geojson").exists()