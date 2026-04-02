"""
Unit tests for step2_6_thueringen_statewise_landkreis_pie_geometries_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_6_thueringen_statewise_landkreis_pie_geometries_yearly as mod


def build_points_gdf(
    kreis_slug="a",
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
    year_bin_slug="2019_2020",
    year_bin_label="2019–2020",
    include_kreis_key=False,
    include_landkreis_slug=False,
):
    data = {
        "kreis_slug": [kreis_slug],
        "kreis_name": [kreis_name],
        "year_bin_slug": [year_bin_slug],
        "year_bin_label": [year_bin_label],
        "pv_kw": [pv_kw],
        "wind_kw": [wind_kw],
        "hydro_kw": [hydro_kw],
        "battery_kw": [battery_kw],
        "biogas_kw": [biogas_kw],
        "others_kw": [others_kw],
        "total_kw": [total_kw],
    }

    if include_kreis_key:
        data["kreis_key"] = [kreis_slug]

    if include_landkreis_slug:
        data.pop("kreis_slug")
        data["landkreis_slug"] = [kreis_slug]

    return gpd.GeoDataFrame(
        data,
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
    assert slices[0]["energy_key"] in {"pv_kw", "wind_kw"}
    assert "order_id" in slices[0]


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


def test_process_one_bin_creates_output(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out_file = bin_dir / "thueringen_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_process_one_bin_sets_crs_when_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf = gdf.set_crs(None, allow_override=True)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    assert out.crs is not None


def test_process_one_bin_accepts_kreis_key_schema(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0, include_kreis_key=True)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    assert set(out["kreis_key"]) == {"a"}


def test_process_one_bin_accepts_landkreis_slug_schema(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=1000,
        wind_kw=0,
        include_landkreis_slug=True,
    )
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    assert set(out["kreis_key"]) == {"a"}


def test_process_one_bin_raises_when_all_key_columns_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
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
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    with pytest.raises(KeyError):
        mod.process_one_bin("2019_2020", 0, 2000)


def test_process_one_bin_creates_multiple_slices(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1800, pv_kw=1000, wind_kw=500, biogas_kw=300)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    assert len(out) == 3
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw", "biogas_kw"}


def test_process_one_bin_marks_biggest_slice_as_label_anchor(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


def test_process_one_bin_writes_expected_color_columns(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    row = out.iloc[0]
    assert row["color_r"] == 255
    assert row["color_g"] == 255
    assert row["color_b"] == 0


def test_process_one_bin_groups_duplicate_rows_before_geometry(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "kreis_slug": ["a", "a"],
            "kreis_name": ["A", "A"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
            "year_bin_label": ["2019–2020", "2019–2020"],
            "pv_kw": [500, 500],
            "wind_kw": [0, 0],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [500, 500],
        },
        geometry=[Point(10, 50), Point(10, 50)],
        crs="EPSG:4326",
    )
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    assert len(out) == 1
    assert out.iloc[0]["power_kw"] == pytest.approx(1000.0)
    assert out.iloc[0]["total_kw"] == pytest.approx(1000.0)


def test_process_one_bin_skips_rows_with_non_positive_total(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(
        total_kw=0,
        pv_kw=0,
        wind_kw=0,
        hydro_kw=0,
        battery_kw=0,
        biogas_kw=0,
        others_kw=0,
    )
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 0, 2000)

    assert not (bin_dir / "thueringen_landkreis_pie_2019_2020.geojson").exists()


def test_process_one_bin_uses_global_scaling_range_for_radius(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", 1000, 1000)

    out = gpd.read_file(bin_dir / "thueringen_landkreis_pie_2019_2020.geojson")
    expected_radius = (mod.R_MIN_M + mod.R_MAX_M) / 2.0
    assert out.iloc[0]["radius_m"] == pytest.approx(expected_radius)


def test_process_one_bin_does_not_call_repulse_when_centers_are_fixed(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "kreis_slug": ["a", "b"],
            "kreis_name": ["A", "B"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
            "year_bin_label": ["2019–2020", "2019–2020"],
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
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "CENTERS_ARE_FIXED", True)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    mod.process_one_bin("2019_2020", 0, 2000)

    assert called["value"] is False


def test_process_one_bin_calls_repulse_when_centers_not_fixed(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "kreis_slug": ["a", "b"],
            "kreis_name": ["A", "B"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
            "year_bin_label": ["2019–2020", "2019–2020"],
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
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "CENTERS_ARE_FIXED", False)
    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    mod.process_one_bin("2019_2020", 0, 2000)

    assert called["value"] is True


def test_process_one_bin_skips_missing_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.process_one_bin("2019_2020", 0, 1000)


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    meta = {"min_total_kw": 0, "max_total_kw": 2000}
    meta_path = base / "_THUERINGEN_GLOBAL_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir()

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "thueringen_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META", meta_path)
    monkeypatch.setattr(mod, "YEAR_BINS", ["2019_2020"])

    mod.main()

    out_file = bin_dir / "thueringen_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()


def test_main_returns_when_meta_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "GLOBAL_META", tmp_path / "_THUERINGEN_GLOBAL_style_meta.json")

    mod.main()

    assert list(tmp_path.glob("**/thueringen_landkreis_pie_*.geojson")) == []


def test_main_processes_multiple_bins(tmp_path, monkeypatch):
    base = tmp_path

    meta = {"min_total_kw": 0, "max_total_kw": 3000}
    meta_path = base / "_THUERINGEN_GLOBAL_style_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    for slug, total, pv, wind in [
        ("2019_2020", 1000, 1000, 0),
        ("2021_2022", 3000, 0, 3000),
    ]:
        bin_dir = base / slug
        bin_dir.mkdir()
        gdf = build_points_gdf(
            total_kw=total,
            pv_kw=pv,
            wind_kw=wind,
            year_bin_slug=slug,
            year_bin_label=slug,
        )
        gdf.to_file(bin_dir / f"thueringen_landkreis_pies_{slug}.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META", meta_path)
    monkeypatch.setattr(mod, "YEAR_BINS", ["2019_2020", "2021_2022"])

    mod.main()

    assert (base / "2019_2020" / "thueringen_landkreis_pie_2019_2020.geojson").exists()
    assert (base / "2021_2022" / "thueringen_landkreis_pie_2021_2022.geojson").exists()