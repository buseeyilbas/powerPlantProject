import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_4_make_statewise_landkreis_pie_geometries_yearly as mod


def test_scale_linear_basic():
    val = mod.scale_linear(5, 0, 10, 0, 100)
    assert val == pytest.approx(50)


def test_scale_linear_clamp():
    assert mod.scale_linear(-5, 0, 10, 0, 100) == 0
    assert mod.scale_linear(20, 0, 10, 0, 100) == 100


def test_make_pie_basic():
    center = (0, 0)
    parts = [("pv_kw", 100), ("wind_kw", 100)]

    slices, anchor = mod.make_pie(center, 10, parts)

    assert len(slices) == 2
    assert anchor in ["pv_kw", "wind_kw"]


def test_make_pie_zero_total():
    center = (0, 0)
    parts = [("pv_kw", 0), ("wind_kw", 0)]

    slices, anchor = mod.make_pie(center, 10, parts)

    assert slices == []
    assert anchor is None


def test_process_one_bin_creates_outputs(tmp_path, monkeypatch):
    base = tmp_path

    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern"],
            "kreis_key": ["A"],
            "year_bin_slug": ["2019_2020"],
            "year_bin_label": ["2019–2020"],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
            "total_kw": [1000],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {
        "bayern": {
            "min_total_kw": 0,
            "max_total_kw": 2000,
        }
    }

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out_all = bin_dir / "de_landkreis_pie_2019_2020.geojson"
    out_state = base / "de_bayern_landkreis_pie_2019_2020.geojson"

    assert out_all.exists()
    assert out_state.exists()

    out = gpd.read_file(out_all)
    assert len(out) > 0


def test_process_one_bin_skips_missing_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 1000}}

    # should not raise
    mod.process_one_bin("2019_2020", state_meta)


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    # create meta
    meta = {
        "bayern": {
            "min_total_kw": 0,
            "max_total_kw": 2000,
        }
    }

    meta_path = base / "_STATEWISE_size_meta.json"
    meta_path.write_text(__import__("json").dumps(meta), encoding="utf-8")

    # create one bin input
    bin_dir = base / "2019_2020"
    bin_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern"],
            "kreis_key": ["A"],
            "year_bin_slug": ["2019_2020"],
            "year_bin_label": ["2019–2020"],
            "pv_kw": [1000],
            "wind_kw": [0],
            "hydro_kw": [0],
            "battery_kw": [0],
            "biogas_kw": [0],
            "others_kw": [0],
            "total_kw": [1000],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )

    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out_file = bin_dir / "de_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()