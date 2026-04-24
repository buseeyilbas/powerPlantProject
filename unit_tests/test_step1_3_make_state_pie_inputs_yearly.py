"""
Unit tests for step1_3_make_state_pie_inputs_yearly.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point, Polygon

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_3_make_state_pie_inputs_yearly as mod


def write_point_centers(path: Path, rows):
    attrs = []
    geoms = []
    for r in rows:
        rr = dict(r)
        x = rr.pop("x")
        y = rr.pop("y")
        attrs.append(rr)
        geoms.append(Point(x, y))
    gdf = gpd.GeoDataFrame(attrs, geometry=geoms, crs="EPSG:4326")
    gdf.to_file(path, driver="GeoJSON")


def write_polygon_centers(path: Path, rows):
    polys = []
    attrs = []
    for r in rows:
        x = r["x"]
        y = r["y"]
        poly = Polygon(
            [
                (x - 0.1, y - 0.1),
                (x + 0.1, y - 0.1),
                (x + 0.1, y + 0.1),
                (x - 0.1, y + 0.1),
                (x - 0.1, y - 0.1),
            ]
        )
        polys.append(poly)
        attrs.append({"name": r["name"]})
    gdf = gpd.GeoDataFrame(attrs, geometry=polys, crs="EPSG:4326")
    gdf.to_file(path, driver="GeoJSON")


def test_normalize_text_basic():
    assert mod.normalize_text("Bayern") == "bayern"
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Nordrhein-Westfalen") == "nordrhein-westfalen"
    assert mod.normalize_text(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", 10.0),
        ("10,5", 10.5),
        ("1.000,5", 1000.5),
        ("1.000", 1.0),
        (100, 100.0),
        (100.5, 100.5),
        (None, None),
        ("abc", None),
        ("", None),
    ],
)
def test_parse_number(value, expected):
    assert mod.parse_number(value) == expected


def test_normalize_energy_from_code():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("2497") == "Windenergie Onshore"
    assert mod.normalize_energy("2498") == "Wasserkraft"
    assert mod.normalize_energy("2496") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("2493") == "Biogas"


def test_normalize_energy_from_text():
    assert mod.normalize_energy("solar") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"
    assert mod.normalize_energy("hydro") == "Wasserkraft"
    assert mod.normalize_energy("battery") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("biogas") == "Biogas"
    assert mod.normalize_energy("mystery") == "Unknown"


def test_normalize_energy_from_filename_hint():
    assert mod.normalize_energy(None, "solar_data.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "wind_assets.geojson") == "Windenergie Onshore"
    assert mod.normalize_energy(None, "hydro_assets.geojson") == "Wasserkraft"
    assert mod.normalize_energy(None, "battery_assets.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "biogas_assets.geojson") == "Biogas"
    assert mod.normalize_energy(None, "other.geojson") == "Unknown"


def test_extract_year_from_string():
    row = {"commissioning_date": "2020-05-01"}
    assert mod.extract_year(row) == 2020


def test_extract_year_from_year_column():
    row = {"year": 2015}
    assert mod.extract_year(row) == 2015


def test_extract_year_from_baujahr():
    row = {"Baujahr": "1998"}
    assert mod.extract_year(row) == 1998


def test_extract_year_from_filename():
    row = {}
    assert mod.extract_year(row, "plants_2018.geojson") == 2018


def test_extract_year_returns_none_for_unknown():
    row = {"commissioning_date": "abcd"}
    assert mod.extract_year(row, "no_year_here.geojson") is None


def test_year_to_bin_basic():
    slug, label = mod.year_to_bin(2020)
    assert slug == "2019_2020"
    assert label == "2019–2020"


def test_year_to_bin_unknown():
    slug, label = mod.year_to_bin(None)
    assert slug == "unknown"
    assert label == "Unknown / NA"


def test_scan_geojsons(tmp_path):
    root = tmp_path
    sub = root / "sub"
    sub.mkdir()

    (root / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")

    files = sorted(p.name for p in mod.scan_geojsons(root))
    assert files == ["a.geojson", "b.geojson"]


def test_load_state_centers_from_polygon_file(tmp_path, monkeypatch):
    base_fixed = tmp_path / "fixed"
    base_fixed.mkdir()

    poly_path = base_fixed / "de_state_pie.geojson"
    write_polygon_centers(
        poly_path,
        [
            {"name": "Bayern", "x": 10.0, "y": 50.0},
            {"name": "Hessen", "x": 9.0, "y": 51.0},
        ],
    )

    monkeypatch.setattr(mod, "BASE_FIXED", base_fixed)

    centers = mod.load_state_centers()

    assert "Bayern" in centers
    assert "Hessen" in centers
    assert isinstance(centers["Bayern"][0], float)
    assert isinstance(centers["Bayern"][1], float)


def test_load_state_centers_falls_back_to_point_file(tmp_path, monkeypatch):
    base_fixed = tmp_path / "fixed"
    base_fixed.mkdir()

    pts_path = base_fixed / "de_state_pies.geojson"
    write_point_centers(
        pts_path,
        [
            {"state_name": "Bayern", "x": 10.0, "y": 50.0},
            {"state_name": "Hessen", "x": 9.0, "y": 51.0},
        ],
    )

    monkeypatch.setattr(mod, "BASE_FIXED", base_fixed)

    centers = mod.load_state_centers()

    assert centers["Bayern"] == (10.0, 50.0)
    assert centers["Hessen"] == (9.0, 51.0)


def test_load_state_centers_returns_empty_when_no_files(tmp_path, monkeypatch):
    base_fixed = tmp_path / "fixed"
    base_fixed.mkdir()

    monkeypatch.setattr(mod, "BASE_FIXED", base_fixed)

    centers = mod.load_state_centers()

    assert centers == {}


def test_empty_parts_dict():
    d = mod.empty_parts_dict()
    assert "pv_kw" in d
    assert "others_kw" in d
    assert all(v == 0.0 for v in d.values())


def test_add_parts_inplace():
    a = mod.empty_parts_dict()
    b = mod.empty_parts_dict()

    b["pv_kw"] = 100
    b["others_kw"] = 50
    mod.add_parts_inplace(a, b)

    assert a["pv_kw"] == 100
    assert a["others_kw"] == 50


def test_main_raises_when_no_state_dirs(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    input_root.mkdir()

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path / "fixed")

    with pytest.raises(RuntimeError, match="No state folders"):
        mod.main()


def test_main_raises_when_no_usable_features_after_parsing(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path / "fixed")

    with pytest.raises(RuntimeError, match="No usable features after parsing"):
        mod.main()


def test_main_completes_with_unknown_years_filtered_out(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["unknown-date"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", tmp_path / "out")
    monkeypatch.setattr(mod, "BASE_FIXED", tmp_path / "fixed")
    monkeypatch.setattr(mod, "INCLUDE_UNKNOWN", False)

    mod.main()

    out_base = tmp_path / "out"
    assert out_base.exists()
    assert not (out_base / "de_yearly_totals.json").exists()
    assert not (out_base / "de_yearly_totals_chart.geojson").exists()
    assert not any(out_base.glob("*/de_state_pies_*.geojson"))
    assert not (out_base / "de_energy_legend_points.geojson").exists()
    assert not (out_base / "de_pie_size_legend_circles.geojson").exists()
    assert not (out_base / "de_pie_size_legend_labels.geojson").exists()
    assert not (out_base / "de_legend_frames.geojson").exists()


def test_main_basic_flow_creates_outputs(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 11.0, "y": 48.5}],
    )

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)
    monkeypatch.setattr(mod, "GLOBAL_META", out_base / "_GLOBAL_style_meta.json")

    mod.main()

    pts_path = out_base / "2019_2020" / "de_state_pies_2019_2020.geojson"
    meta_path = out_base / "2019_2020" / "state_pie_style_meta_2019_2020.json"
    global_meta = out_base / "_GLOBAL_style_meta.json"
    totals_json = out_base / "de_yearly_totals.json"
    chart_geo = out_base / "de_yearly_totals_chart.geojson"
    chart_guides = out_base / "de_yearly_totals_chart_guides.geojson"
    col_bars = out_base / "de_state_totals_columnChart_bars.geojson"
    col_labels = out_base / "de_state_totals_columnChart_labels.geojson"
    legend = out_base / "de_energy_legend_points.geojson"
    pie_legend_circles = out_base / "de_pie_size_legend_circles.geojson"
    pie_legend_labels = out_base / "de_pie_size_legend_labels.geojson"
    legend_frames = out_base / "de_legend_frames.geojson"

    assert pts_path.exists()
    assert meta_path.exists()
    assert global_meta.exists()
    assert totals_json.exists()
    assert chart_geo.exists()
    assert chart_guides.exists()
    assert col_bars.exists()
    assert col_labels.exists()
    assert legend.exists()
    assert pie_legend_circles.exists()
    assert pie_legend_labels.exists()
    assert legend_frames.exists()

    pts = gpd.read_file(pts_path)
    assert len(pts) == 1
    assert pts.iloc[0]["state_name"] == "Bayern"
    assert pts.iloc[0]["state_abbrev"] == "BY"
    assert pts.iloc[0]["pv_kw"] == 1000
    assert pts.iloc[0]["total_kw"] == 1000
    assert pts.iloc[0].geometry.x == pytest.approx(11.0)
    assert pts.iloc[0].geometry.y == pytest.approx(48.5)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["is_cumulative"] is True
    assert meta["name_field"] == "state_name"
    assert meta["state_abbrev_field"] == "state_abbrev"
    assert "min_total_kw" in meta
    assert "max_total_kw" in meta

    gmeta = json.loads(global_meta.read_text(encoding="utf-8"))
    assert gmeta["min_total_kw"] <= gmeta["max_total_kw"]
    assert gmeta["radius_min_m"] == mod.LEGEND_R_MIN_M
    assert gmeta["radius_max_m"] == mod.LEGEND_R_MAX_M

    legend_gdf = gpd.read_file(legend)
    assert "legend_title" in set(legend_gdf["energy_type"])
    assert "Energy Type Color Legend" in set(legend_gdf["legend_label"])

    pie_lbl_gdf = gpd.read_file(pie_legend_labels)
    assert "title" in set(pie_lbl_gdf["kind"])
    assert "Pie Size Legend" in set(pie_lbl_gdf["legend_label"])

    circles_gdf = gpd.read_file(pie_legend_circles)
    assert len(circles_gdf) == len(mod.PIE_LEGEND_VALUES_GW)
    assert set(circles_gdf["legend_gw"]) == set(float(v) for v in mod.PIE_LEGEND_VALUES_GW)

    frames_gdf = gpd.read_file(legend_frames)
    assert set(frames_gdf["frame_type"]) == {"energy_legend", "pie_size_legend"}


def test_column_chart_labels_use_state_abbrev(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 11.0, "y": 48.5}],
    )

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    labels = gpd.read_file(out_base / "de_state_totals_columnChart_labels.geojson")

    state_rows = labels[
        (labels["kind"] == "state_label") &
        (labels["state_number"] == 2)
    ]
    assert len(state_rows) >= 1
    assert set(state_rows["state_abbrev"]) == {"BY"}

    value_rows = labels[
        (labels["kind"] == "value_label") &
        (labels["state_number"] == 2)
    ]
    assert len(value_rows) >= 1

    title_rows = labels[labels["kind"] == "title"]
    assert len(title_rows) == 1
    assert title_rows.iloc[0]["year_bin_label"] == mod.UNIFIED_TITLE_TEXT["column_chart"]


def test_main_uses_polygon_baseline_before_point_fallback(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_polygon_centers(
        fixed / "de_state_pie.geojson",
        [{"name": "Bayern", "x": 12.0, "y": 49.0}],
    )
    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 1.0, "y": 1.0}],
    )

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    pts = gpd.read_file(out_base / "2019_2020" / "de_state_pies_2019_2020.geojson")
    assert pts.iloc[0].geometry.x == pytest.approx(12.0, abs=0.2)
    assert pts.iloc[0].geometry.y == pytest.approx(49.0, abs=0.2)


def test_main_falls_back_to_mean_coords_without_baseline(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 2000],
            "commissioning_date": ["2020-01-01", "2020-06-01"],
            "energy_source_label": ["solar", "wind"],
        },
        geometry=[Point(10, 50), Point(12, 52)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    pts = gpd.read_file(out_base / "2019_2020" / "de_state_pies_2019_2020.geojson")
    assert pts.iloc[0].geometry.x == pytest.approx(11.0)
    assert pts.iloc[0].geometry.y == pytest.approx(51.0)


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 11.0, "y": 48.5}],
    )

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[MultiPoint([(10, 50), (10.1, 50.1)])],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    pts = gpd.read_file(out_base / "2019_2020" / "de_state_pies_2019_2020.geojson")
    assert pts.iloc[0]["pv_kw"] == 2000.0
    assert pts.iloc[0]["total_kw"] == 2000.0


def test_main_cumulative_growth_across_bins(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 11.0, "y": 48.5}],
    )

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000, 2000],
            "commissioning_date": ["2019-01-01", "2021-01-01"],
            "energy_source_label": ["solar", "wind"],
        },
        geometry=[Point(10, 50), Point(10.5, 50.5)],
        crs="EPSG:4326",
    )
    gdf.to_file(state_dir / "plants.geojson", driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    g_2019 = gpd.read_file(out_base / "2019_2020" / "de_state_pies_2019_2020.geojson")
    g_2021 = gpd.read_file(out_base / "2021_2022" / "de_state_pies_2021_2022.geojson")

    assert g_2019.iloc[0]["total_kw"] == 1000.0
    assert g_2021.iloc[0]["total_kw"] == 3000.0
    assert g_2021.iloc[0]["pv_kw"] == 1000.0
    assert g_2021.iloc[0]["wind_kw"] == 2000.0


def test_main_skips_bad_geojson_and_continues(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    out_base = tmp_path / "out"
    fixed = tmp_path / "fixed"

    state_dir = input_root / "bayern"
    state_dir.mkdir(parents=True)
    fixed.mkdir()

    write_point_centers(
        fixed / "de_state_pies.geojson",
        [{"state_name": "Bayern", "x": 11.0, "y": 48.5}],
    )

    good = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "commissioning_date": ["2020-01-01"],
            "energy_source_label": ["solar"],
        },
        geometry=[Point(10, 50)],
        crs="EPSG:4326",
    )
    good.to_file(state_dir / "good.geojson", driver="GeoJSON")
    (state_dir / "bad.geojson").write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "OUT_BASE", out_base)
    monkeypatch.setattr(mod, "BASE_FIXED", fixed)

    mod.main()

    pts = gpd.read_file(out_base / "2019_2020" / "de_state_pies_2019_2020.geojson")
    assert len(pts) == 1
    assert pts.iloc[0]["state_name"] == "Bayern"