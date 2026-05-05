"""
Unit tests for step2_4_make_statewise_landkreis_pie_geometries_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step2_4_make_statewise_landkreis_pie_geometries_yearly as mod


def build_points_gdf(
    state_slug="bayern",
    kreis_key="A",
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
):
    return gpd.GeoDataFrame(
        {
            "state_slug": [state_slug],
            "kreis_key": [kreis_key],
            "year_bin_slug": [year_bin_slug],
            "year_bin_label": [year_bin_label],
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


def test_process_one_bin_creates_outputs(tmp_path, monkeypatch):
    base = tmp_path

    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
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
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_process_one_bin_sets_crs_when_missing(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf = gdf.set_crs(None, allow_override=True)

    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    assert out.crs is not None


def test_process_one_bin_creates_multiple_slices(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1800, pv_kw=1000, wind_kw=500, biogas_kw=300)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    assert len(out) == 3
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw", "biogas_kw"}


def test_process_one_bin_marks_biggest_slice_as_label_anchor(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


def test_process_one_bin_writes_expected_color_columns(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    row = out.iloc[0]
    assert row["color_r"] == 255
    assert row["color_g"] == 255
    assert row["color_b"] == 0


def test_process_one_bin_writes_power_gw_and_total_gw(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    row = out.iloc[0]
    assert row["power_gw"] == pytest.approx(0.001)
    assert row["total_gw"] == pytest.approx(0.001)


def test_process_one_bin_uses_statewise_meta_for_radius_scaling(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {
        "bayern": {
            "min_total_kw": 1000,
            "max_total_kw": 1000,
        }
    }

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    expected_radius = (mod.R_MIN_M + mod.R_MAX_M) / 2.0
    assert out.iloc[0]["radius_m"] == pytest.approx(expected_radius)


def test_process_one_bin_groups_duplicate_rows_before_geometry(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern", "bayern"],
            "kreis_key": ["A", "A"],
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
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    assert len(out) == 1
    assert out.iloc[0]["power_kw"] == pytest.approx(1000.0)
    assert out.iloc[0]["total_kw"] == pytest.approx(1000.0)


def test_process_one_bin_skips_missing_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 1000}}

    mod.process_one_bin("2019_2020", state_meta)


def test_process_one_bin_skips_empty_input_file(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    empty = gpd.GeoDataFrame(
        {
            "state_slug": [],
            "kreis_key": [],
            "year_bin_slug": [],
            "year_bin_label": [],
            "pv_kw": [],
            "wind_kw": [],
            "hydro_kw": [],
            "battery_kw": [],
            "biogas_kw": [],
            "others_kw": [],
            "total_kw": [],
        },
        geometry=[],
        crs="EPSG:4326",
    )
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    empty.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", {"bayern": {"min_total_kw": 0, "max_total_kw": 1000}})

    assert not (bin_dir / "de_landkreis_pie_2019_2020.geojson").exists()


def test_process_one_bin_skips_rows_without_state_meta(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(state_slug="bayern", total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", {"hessen": {"min_total_kw": 0, "max_total_kw": 2000}})

    assert not (bin_dir / "de_landkreis_pie_2019_2020.geojson").exists()
    assert not (base / "de_bayern_landkreis_pie_2019_2020.geojson").exists()


def test_process_one_bin_zero_parts_produces_no_outputs(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=0,
        wind_kw=0,
        hydro_kw=0,
        battery_kw=0,
        biogas_kw=0,
        others_kw=0,
    )
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}})

    assert not (bin_dir / "de_landkreis_pie_2019_2020.geojson").exists()
    assert not (base / "de_bayern_landkreis_pie_2019_2020.geojson").exists()


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "bayern": {
            "min_total_kw": 0,
            "max_total_kw": 2000,
        }
    }

    meta_path = base / "_STATEWISE_size_meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir()

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.main()

    out_file = bin_dir / "de_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()


def test_main_returns_when_meta_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(mod, "IN_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    mod.main()

    assert list(tmp_path.glob("**/de_landkreis_pie_*.geojson")) == []


def test_main_processes_multiple_bins(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "bayern": {
            "min_total_kw": 0,
            "max_total_kw": 3000,
        }
    }
    (base / "_STATEWISE_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

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
        gdf.to_file(bin_dir / f"de_landkreis_pies_{slug}.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "YEAR_BINS", ["2019_2020", "2021_2022"])

    mod.main()

    assert (base / "2019_2020" / "de_landkreis_pie_2019_2020.geojson").exists()
    assert (base / "2021_2022" / "de_landkreis_pie_2021_2022.geojson").exists()


def test_main_writes_per_state_outputs(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "bayern": {"min_total_kw": 0, "max_total_kw": 2000},
        "hessen": {"min_total_kw": 0, "max_total_kw": 2000},
    }
    (base / "_STATEWISE_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern", "hessen"],
            "kreis_key": ["A", "B"],
            "year_bin_slug": ["2019_2020", "2019_2020"],
            "year_bin_label": ["2019–2020", "2019–2020"],
            "pv_kw": [1000, 0],
            "wind_kw": [0, 1000],
            "hydro_kw": [0, 0],
            "battery_kw": [0, 0],
            "biogas_kw": [0, 0],
            "others_kw": [0, 0],
            "total_kw": [1000, 1000],
        },
        geometry=[Point(10, 50), Point(9, 51)],
        crs="EPSG:4326",
    )
    gdf.to_file(bin_dir / "de_landkreis_pies_2019_2020.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)
    monkeypatch.setattr(mod, "YEAR_BINS", ["2019_2020"])

    mod.main()

    assert (base / "de_bayern_landkreis_pie_2019_2020.geojson").exists()
    assert (base / "de_hessen_landkreis_pie_2019_2020.geojson").exists()

def test_radius_constants_match_step2_3_manual_setup():
    assert mod.R_MIN_M == 5000.0
    assert mod.R_MAX_M == 30000.0


def test_process_one_bin_carries_state_abbrev_to_outputs(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf["state_abbrev"] = ["BY"]

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

    out_all = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    out_state = gpd.read_file(base / "de_bayern_landkreis_pie_2019_2020.geojson")

    assert "state_abbrev" in out_all.columns
    assert "state_abbrev" in out_state.columns
    assert set(out_all["state_abbrev"]) == {"BY"}
    assert set(out_state["state_abbrev"]) == {"BY"}


def test_process_one_bin_missing_state_abbrev_becomes_empty_string(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

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

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")

    assert "state_abbrev" in out.columns
    assert set(out["state_abbrev"].fillna("")) == {""}


def test_process_one_bin_groups_duplicate_rows_preserves_state_abbrev(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["bayern", "bayern"],
            "state_abbrev": ["BY", "BY"],
            "kreis_key": ["A", "A"],
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

    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")

    assert len(out) == 1
    assert out.iloc[0]["power_kw"] == pytest.approx(1000.0)
    assert out.iloc[0]["total_kw"] == pytest.approx(1000.0)
    assert set(out["state_abbrev"]) == {"BY"}


def test_process_one_bin_output_schema_contains_current_fields(tmp_path, monkeypatch):
    base = tmp_path
    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1_500_000, pv_kw=1_000_000, wind_kw=500_000)
    gdf["state_abbrev"] = ["BY"]

    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_meta = {"bayern": {"min_total_kw": 0, "max_total_kw": 2_000_000}}

    monkeypatch.setattr(mod, "IN_DIR", base)
    monkeypatch.setattr(mod, "OUT_DIR", base)

    mod.process_one_bin("2019_2020", state_meta)

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")

    expected_columns = {
        "name",
        "state_slug",
        "state_abbrev",
        "energy_type",
        "power_kw",
        "power_gw",
        "total_kw",
        "total_gw",
        "share",
        "radius_m",
        "order_id",
        "label_anchor",
        "year_bin",
        "year_bin_slug",
        "color_r",
        "color_g",
        "color_b",
        "geometry",
    }

    assert expected_columns.issubset(set(out.columns))
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw"}
    assert set(out["state_abbrev"]) == {"BY"}

    pv = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv["power_gw"] == pytest.approx(1.0)
    assert wind["power_gw"] == pytest.approx(0.5)
    assert pv["total_gw"] == pytest.approx(1.5)
    assert wind["total_gw"] == pytest.approx(1.5)