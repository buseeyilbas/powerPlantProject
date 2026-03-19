import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_4_make_landkreis_pie_geometries_yearly as mod


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


def test_repulse_centers_moves():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10.0},
        {"x": 0.0, "y": 0.0, "r": 10.0},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"] or centers[0]["y"] != centers[1]["y"]


def test_make_pies_for_points_basic(tmp_path):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["test"],
            "kreis_key": ["123"],
            "kreis_name": ["A"],
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

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n > 0
    assert out_file.exists()


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    # create global meta
    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
        "r_min_m": 10000,
        "r_max_m": 50000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(__import__("json").dumps(meta))

    # create bin folder + input
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["test"],
            "kreis_key": ["123"],
            "kreis_name": ["A"],
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
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    mod.main()

    out_file = bin_dir / "de_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()