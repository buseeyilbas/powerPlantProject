import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step3_1_make_landkreis_pie_inputs as mod


def test_normalize_text_basic():
    assert mod.normalize_text("Thüringen") == "thuringen"
    assert mod.normalize_text("Hello World!") == "hello world"


def test_parse_number_variants():
    assert mod.parse_number("1.000") == 1.0
    assert mod.parse_number("1,5") == 1.5
    assert mod.parse_number("1.234,5") == 1234.5


def test_extract_ags5():
    row = pd.Series({"AGS": "12345678"})
    assert mod.extract_ags5(row) == "12345"


def test_first_power_column_direct():
    cols = ["a", "power_kw", "b"]
    assert mod.first_power_column(cols) == "power_kw"


def test_first_power_column_fallback():
    cols = ["Leistung_total"]
    assert mod.first_power_column(cols) == "Leistung_total"


def test_scan_geojsons(tmp_path):
    f = tmp_path / "a.geojson"
    f.write_text("{}", encoding="utf-8")

    files = list(mod.scan_geojsons(tmp_path))
    assert len(files) == 1
    assert files[0].name == "a.geojson"


def test_main_raises_when_no_input(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "INPUT_ROOT", tmp_path)

    with pytest.raises(RuntimeError):
        mod.main()


def test_main_basic(tmp_path, monkeypatch):
    input_root = tmp_path / "input"
    state_dir = input_root / "state1"
    state_dir.mkdir(parents=True)

    gdf = gpd.GeoDataFrame(
        {
            "power_kw": [1000],
            "energy_source_label": ["Solar"],
            "AGS": ["12345"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    file_path = state_dir / "plants.geojson"
    gdf.to_file(file_path, driver="GeoJSON")

    centers = gpd.GeoDataFrame(
        {
            "ags5": ["12345"],
            "state_slug": ["test"],
            "kreis_name": ["Testkreis"],
        },
        geometry=[Point(1, 1)],
        crs="EPSG:4326",
    )

    centers_path = tmp_path / "centers.geojson"
    centers.to_file(centers_path, driver="GeoJSON")

    monkeypatch.setattr(mod, "INPUT_ROOT", input_root)
    monkeypatch.setattr(mod, "CENTERS_PATH", centers_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "out")

    mod.main()

    out_dir = tmp_path / "out"
    assert out_dir.exists()

    nationwide = out_dir / "de_landkreis_pies.geojson"
    assert nationwide.exists()

    g = gpd.read_file(nationwide)
    assert len(g) == 1