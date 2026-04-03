"""
Unit tests for step3_4_make_landkreis_pie_geometries_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_4_make_landkreis_pie_geometries_yearly as mod


def build_points_gdf(
    state_slug="test",
    kreis_key="123",
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
):
    return gpd.GeoDataFrame(
        {
            "state_slug": [state_slug],
            "kreis_key": [kreis_key],
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


def test_repulse_centers_moves():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10.0},
        {"x": 0.0, "y": 0.0, "r": 10.0},
    ]

    mod.repulse_centers(centers)

    assert centers[0]["x"] != centers[1]["x"] or centers[0]["y"] != centers[1]["y"]


def test_repulse_centers_no_change_when_truly_far():
    centers = [
        {"x": 0.0, "y": 0.0, "r": 10.0},
        {"x": 1000000.0, "y": 1000000.0, "r": 10.0},
    ]
    before = [(c["x"], c["y"]) for c in centers]

    mod.repulse_centers(centers)

    after = [(c["x"], c["y"]) for c in centers]
    assert after == before


def test_safe_to_file_basic(tmp_path):
    gdf = build_points_gdf()
    out = tmp_path / "out.geojson"

    written = mod.safe_to_file(gdf, out)

    assert written == out
    assert out.exists()


def test_safe_to_file_writes_alt_when_permission_error(tmp_path, monkeypatch):
    gdf = build_points_gdf()
    out = tmp_path / "out.geojson"

    real_to_file = gpd.GeoDataFrame.to_file
    called = {"count": 0}

    def fake_to_file(self, path, driver="GeoJSON", *args, **kwargs):
        called["count"] += 1
        if called["count"] == 1:
            raise PermissionError("locked")
        return real_to_file(self, path, driver=driver, *args, **kwargs)

    monkeypatch.setattr(gpd.GeoDataFrame, "to_file", fake_to_file)

    written = mod.safe_to_file(gdf, out)

    assert written.name == "out_NEW.geojson"
    assert written.exists()


def test_make_pies_for_points_basic(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n > 0
    assert out_file.exists()

    out = gpd.read_file(out_file)
    assert len(out) == 1
    assert set(out["energy_type"]) == {"pv_kw"}


def test_make_pies_for_points_empty_input(tmp_path):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": [],
            "kreis_key": [],
            "kreis_name": [],
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

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n == 0
    assert not out_file.exists()


def test_make_pies_for_points_sets_crs_when_missing(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    gdf = gdf.set_crs(None, allow_override=True)

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n > 0
    out = gpd.read_file(out_file)
    assert out.crs is not None


def test_make_pies_for_points_creates_multiple_slices(tmp_path):
    gdf = build_points_gdf(total_kw=1800, pv_kw=1000, wind_kw=500, biogas_kw=300)

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n == 3
    out = gpd.read_file(out_file)
    assert set(out["energy_type"]) == {"pv_kw", "wind_kw", "biogas_kw"}


def test_make_pies_for_points_marks_biggest_slice_as_label_anchor(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=800, wind_kw=200)

    out_file = tmp_path / "out.geojson"

    mod.make_pies_for_points(gdf, 0, 2000, out_file)

    out = gpd.read_file(out_file)
    pv_row = out[out["energy_type"] == "pv_kw"].iloc[0]
    wind_row = out[out["energy_type"] == "wind_kw"].iloc[0]

    assert pv_row["label_anchor"] == 1
    assert wind_row["label_anchor"] == 0


def test_make_pies_for_points_writes_expected_colors(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    out_file = tmp_path / "out.geojson"

    mod.make_pies_for_points(gdf, 0, 2000, out_file)

    out = gpd.read_file(out_file)
    row = out.iloc[0]
    assert row["color_r"] == 255
    assert row["color_g"] == 255
    assert row["color_b"] == 0


def test_make_pies_for_points_writes_power_gw_and_total_gw(tmp_path):
    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)

    out_file = tmp_path / "out.geojson"

    mod.make_pies_for_points(gdf, 0, 2000, out_file)

    out = gpd.read_file(out_file)
    row = out.iloc[0]
    assert row["power_gw"] == pytest.approx(0.001)
    assert row["total_gw"] == pytest.approx(0.001)


def test_make_pies_for_points_zero_parts_produces_no_output(tmp_path):
    gdf = build_points_gdf(
        total_kw=1000,
        pv_kw=0,
        wind_kw=0,
        hydro_kw=0,
        battery_kw=0,
        biogas_kw=0,
        others_kw=0,
    )

    out_file = tmp_path / "out.geojson"

    n = mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert n == 0
    assert not out_file.exists()


def test_make_pies_for_points_calls_repulse_centers(tmp_path, monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "state_slug": ["test", "test"],
            "kreis_key": ["123", "456"],
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

    called = {"value": False}

    def fake_repulse(centers):
        called["value"] = True

    monkeypatch.setattr(mod, "repulse_centers", fake_repulse)

    out_file = tmp_path / "out.geojson"

    mod.make_pies_for_points(gdf, 0, 2000, out_file)

    assert called["value"] is True


def test_iter_bins_lists_only_valid_bin_dirs(tmp_path, monkeypatch):
    (tmp_path / "2019_2020").mkdir()
    (tmp_path / "pre_1990").mkdir()
    (tmp_path / "not_a_bin").mkdir()
    (tmp_path / "bayern").mkdir()

    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)

    bins = list(mod.iter_bins())

    assert bins == ["2019_2020", "pre_1990"]


def test_main_runs(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
        "r_min_m": 10000,
        "r_max_m": 50000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_dir = base / "test" / "2019_2020"
    state_dir.mkdir(parents=True)
    state_infile = state_dir / "de_test_landkreis_pies_2019_2020.geojson"
    gdf.to_file(state_infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    mod.main()

    out_file = bin_dir / "de_landkreis_pie_2019_2020.geojson"
    assert out_file.exists()

    out_state = state_dir / "de_test_landkreis_pie_2019_2020.geojson"
    assert out_state.exists()


def test_main_updates_global_radius_constants_from_meta(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
        "r_min_m": 12000,
        "r_max_m": 42000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_dir = base / "test" / "2019_2020"
    state_dir.mkdir(parents=True)
    state_infile = state_dir / "de_test_landkreis_pies_2019_2020.geojson"
    gdf.to_file(state_infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    mod.main()

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    expected_radius = 12000 + (1000 / 2000) * (42000 - 12000)
    assert out.iloc[0]["radius_m"] == pytest.approx(expected_radius)


def test_main_bumps_vmax_when_meta_min_equals_max(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "min_total_kw": 1000,
        "max_total_kw": 1000,
        "r_min_m": 10000,
        "r_max_m": 50000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    bin_dir = base / "2019_2020"
    bin_dir.mkdir(parents=True)

    gdf = build_points_gdf(total_kw=1000, pv_kw=1000, wind_kw=0)
    infile = bin_dir / "de_landkreis_pies_2019_2020.geojson"
    gdf.to_file(infile, driver="GeoJSON")

    state_dir = base / "test" / "2019_2020"
    state_dir.mkdir(parents=True)
    state_infile = state_dir / "de_test_landkreis_pies_2019_2020.geojson"
    gdf.to_file(state_infile, driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    mod.main()

    out = gpd.read_file(bin_dir / "de_landkreis_pie_2019_2020.geojson")
    assert out.iloc[0]["radius_m"] == pytest.approx(mod.R_MIN_M)


def test_main_raises_when_global_meta_missing(tmp_path, monkeypatch):
    base = tmp_path
    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_raises_when_no_bin_inputs_found(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 2000,
        "r_min_m": 10000,
        "r_max_m": 50000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (base / "2019_2020").mkdir(parents=True)

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_processes_multiple_bins(tmp_path, monkeypatch):
    base = tmp_path

    meta = {
        "min_total_kw": 0,
        "max_total_kw": 3000,
        "r_min_m": 10000,
        "r_max_m": 50000,
    }
    (base / "_GLOBAL_size_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    for slug, total, pv, wind in [
        ("2019_2020", 1000, 1000, 0),
        ("2021_2022", 3000, 0, 3000),
    ]:
        bin_dir = base / slug
        bin_dir.mkdir(parents=True)

        gdf = build_points_gdf(
            total_kw=total,
            pv_kw=pv,
            wind_kw=wind,
            year_bin_slug=slug,
            year_bin_label=slug,
        )
        gdf.to_file(bin_dir / f"de_landkreis_pies_{slug}.geojson", driver="GeoJSON")

        state_dir = base / "test" / slug
        state_dir.mkdir(parents=True)
        gdf.to_file(state_dir / f"de_test_landkreis_pies_{slug}.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "BASE_DIR", base)
    monkeypatch.setattr(mod, "GLOBAL_META_PATH", base / "_GLOBAL_size_meta.json")

    mod.main()

    assert (base / "2019_2020" / "de_landkreis_pie_2019_2020.geojson").exists()
    assert (base / "2021_2022" / "de_landkreis_pie_2021_2022.geojson").exists()
    assert (base / "test" / "2019_2020" / "de_test_landkreis_pie_2019_2020.geojson").exists()
    assert (base / "test" / "2021_2022" / "de_test_landkreis_pie_2021_2022.geojson").exists()