"""
Unit tests for step1_6_thueringen_state_pie_geometries_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_6_thueringen_state_pie_geometries_yearly as mod


def build_points_gdf(
    state_name="Thüringen",
    total_kw=1000,
    pv_kw=500,
    wind_kw=500,
    hydro_kw=0,
    battery_kw=0,
    biogas_kw=0,
    others_kw=0,
    x=10,
    y=50,
    year_bin_label="2019–2020",
    year_bin_slug="2019_2020",
    state_number=None,
    extra_name=None,
):
    data = {
        "state_name": [state_name],
        "total_kw": [total_kw],
        "pv_kw": [pv_kw],
        "wind_kw": [wind_kw],
        "hydro_kw": [hydro_kw],
        "battery_kw": [battery_kw],
        "biogas_kw": [biogas_kw],
        "others_kw": [others_kw],
        "year_bin_label": [year_bin_label],
        "year_bin_slug": [year_bin_slug],
    }
    if state_number is not None:
        data["state_number"] = [state_number]
    if extra_name is not None:
        data["name"] = [extra_name]

    return gpd.GeoDataFrame(
        data,
        geometry=[Point(x, y)],
        crs="EPSG:4326",
    )


def test_scale_linear_basic():
    val = mod.scale_linear(5, 0, 10, 0, 100)
    assert val == pytest.approx(50)


def test_scale_linear_clamps():
    assert mod.scale_linear(-10, 0, 10, 0, 100) == 0
    assert mod.scale_linear(20, 0, 10, 0, 100) == 100


def test_scale_linear_same_min_max_returns_midpoint():
    val = mod.scale_linear(5, 10, 10, 20, 40)
    assert val == pytest.approx(30)


def test_ring_pts_returns_expected_count_and_type():
    pts = mod.ring_pts((0, 0), 10, 0, 1)
    assert len(pts) == 49
    assert isinstance(pts[0], tuple)


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


def test_make_pie_anchor_is_biggest_slice():
    center = (0, 0)
    parts = [("pv_kw", 70), ("wind_kw", 20), ("others_kw", 10)]

    slices, anchor = mod.make_pie(center, 10, parts)

    assert len(slices) == 3
    assert anchor == "pv_kw"


def test_repulse_centers_moves_overlap():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10},
        {"x": 0.0, "y": 0.0, "r": 10},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"] or centers[0]["y"] != centers[1]["y"]


def test_repulse_centers_no_change_when_truly_far():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10},
        {"x": 1000000.0, "y": 1000000.0, "r": 10},
    ]
    before = [(c["x"], c["y"]) for c in centers]

    mod.repulse_centers(centers)

    after = [(c["x"], c["y"]) for c in centers]
    assert after == before


def test_pies_from_points_basic(tmp_path):
    gdf = build_points_gdf()

    out = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 2000, out)

    assert n > 0
    assert out.exists()

    gout = gpd.read_file(out)
    assert len(gout) == 2
    assert set(gout["energy_type"]) == {"pv_kw", "wind_kw"}
    assert "label_anchor" in gout.columns


def test_pies_from_points_empty(tmp_path):
    gdf = gpd.GeoDataFrame(
        {
            "state_name": [],
            "total_kw": [],
            "pv_kw": [],
            "wind_kw": [],
            "hydro_kw": [],
            "battery_kw": [],
            "biogas_kw": [],
            "others_kw": [],
            "year_bin_label": [],
            "year_bin_slug": [],
        },
        geometry=[],
        crs="EPSG:4326",
    )

    out = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1, out)

    assert n == 0
    assert not out.exists()


def test_pies_from_points_sets_crs_when_missing(tmp_path):
    gdf = build_points_gdf()
    gdf = gdf.set_crs(None, allow_override=True)

    out = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 2000, out)

    assert n > 0
    gout = gpd.read_file(out)
    assert gout.crs is not None


# def test_pies_from_points_uses_name_fallback(tmp_path):
#     gdf = build_points_gdf(state_name=None, extra_name="Fallback Name")

#     out = tmp_path / "out.geojson"

#     mod.pies_from_points(gdf, 0, 2000, out)

#     gout = gpd.read_file(out)
#     assert set(gout["name"]) == {"Fallback Name"}


# def test_pies_from_points_uses_name_fallback_when_state_name_is_empty_string(tmp_path):
#     gdf = build_points_gdf(state_name="", extra_name="Fallback Name")

#     out = tmp_path / "out.geojson"

#     mod.pies_from_points(gdf, 0, 2000, out)

#     gout = gpd.read_file(out)
#     assert set(gout["name"]) == {"Fallback Name"}


def test_pies_from_points_parses_state_number_to_int(tmp_path):
    gdf = build_points_gdf(state_number="16")

    out = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 2000, out)

    gout = gpd.read_file(out)
    assert set(gout["state_number"]) == {16}


def test_pies_from_points_invalid_state_number_becomes_none(tmp_path):
    gdf = build_points_gdf(state_number="not_an_int")

    out = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 2000, out)

    gout = gpd.read_file(out)
    assert gout["state_number"].isna().all()


def test_pies_from_points_marks_biggest_slice_as_label_anchor(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)

    out = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 2000, out)

    gout = gpd.read_file(out)
    pv_row = gout[gout["energy_type"] == "pv_kw"].iloc[0]
    wind_row = gout[gout["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


# def test_pies_from_points_zero_parts_produce_no_features(tmp_path):
#     gdf = build_points_gdf(
#         total_kw=1000,
#         pv_kw=0,
#         wind_kw=0,
#         hydro_kw=0,
#         battery_kw=0,
#         biogas_kw=0,
#         others_kw=0,
#     )

#     out = tmp_path / "out.geojson"

#     n = mod.pies_from_points(gdf, 0, 2000, out)

#     assert n == 0
#     assert not out.exists()


def test_pies_from_points_calls_repulse_when_centers_not_fixed(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A", "B"],
            "total_kw": [1000, 1000],
            "pv_kw": [1000, 1000],
            "wind_kw": [0, 0],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "year_bin_label": ["2019–2020", "2019–2020"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "CENTERS_ARE_FIXED", False)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    out = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 2000, out)

    assert called["value"] is True


def test_pies_from_points_does_not_call_repulse_when_centers_are_fixed(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_name": ["A", "B"],
            "total_kw": [1000, 1000],
            "pv_kw": [1000, 1000],
            "wind_kw": [0, 0],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "year_bin_label": ["2019–2020", "2019–2020"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "CENTERS_ARE_FIXED", True)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    out = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 2000, out)

    assert called["value"] is False


def test_main_skips_missing_inputs(tmp_path, monkeypatch):
    base = tmp_path
    monkeypatch.setattr(mod, "BASE", base)

    (base / "bin1").mkdir()

    mod.main()


def test_main_basic(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    pts_path = bin_dir / "thueringen_state_pies_2019_2020.geojson"
    gdf.to_file(pts_path, driver="GeoJSON")

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
    }
    meta_path = bin_dir / "thueringen_state_pie_style_meta_2019_2020.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert out_file.exists()

    gout = gpd.read_file(out_file)
    assert len(gout) == 1
    assert set(gout["energy_type"]) == {"pv_kw"}


def test_main_global_scaling(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    pts_path = bin_dir / "thueringen_state_pies_2019_2020.geojson"
    gdf.to_file(pts_path, driver="GeoJSON")

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
    }
    meta_path = bin_dir / "thueringen_state_pie_style_meta_2019_2020.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    global_meta = {
        "min_total_kw": 0,
        "max_total_kw": 5000,
    }
    global_meta_path = base / "_GLOBAL_style_meta.json"
    global_meta_path.write_text(json.dumps(global_meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)
    monkeypatch.setattr(mod, "GLOBAL_META", global_meta_path)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert out_file.exists()


def test_main_computes_global_scaling_when_global_meta_missing(tmp_path, monkeypatch):
    base = tmp_path

    bin1 = base / "2019_2020"
    bin2 = base / "2021_2022"
    bin1.mkdir(parents=True)
    bin2.mkdir(parents=True)

    gdf1 = build_points_gdf(
        total_kw=1000,
        pv_kw=1000,
        wind_kw=0,
        year_bin_slug="2019_2020",
        year_bin_label="2019–2020",
    )
    gdf2 = build_points_gdf(
        total_kw=3000,
        pv_kw=0,
        wind_kw=3000,
        year_bin_slug="2021_2022",
        year_bin_label="2021–2022",
    )

    pts1 = bin1 / "thueringen_state_pies_2019_2020.geojson"
    pts2 = bin2 / "thueringen_state_pies_2021_2022.geojson"
    gdf1.to_file(pts1, driver="GeoJSON")
    gdf2.to_file(pts2, driver="GeoJSON")

    meta1 = bin1 / "thueringen_state_pie_style_meta_2019_2020.json"
    meta2 = bin2 / "thueringen_state_pie_style_meta_2021_2022.json"
    meta1.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 1000}), encoding="utf-8")
    meta2.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 3000}), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_META", base / "missing_global_meta.json")
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)

    mod.main()

    out1 = bin1 / "thueringen_state_pie_2019_2020.geojson"
    out2 = bin2 / "thueringen_state_pie_2021_2022.geojson"

    assert out1.exists()
    assert out2.exists()


def test_main_skips_bin_when_meta_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    pts_path = bin_dir / "thueringen_state_pies_2019_2020.geojson"
    gdf.to_file(pts_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert not out_file.exists()


def test_main_skips_bin_when_points_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    meta_path = bin_dir / "thueringen_state_pie_style_meta_2019_2020.json"
    meta_path.write_text(json.dumps({"min_total_kw": 0, "max_total_kw": 1000}), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out_file = bin_dir / "thueringen_state_pie_2019_2020.geojson"
    assert not out_file.exists()