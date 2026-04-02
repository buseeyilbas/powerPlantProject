"""
Unit tests for step2_2_make_statewise_landkreis_pie_geometries.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_2_make_statewise_landkreis_pie_geometries as mod


def build_points_gdf(
    state_slug="bayern",
    kreis_name="A",
    total_kw=1000,
    pv_kw=500,
    wind_kw=500,
    hydro_kw=0,
    battery_kw=0,
    biogas_kw=0,
    others_kw=0,
    x=10,
    y=50,
    extra_name=None,
):
    data = {
        "state_slug": [state_slug],
        "kreis_name": [kreis_name],
        "total_kw": [total_kw],
        "pv_kw": [pv_kw],
        "wind_kw": [wind_kw],
        "hydro_kw": [hydro_kw],
        "battery_kw": [battery_kw],
        "biogas_kw": [biogas_kw],
        "others_kw": [others_kw],
    }
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
    val = mod.scale_linear(10, 100, 100, 20, 40)
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


def test_process_one_state_basic(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out_file = tmp_path / "de_bayern_landkreis_pie.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_process_one_state_sets_crs_when_missing(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf = gdf.set_crs(None, allow_override=True)

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    assert out.crs is not None


def test_process_one_state_uses_name_column_preference(tmp_path, monkeypatch):
    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=1000,
        wind_kw=0,
        kreis_name="Kreis Label",
        extra_name="Preferred Name",
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    assert set(out["name"]) == {"Preferred Name"}


def test_process_one_state_falls_back_to_kreis_name_when_name_missing(tmp_path, monkeypatch):
    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=1000,
        wind_kw=0,
        kreis_name="Fallback Kreis",
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    assert set(out["name"]) == {"Fallback Kreis"}


def test_process_one_state_parses_multiple_energy_types(tmp_path, monkeypatch):
    gdf = build_points_gdf(
        total_kw=2000,
        pv_kw=1000,
        wind_kw=500,
        biogas_kw=500,
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw", "biogas_kw"}
    assert len(out) == 3


def test_process_one_state_marks_biggest_slice_as_label_anchor(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


def test_process_one_state_writes_expected_colors(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_state(infile)

    out = gpd.read_file(tmp_path / "de_bayern_landkreis_pie.geojson")
    row = out.iloc[0]
    assert row["color_r"] == 255
    assert row["color_g"] == 255
    assert row["color_b"] == 0


def test_process_one_state_zero_parts_raises_with_current_behavior(tmp_path, monkeypatch):
    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=0,
        wind_kw=0,
        hydro_kw=0,
        battery_kw=0,
        biogas_kw=0,
        others_kw=0,
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    with pytest.raises(ValueError):
        mod.process_one_state(infile)


def test_process_one_state_calls_repulse_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern", "bayern"],
            "kreis_name": ["A", "B"],
            "total_kw": [1000, 1000],
            "pv_kw": [1000, 1000],
            "wind_kw": [0, 0],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    mod.process_one_state(infile)

    assert called["value"] is True


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    infile = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.main()

    out_file = tmp_path / "de_bayern_landkreis_pie.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_main_processes_multiple_state_files(tmp_path, monkeypatch):
    gdf1 = build_points_gdf(
        state_slug="bayern",
        kreis_name="A",
        total_kw=1000,
        pv_kw=1000,
        wind_kw=0,
    )
    gdf2 = build_points_gdf(
        state_slug="hessen",
        kreis_name="B",
        total_kw=500,
        pv_kw=0,
        wind_kw=500,
    )

    infile1 = tmp_path / "de_bayern_landkreis_pies.geojson"
    infile2 = tmp_path / "de_hessen_landkreis_pies.geojson"
    gdf1.to_file(infile1, driver="GeoJSON")
    gdf2.to_file(infile2, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.main()

    assert (tmp_path / "de_bayern_landkreis_pie.geojson").exists()
    assert (tmp_path / "de_hessen_landkreis_pie.geojson").exists()


def test_main_ignores_non_matching_filenames(tmp_path, monkeypatch):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    non_matching = tmp_path / "bayern_landkreis_pies.geojson"
    matching = tmp_path / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(non_matching, driver="GeoJSON")
    gdf.to_file(matching, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.main()

    assert (tmp_path / "de_bayern_landkreis_pie.geojson").exists()


def test_main_writes_outputs_to_out_dir_not_in_dir(tmp_path, monkeypatch):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = in_dir / "de_bayern_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", in_dir)
    monkeypatch.setattr(mod, "OUT_DIR", out_dir)

    mod.main()

    assert (out_dir / "de_bayern_landkreis_pie.geojson").exists()
    assert not (in_dir / "de_bayern_landkreis_pie.geojson").exists()