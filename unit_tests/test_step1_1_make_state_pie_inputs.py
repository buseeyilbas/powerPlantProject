"""
Unit tests for step1_1_make_state_pie_inputs.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_1_make_state_pie_inputs as mod


def test_normalize_text_basic():
    assert mod.normalize_text("Bayern") == "bayern"
    assert mod.normalize_text("Baden-Württemberg") == "baden wurttemberg"
    assert mod.normalize_text("  NRW  ") == "nrw"
    assert mod.normalize_text(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.5", 10.5),
        ("1.234,56", 1234.56),
        ("94.000", 94.0),
        ("250", 250.0),
        (100, 100.0),
        (100.5, 100.5),
        (None, None),
        ("invalid", None),
        ("", None),
    ],
)
def test_parse_number(value, expected):
    assert mod.parse_number(value) == expected


def test_map_bundesland_code_basic():
    assert mod.map_bundesland_code("1403") == "Bayern"
    assert mod.map_bundesland_code("1415") == "Thüringen"
    assert mod.map_bundesland_code("9999") is None
    assert mod.map_bundesland_code(None) is None


def test_map_bundesland_code_decimal_string():
    assert mod.map_bundesland_code("1406.0") == "Hamburg"


def test_normalize_energy_from_value():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"
    assert mod.normalize_energy("hydro") == "Wasserkraft"
    assert mod.normalize_energy("battery") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("biogas") == "Biogas"
    assert mod.normalize_energy("unknown_value") == "Unknown"


def test_normalize_energy_from_filename():
    assert mod.normalize_energy(None, "solar_data.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "wind_power.geojson") == "Windenergie Onshore"
    assert mod.normalize_energy(None, "hydro_file.geojson") == "Wasserkraft"
    assert mod.normalize_energy(None, "battery_storage.geojson") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy(None, "biogas_file.geojson") == "Biogas"
    assert mod.normalize_energy(None, "other.geojson") == "Unknown"


def test_infer_state_from_row_with_bundesland_code():
    row = pd.Series({"Bundesland": "1403"})
    assert mod.infer_state_from_row(row) == "Bayern"


def test_infer_state_from_row_with_state_field():
    row = pd.Series({"state": "Hessen"})
    assert mod.infer_state_from_row(row) == "Hessen"


def test_infer_state_from_row_with_bundesland_name_field():
    row = pd.Series({"BundeslandName": "Sachsen"})
    assert mod.infer_state_from_row(row) == "Sachsen"


def test_infer_state_from_row_with_city_state_hint():
    row = pd.Series({"Landkreis": "Berlin"})
    assert mod.infer_state_from_row(row) == "Berlin"


def test_infer_state_from_row_with_ags_prefix():
    row = pd.Series({"Gemeindeschluessel": "09162000"})
    assert mod.infer_state_from_row(row) == "Bayern"


def test_infer_state_from_row_returns_none_when_unknown():
    row = pd.Series({"foo": "bar"})
    assert mod.infer_state_from_row(row) is None


def test_infer_state_from_path():
    p = Path("/tmp/by_state_4_checks/thueringen/test.geojson")
    assert mod.infer_state_from_path(p) == "Thüringen"

    p2 = Path("/tmp/by_state_4_checks/bayern/test.geojson")
    assert mod.infer_state_from_path(p2) == "Bayern"

    p3 = Path("/tmp/by_state_4_checks/unknown/test.geojson")
    assert mod.infer_state_from_path(p3) is None


def test_scan_geojsons_recursively(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()

    (root / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")

    found = sorted(p.name for p in mod.scan_geojsons(str(root)))
    assert found == ["a.geojson", "b.geojson"]


def test_first_power_column_direct_matches():
    cols = ["id", "Bruttoleistung", "other"]
    assert mod.first_power_column(cols) == "Bruttoleistung"

    cols2 = ["id", "power_kw"]
    assert mod.first_power_column(cols2) == "power_kw"

    cols3 = ["id", "unknown"]
    assert mod.first_power_column(cols3) is None


def test_first_power_column_normalized_match():
    cols = ["Installed Power KW"]
    assert mod.first_power_column(cols) == "Installed Power KW"

    cols2 = ["Gesamt Leistung"]
    assert mod.first_power_column(cols2) == "Gesamt Leistung"


def test_sep_one_step_moves_points():
    pts = [
        {"x": 10.0, "y": 50.0, "state": "A"},
        {"x": 10.0, "y": 50.0, "state": "B"},
    ]

    changed = mod.sep_one_step(pts, min_km=10, locked_states=set())

    assert changed is True
    assert pts[0]["x"] != pts[1]["x"] or pts[0]["y"] != pts[1]["y"]


def test_sep_one_step_does_not_move_two_locked_points():
    pts = [
        {"x": 10.0, "y": 50.0, "state": "Berlin"},
        {"x": 10.01, "y": 50.01, "state": "Hamburg"},
    ]

    original = [(p["x"], p["y"]) for p in pts]
    changed = mod.sep_one_step(pts, min_km=1000, locked_states={"Berlin", "Hamburg"})

    assert changed is False
    assert [(p["x"], p["y"]) for p in pts] == original


def test_sep_one_step_moves_only_unlocked_when_other_locked():
    pts = [
        {"x": 10.0, "y": 50.0, "state": "Berlin"},
        {"x": 10.01, "y": 50.01, "state": "A"},
    ]

    original_locked = (pts[0]["x"], pts[0]["y"])
    changed = mod.sep_one_step(pts, min_km=1000, locked_states={"Berlin"})

    assert changed is True
    assert (pts[0]["x"], pts[0]["y"]) == original_locked
    assert (pts[1]["x"], pts[1]["y"]) != (10.01, 50.01)


def test_main_creates_outputs_and_meta(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "Bundesland": ["1403", "1403", "1415"],
            "energy_source_label": ["2495", "wind", "hydro"],
            "power_kw": [1000, 2000, 500],
        },
        geometry=[
            Point(10.0, 50.0),
            Point(10.5, 50.5),
            Point(11.0, 51.0),
        ],
        crs="EPSG:4326",
    )

    file_path = input_dir / "test.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    mod.main()

    out_geo = output_dir / "de_state_pies.geojson"
    out_meta = output_dir / "state_pie_style_meta.json"

    assert out_geo.exists()
    assert out_meta.exists()

    out = gpd.read_file(out_geo)
    assert len(out) == 2
    assert "total_kw" in out.columns
    assert "pv_kw" in out.columns
    assert "wind_kw" in out.columns
    assert "hydro_kw" in out.columns
    assert all(out.geometry.geom_type == "Point")

    meta = json.loads(out_meta.read_text(encoding="utf-8"))
    assert "min_total_kw" in meta
    assert "max_total_kw" in meta
    assert meta["name_field"] == "state_name"


def test_main_uses_fixed_anchor_for_locked_state(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "Bundesland": ["1401"],
            "energy_source_label": ["2495"],
            "power_kw": [1000],
        },
        geometry=[Point(1.0, 1.0)],
        crs="EPSG:4326",
    )

    file_path = input_dir / "berlin.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    mod.main()

    out = gpd.read_file(output_dir / "de_state_pies.geojson")
    row = out.loc[out["state_name"] == "Berlin"].iloc[0]

    exp_x, exp_y = mod.FIXED_ANCHORS["Berlin"]
    assert row.geometry.x == pytest.approx(exp_x)
    assert row.geometry.y == pytest.approx(exp_y)


def test_main_explodes_multipoint(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "Bundesland": ["1403"],
            "energy_source_label": ["2495"],
            "power_kw": [1000],
        },
        geometry=[MultiPoint([(10.0, 50.0), (10.2, 50.2)])],
        crs="EPSG:4326",
    )

    file_path = input_dir / "multi.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    mod.main()

    out = gpd.read_file(output_dir / "de_state_pies.geojson")
    assert len(out) == 1
    assert out.iloc[0]["total_kw"] == 2000.0


def test_main_skips_invalid_geojson_file_and_continues(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    good = gpd.GeoDataFrame(
        {
            "Bundesland": ["1403"],
            "energy_source_label": ["2495"],
            "power_kw": [1000],
        },
        geometry=[Point(10.0, 50.0)],
        crs="EPSG:4326",
    )
    good.to_file(input_dir / "good.geojson", driver="GeoJSON")

    (input_dir / "bad.geojson").write_text("{ invalid json", encoding="utf-8")

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    mod.main()

    out = gpd.read_file(output_dir / "de_state_pies.geojson")
    assert len(out) == 1
    assert out.iloc[0]["state_name"] == "Bayern"


def test_main_raises_when_no_files(tmp_path, monkeypatch):
    input_dir = tmp_path / "empty"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    with pytest.raises(RuntimeError, match="No .geojson files"):
        mod.main()


def test_main_raises_when_no_valid_data(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    gdf = gpd.GeoDataFrame(
        {
            "Bundesland": ["1403"],
            "power_kw": [None],
        },
        geometry=[Point(10.0, 50.0)],
        crs="EPSG:4326",
    )

    file_path = input_dir / "bad.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(mod, "OUTPUT_DIR", str(output_dir))

    with pytest.raises(RuntimeError, match="No usable point features"):
        mod.main()