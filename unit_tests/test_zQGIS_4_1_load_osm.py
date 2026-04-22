# Filename: unit_tests/test_zQGIS_4_1_load_osm.py

import importlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.4_1_load_osm"


# -------------------------------------------------------------------
# Fake QGIS classes
# -------------------------------------------------------------------

class FakeRasterLayer:
    def __init__(self, url, name, provider, *, is_valid=True):
        self.url = url
        self.name = name
        self.provider = provider
        self._is_valid = is_valid

    def isValid(self):
        return self._is_valid


class FakeProject:
    def __init__(self):
        self.added_layers = []

    def addMapLayer(self, layer):
        self.added_layers.append(layer)


# -------------------------------------------------------------------
# Import helper
# -------------------------------------------------------------------

def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(monkeypatch, *, raster_is_valid):
    clear_module()

    project = FakeProject()
    created_layers = []

    qgis_module = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")
    qgis_utils = types.ModuleType("qgis.utils")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    def fake_raster_layer(url, name, provider):
        layer = FakeRasterLayer(url, name, provider, is_valid=raster_is_valid)
        created_layers.append(layer)
        return layer

    qgis_core.QgsProject = FakeQgsProject
    qgis_core.QgsRasterLayer = fake_raster_layer

    # Script imports iface but does not use it
    qgis_utils.iface = object()

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.utils", qgis_utils)

    module = importlib.import_module(MODULE_NAME)
    return module, project, created_layers


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

def test_creates_osm_raster_layer_with_expected_url_name_and_provider(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        raster_is_valid=True,
    )

    assert len(created_layers) == 1
    layer = created_layers[0]

    assert layer.url == "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert layer.name == "OpenStreetMap"
    assert layer.provider == "wms"


def test_adds_layer_to_project_when_raster_layer_is_valid(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        raster_is_valid=True,
    )

    assert len(created_layers) == 1
    assert project.added_layers == [created_layers[0]]


def test_prints_success_message_when_raster_layer_is_valid(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        raster_is_valid=True,
    )

    captured = capsys.readouterr()
    assert "🗺️ OpenStreetMap layer added." in captured.out


def test_does_not_add_layer_to_project_when_raster_layer_is_invalid(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        raster_is_valid=False,
    )

    assert len(created_layers) == 1
    assert project.added_layers == []


def test_prints_failure_message_when_raster_layer_is_invalid(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        raster_is_valid=False,
    )

    captured = capsys.readouterr()
    assert "❌ Failed to load OpenStreetMap layer." in captured.out


def test_project_instance_is_used_for_layer_addition(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        raster_is_valid=True,
    )

    assert len(project.added_layers) == 1
    assert project.added_layers[0] is created_layers[0]