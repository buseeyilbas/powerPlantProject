"""
Unit tests for step1_4_make_state_pie_geometries_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_4_make_state_pie_geometries_yearly as mod


def build_points_gdf(
    state_name="A",
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
    val = mod.scale_linear(50, 0, 100, 10, 20)
    assert 10 <= val <= 20
    assert val == pytest.approx(15)


def test_scale_linear_edge_same_min_max():
    val = mod.scale_linear(50, 100, 100, 10, 20)
    assert val == 15


def test_scale_linear_clamps_low_and_high():
    assert mod.scale_linear(-5, 0, 100, 10, 20) == 10
    assert mod.scale_linear(500, 0, 100, 10, 20) == 20


def test_ring_pts_returns_points():
    pts = mod.ring_pts((0, 0), 10, 0, 1)
    assert len(pts) == 49
    assert isinstance(pts[0], tuple)


def test_make_pie_basic():
    center = (0, 0)
    radius = 10
    parts = [("pv_kw", 50), ("wind_kw", 50)]

    slices, anchor = mod.make_pie(center, radius, parts)

    assert len(slices) == 2
    assert anchor in ["pv_kw", "wind_kw"]


def test_make_pie_zero_total():
    slices, anchor = mod.make_pie((0, 0), 10, [("pv_kw", 0)])
    assert slices == []
    assert anchor is None


def test_make_pie_anchor_is_biggest_slice():
    slices, anchor = mod.make_pie(
        (0, 0),
        10,
        [("pv_kw", 70), ("wind_kw", 20), ("others_kw", 10)],
    )
    assert len(slices) == 3
    assert anchor == "pv_kw"


def test_repulse_centers_moves_overlap():
    centers = [
        {"x": 0, "y": 0, "r": 10},
        {"x": 0, "y": 0, "r": 10},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"] or centers[0]["y"] != centers[1]["y"]


# def test_repulse_centers_no_change_when_far():
#     centers = [
#         {"x": 0, "y": 0, "r": 10},
#         {"x": 1000, "y": 1000, "r": 10},
#     ]
#     before = [(c["x"], c["y"]) for c in centers]

#     mod.repulse_centers(centers)

#     after = [(c["x"], c["y"]) for c in centers]
#     assert after == before


def test_pies_from_points_basic(tmp_path):
    gdf = build_points_gdf()

    out_path = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1000, out_path)

    assert n > 0
    assert out_path.exists()

    out = gpd.read_file(out_path)
    assert len(out) == 2
    assert "energy_type" in out.columns
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw"}


def test_pies_from_points_empty_input(tmp_path):
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

    out_path = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1000, out_path)

    assert n == 0
    assert not out_path.exists()


def test_pies_from_points_sets_crs_when_missing(tmp_path):
    gdf = build_points_gdf()
    gdf = gdf.set_crs(None, allow_override=True)

    out_path = tmp_path / "out.geojson"

    n = mod.pies_from_points(gdf, 0, 1000, out_path)

    assert n > 0
    out = gpd.read_file(out_path)
    assert out.crs is not None


# def test_pies_from_points_uses_name_fallback(tmp_path):
#     gdf = build_points_gdf(state_name=None, extra_name="Fallback Name")

#     out_path = tmp_path / "out.geojson"

#     mod.pies_from_points(gdf, 0, 1000, out_path)

#     out = gpd.read_file(out_path)
#     assert set(out["name"]) == {"Fallback Name"}


# def test_pies_from_points_uses_name_fallback_when_state_name_is_empty_string(tmp_path):
#     gdf = build_points_gdf(state_name="", extra_name="Fallback Name")

#     out_path = tmp_path / "out.geojson"

#     mod.pies_from_points(gdf, 0, 1000, out_path)

#     out = gpd.read_file(out_path)
#     assert set(out["name"]) == {"Fallback Name"}


def test_pies_from_points_parses_state_number_to_int(tmp_path):
    gdf = build_points_gdf(state_number="7")

    out_path = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 1000, out_path)

    out = gpd.read_file(out_path)
    assert set(out["state_number"]) == {7}


def test_pies_from_points_invalid_state_number_becomes_none(tmp_path):
    gdf = build_points_gdf(state_number="not_an_int")

    out_path = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 1000, out_path)

    out = gpd.read_file(out_path)
    assert out["state_number"].isna().all()


def test_pies_from_points_marks_biggest_slice_as_label_anchor(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)

    out_path = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 1000, out_path)

    out = gpd.read_file(out_path)
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

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

#     out_path = tmp_path / "out.geojson"

#     n = mod.pies_from_points(gdf, 0, 1000, out_path)

#     assert n == 0
#     assert not out_path.exists()


# def test_pies_from_points_zero_parts_removes_existing_output_file(tmp_path):
#     gdf = build_points_gdf(
#         total_kw=1000,
#         pv_kw=0,
#         wind_kw=0,
#         hydro_kw=0,
#         battery_kw=0,
#         biogas_kw=0,
#         others_kw=0,
#     )

#     out_path = tmp_path / "out.geojson"
#     out_path.write_text("old content", encoding="utf-8")

#     n = mod.pies_from_points(gdf, 0, 1000, out_path)

#     assert n == 0
#     assert not out_path.exists()


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

    out_path = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 1000, out_path)

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

    out_path = tmp_path / "out.geojson"

    mod.pies_from_points(gdf, 0, 1000, out_path)

    assert called["value"] is False


def test_main_skips_missing_bins(tmp_path, monkeypatch):
    base = tmp_path
    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_META", base / "_GLOBAL_style_meta.json")

    mod.main()


def test_main_basic_per_bin_scaling(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    pts = bin_dir / "de_state_pies_2019_2020.geojson"
    meta = bin_dir / "state_pie_style_meta_2019_2020.json"

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf.to_file(pts, driver="GeoJSON")

    meta.write_text(
        json.dumps({"min_total_kw": 0, "max_total_kw": 1000}),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out = bin_dir / "de_state_pie_2019_2020.geojson"
    assert out.exists()

    gout = gpd.read_file(out)
    assert len(gout) == 1
    assert set(gout["energy_type"]) == {"pv_kw"}


def test_main_with_global_meta(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    pts = bin_dir / "de_state_pies_2019_2020.geojson"
    meta = bin_dir / "state_pie_style_meta_2019_2020.json"
    global_meta = base / "_GLOBAL_style_meta.json"

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf.to_file(pts, driver="GeoJSON")

    meta.write_text(
        json.dumps({"min_total_kw": 0, "max_total_kw": 500}),
        encoding="utf-8",
    )
    global_meta.write_text(
        json.dumps({"min_total_kw": 0, "max_total_kw": 1000}),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_META", global_meta)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)

    mod.main()

    out = bin_dir / "de_state_pie_2019_2020.geojson"
    assert out.exists()


def test_main_computes_global_scale_when_meta_missing(tmp_path, monkeypatch):
    base = tmp_path

    bin1 = base / "2019_2020"
    bin2 = base / "2021_2022"
    bin1.mkdir(parents=True)
    bin2.mkdir(parents=True)

    pts1 = bin1 / "de_state_pies_2019_2020.geojson"
    pts2 = bin2 / "de_state_pies_2021_2022.geojson"

    meta1 = bin1 / "state_pie_style_meta_2019_2020.json"
    meta2 = bin2 / "state_pie_style_meta_2021_2022.json"

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

    gdf1.to_file(pts1, driver="GeoJSON")
    gdf2.to_file(pts2, driver="GeoJSON")

    meta1.write_text(
        json.dumps({"min_total_kw": 0, "max_total_kw": 1000}),
        encoding="utf-8",
    )
    meta2.write_text(
        json.dumps({"min_total_kw": 0, "max_total_kw": 3000}),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_META", base / "missing_global_meta.json")
    monkeypatch.setattr(mod, "GLOBAL_SIZING", True)

    mod.main()

    out1 = bin1 / "de_state_pie_2019_2020.geojson"
    out2 = bin2 / "de_state_pie_2021_2022.geojson"

    assert out1.exists()
    assert out2.exists()


def test_main_skips_bin_when_inputs_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "BASE", base)
    monkeypatch.setattr(mod, "GLOBAL_SIZING", False)

    mod.main()

    out = bin_dir / "de_state_pie_2019_2020.geojson"
    assert not out.exists()