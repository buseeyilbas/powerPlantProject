"""
Unit tests for step3_2_make_landkreis_pie_geometries.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_2_make_landkreis_pie_geometries as mod


def build_points_gdf(
    state_slug="test",
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
):
    return gpd.GeoDataFrame(
        {
            "kreis_name": [kreis_name],
            "state_slug": [state_slug],
            "pv_kw": [pv_kw],
            "wind_kw": [wind_kw],
            "hydro_kw": [hydro_kw],
            "battery_kw": [battery_kw],
            "biogas_kw": [biogas_kw],
            "others_kw": [others_kw],
            "total_kw": [total_kw],
        },
        geometry=[Point(x, y)],
        crs="EPSG:4326",
    )


def test_scale_linear_basic():
    val = mod.scale_linear(5, 0, 10, 0, 100)
    assert val == pytest.approx(50)


def test_scale_linear_clamp():
    assert mod.scale_linear(-5, 0, 10, 0, 100) == 0
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


def test_process_one_state_creates_output(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out_file = base / "test" / "de_test_landkreis_pie.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_process_one_state_creates_multiple_slices(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(total_kw=1800, pv_kw=1000, wind_kw=500, biogas_kw=300)

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    assert len(out) == 3
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw", "biogas_kw"}


def test_process_one_state_marks_biggest_slice_as_label_anchor(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


def test_process_one_state_writes_expected_color_columns(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    row = out.iloc[0]
    assert row["color_r"] == 255
    assert row["color_g"] == 212
    assert row["color_b"] == 0


def test_process_one_state_preserves_name_from_kreis_name(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(kreis_name="Testkreis", total_kw=1000, pv_kw=1000, wind_kw=0)

    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_state(gdf, 0, 2000, "test")

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    assert set(out["name"]) == {"Testkreis"}


def test_process_one_state_calls_repulse_centers(tmp_path, monkeypatch):
    base = tmp_path
    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A", "B"],
            "state_slug": ["test", "test"],
            "pv_kw": [1000, 1000],
            "wind_kw": [0, 0],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [1000, 1000],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    mod.process_one_state(gdf, 0, 2000, "test")

    assert called["value"] is True


def test_process_one_state_zero_parts_current_behavior_raises(tmp_path, monkeypatch):
    base = tmp_path
    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=0,
        wind_kw=0,
        hydro_kw=0,
        battery_kw=0,
        biogas_kw=0,
        others_kw=0,
    )

    monkeypatch.setattr(mod, "OUT_DIR", base)

    with pytest.raises(ValueError):
        mod.process_one_state(gdf, 0, 2000, "test")


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 0, "max_total_kw": 2000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out_file = base / "test" / "de_test_landkreis_pie.geojson"
    assert out_file.exists()


def test_main_uses_meta_file_when_present(tmp_path, monkeypatch):
    base = tmp_path

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 1000, "max_total_kw": 1000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    assert out.iloc[0]["radius_m"] == pytest.approx(mod.R_MIN_M)


def test_main_bumps_vmax_when_meta_min_equals_max(tmp_path, monkeypatch):
    base = tmp_path

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 1000, "max_total_kw": 1000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    assert out.iloc[0]["radius_m"] == pytest.approx(mod.R_MIN_M)
    assert out.iloc[0]["total_kw"] == pytest.approx(1000.0)


def test_main_falls_back_to_gdf_min_max_when_meta_missing(tmp_path, monkeypatch):
    base = tmp_path

    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A", "B"],
            "state_slug": ["test", "test"],
            "pv_kw": [1000, 0],
            "wind_kw": [0, 3000],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [1000, 3000],
        },
        geometry=[Point(10, 50), Point(11, 51)],
        crs="EPSG:4326",
    )
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", base / "missing_meta.json")
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out = gpd.read_file(base / "test" / "de_test_landkreis_pie.geojson")
    assert len(out) == 2
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw"}

    pv_radius = out[out["energy_type"] == "pv_kw"].iloc[0]["radius_m"]
    wind_radius = out[out["energy_type"] == "wind_kw"].iloc[0]["radius_m"]
    assert wind_radius > pv_radius


def test_main_raises_when_input_missing(tmp_path, monkeypatch):
    base = tmp_path

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", base / "de_landkreis_pies.geojson")
    monkeypatch.setattr(mod, "META_FILE", base / "landkreis_pie_style_meta.json")
    monkeypatch.setattr(mod, "OUT_DIR", base)

    with pytest.raises(FileNotFoundError):
        mod.main()


def test_main_processes_multiple_states(tmp_path, monkeypatch):
    base = tmp_path

    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A", "B"],
            "state_slug": ["bayern", "hessen"],
            "pv_kw": [1000, 0],
            "wind_kw": [0, 500],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [1000, 500],
        },
        geometry=[Point(10, 50), Point(9, 51)],
        crs="EPSG:4326",
    )
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 0, "max_total_kw": 2000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    assert (base / "bayern" / "de_bayern_landkreis_pie.geojson").exists()
    assert (base / "hessen" / "de_hessen_landkreis_pie.geojson").exists()


def test_main_skips_rows_with_empty_state_slug(tmp_path, monkeypatch):
    base = tmp_path

    gdf = gpd.GeoDataFrame(
        {
            "kreis_name": ["A", "B"],
            "state_slug": ["", "hessen"],
            "pv_kw": [1000, 0],
            "wind_kw": [0, 500],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [1000, 500],
        },
        geometry=[Point(10, 50), Point(9, 51)],
        crs="EPSG:4326",
    )
    infile = base / "de_landkreis_pies.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    meta = {"min_total_kw": 0, "max_total_kw": 2000}
    meta_path = base / "landkreis_pie_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_FILE", infile)
    monkeypatch.setattr(mod, "META_FILE", meta_path)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    assert not (base / "de__landkreis_pie.geojson").exists()
    assert (base / "hessen" / "de_hessen_landkreis_pie.geojson").exists()