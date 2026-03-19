import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_2_make_landkreis_pie_geometries as mod


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


def test_process_one_state_creates_output(tmp_path, monkeypatch):
    base = tmp_path

    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A"],
            "state_slug": ["test"],
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

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out_file = base / "test" / "de_test_landkreis_pie.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) > 0


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A"],
            "state_slug": ["test"],
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

    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 0, "max_total_kw": 2000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(__import__("json").dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out_file = base / "test" / "de_test_landkreis_pie.geojson"
    assert out_file.exists()