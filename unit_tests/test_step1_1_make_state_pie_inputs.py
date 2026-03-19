"""
Unit tests for step1_1_make_state_pie_inputs.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

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
        (None, None),
        ("invalid", None),
    ],
)
def test_parse_number(value, expected):
    assert mod.parse_number(value) == expected


def test_map_bundesland_code():
    assert mod.map_bundesland_code("1403") == "Bayern"
    assert mod.map_bundesland_code("1415") == "Thüringen"
    assert mod.map_bundesland_code("9999") is None
    assert mod.map_bundesland_code(None) is None


def test_normalize_energy_from_value():
    assert mod.normalize_energy("2495") == "Photovoltaik"
    assert mod.normalize_energy("wind") == "Windenergie Onshore"
    assert mod.normalize_energy("hydro") == "Wasserkraft"
    assert mod.normalize_energy("battery") == "Stromspeicher (Battery Storage)"
    assert mod.normalize_energy("biogas") == "Biogas"


def test_normalize_energy_from_filename():
    assert mod.normalize_energy(None, "solar_data.geojson") == "Photovoltaik"
    assert mod.normalize_energy(None, "wind_power.geojson") == "Windenergie Onshore"
    assert mod.normalize_energy(None, "hydro_file.geojson") == "Wasserkraft"
    assert mod.normalize_energy(None, "battery_storage.geojson") == "Stromspeicher (Battery Storage)"


def test_infer_state_from_row_with_bundesland_code():
    row = pd.Series({"Bundesland": "1403"})
    assert mod.infer_state_from_row(row) == "Bayern"


def test_infer_state_from_row_with_name():
    row = pd.Series({"state": "Hessen"})
    assert mod.infer_state_from_row(row) == "Hessen"


def test_infer_state_from_row_with_ags_prefix():
    row = pd.Series({"Gemeindeschluessel": "09162000"})
    assert mod.infer_state_from_row(row) == "Bayern"


def test_first_power_column():
    cols = ["id", "Bruttoleistung", "other"]
    assert mod.first_power_column(cols) == "Bruttoleistung"

    cols2 = ["id", "power_kw"]
    assert mod.first_power_column(cols2) == "power_kw"

    cols3 = ["id", "unknown"]
    assert mod.first_power_column(cols3) is None


def test_scan_geojsons_recursively(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()

    (root / "a.geojson").write_text("{}", encoding="utf-8")
    (sub / "b.geojson").write_text("{}", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")

    found = list(mod.scan_geojsons(str(root)))
    assert len(found) == 2


def test_sep_one_step_moves_points():
    pts = [
        {"x": 10.0, "y": 50.0, "state": "A"},
        {"x": 10.0, "y": 50.0, "state": "B"},
    ]

    changed = mod.sep_one_step(pts, min_km=10, locked_states=set())

    assert changed is True
    assert pts[0]["x"] != pts[1]["x"] or pts[0]["y"] != pts[1]["y"]


def test_main_creates_outputs(tmp_path, monkeypatch):
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
    assert all(out.geometry.geom_type == "Point")


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