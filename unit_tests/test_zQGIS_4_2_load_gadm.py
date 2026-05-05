# Filename: unit_tests/test_zQGIS_4_2_load_gadm.py

import os
import importlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.4_2_load_gadm"


# -------------------------------------------------------------------
# Fake Qt classes
# -------------------------------------------------------------------

class FakeQColor:
    def __init__(self, value):
        self.value = value


class FakeQFont:
    def __init__(self, family, size=None):
        self.family = family
        self.size = size


# -------------------------------------------------------------------
# Fake renderer / symbol classes
# -------------------------------------------------------------------

class FakeFillSymbol:
    def __init__(self, props):
        self.props = props

    @staticmethod
    def createSimple(props):
        return FakeFillSymbol(props)


class FakeSingleSymbolRenderer:
    def __init__(self, symbol):
        self.symbol = symbol


class FakeInvertedPolygonRenderer:
    def __init__(self, base_renderer):
        self.base_renderer = base_renderer


# -------------------------------------------------------------------
# Fake labeling classes (imported but not actively used)
# -------------------------------------------------------------------

class FakeQgsPalLayerSettings:
    def __init__(self):
        self.fieldName = None
        self.enabled = False
        self.format = None

    def setFormat(self, fmt):
        self.format = fmt


class FakeQgsTextFormat:
    def __init__(self):
        self.font = None
        self.size = None
        self.color = None

    def setFont(self, font):
        self.font = font

    def setSize(self, size):
        self.size = size

    def setColor(self, color):
        self.color = color


class FakeQgsVectorLayerSimpleLabeling:
    def __init__(self, settings):
        self.settings = settings


# -------------------------------------------------------------------
# Fake layer tree nodes / groups
# -------------------------------------------------------------------

class FakeLayerNode:
    def __init__(self, layer):
        self.layer = layer
        self.visibility_checked = None

    def setItemVisibilityChecked(self, value):
        self.visibility_checked = value


class FakeRoot:
    def __init__(self):
        self.custom_layer_order_enabled = None
        self.layer_nodes = {}

    def setHasCustomLayerOrder(self, value):
        self.custom_layer_order_enabled = value

    def register_layer(self, layer):
        self.layer_nodes[layer.id()] = FakeLayerNode(layer)

    def unregister_layer(self, layer_id):
        self.layer_nodes.pop(layer_id, None)

    def findLayer(self, layer_id):
        return self.layer_nodes.get(layer_id)


# -------------------------------------------------------------------
# Fake layers / project
# -------------------------------------------------------------------

class FakeBaseLayer:
    _counter = 0

    def __init__(self, source, name, provider, is_valid=True):
        FakeBaseLayer._counter += 1
        self._id = f"layer_{FakeBaseLayer._counter}"
        self._source = source
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._renderer = None
        self._opacity = None
        self.repaint_called = False
        self.labeling = None
        self.labels_enabled = None

    def id(self):
        return self._id

    def name(self):
        return self._name

    def source(self):
        return self._source

    def isValid(self):
        return self._is_valid

    def setRenderer(self, renderer):
        self._renderer = renderer

    def renderer(self):
        return self._renderer

    def setOpacity(self, value):
        self._opacity = value

    def opacity(self):
        return self._opacity

    def triggerRepaint(self):
        self.repaint_called = True

    def setLabeling(self, labeling):
        self.labeling = labeling

    def setLabelsEnabled(self, enabled):
        self.labels_enabled = enabled


class FakeVectorLayer(FakeBaseLayer):
    pass


class FakeRasterLayer(FakeBaseLayer):
    pass


class FakeProject:
    def __init__(self, existing_layers=None):
        self.root = FakeRoot()
        self._map_layers = {}
        self.added_layers = []
        self.removed_layer_ids = []

        for lyr in existing_layers or []:
            self._map_layers[lyr.id()] = lyr
            self.root.register_layer(lyr)

    def layerTreeRoot(self):
        return self.root

    def mapLayers(self):
        return self._map_layers

    def addMapLayer(self, layer):
        self._map_layers[layer.id()] = layer
        self.added_layers.append(layer)
        self.root.register_layer(layer)

    def removeMapLayer(self, layer_id):
        self.removed_layer_ids.append(layer_id)
        self._map_layers.pop(layer_id, None)
        self.root.unregister_layer(layer_id)


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

BASE_PATH = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data/gadm41_DEU"
OSM_URL = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]

def gadm_path(filename):
    return os.path.join(BASE_PATH, filename)

def import_module_with_fakes(
    monkeypatch,
    *,
    existing_layers=None,
    vector_validity_by_source=None,
    raster_validity=True,
):
    clear_module()
    FakeBaseLayer._counter = 0

    project = FakeProject(existing_layers=existing_layers or [])
    created_vector_layers = []
    created_raster_layers = []

    vector_validity_by_source = vector_validity_by_source or {}

    qgis_module = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qgis_qtgui = types.ModuleType("qgis.PyQt.QtGui")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    def fake_vector_layer(source, name, provider):
        is_valid = vector_validity_by_source.get(str(source), True)
        layer = FakeVectorLayer(source, name, provider, is_valid=is_valid)
        created_vector_layers.append(layer)
        return layer

    def fake_raster_layer(source, name, provider):
        layer = FakeRasterLayer(source, name, provider, is_valid=raster_validity)
        created_raster_layers.append(layer)
        return layer

    qgis_core.QgsProject = FakeQgsProject
    qgis_core.QgsVectorLayer = fake_vector_layer
    qgis_core.QgsRasterLayer = fake_raster_layer
    qgis_core.QgsPalLayerSettings = FakeQgsPalLayerSettings
    qgis_core.QgsTextFormat = FakeQgsTextFormat
    qgis_core.QgsVectorLayerSimpleLabeling = FakeQgsVectorLayerSimpleLabeling
    qgis_core.QgsFillSymbol = FakeFillSymbol
    qgis_core.QgsSingleSymbolRenderer = FakeSingleSymbolRenderer
    qgis_core.QgsInvertedPolygonRenderer = FakeInvertedPolygonRenderer

    qgis_qtgui.QColor = FakeQColor
    qgis_qtgui.QFont = FakeQFont

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)

    module = importlib.import_module(MODULE_NAME)
    return module, project, created_vector_layers, created_raster_layers


# -------------------------------------------------------------------
# Test helpers
# -------------------------------------------------------------------

def make_existing_layer(name, source="existing_source", provider="ogr", is_valid=True):
    return FakeVectorLayer(source, name, provider, is_valid=is_valid)


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

def test_removes_existing_osm_gadm_and_mask_layers_by_id(monkeypatch):
    osm = make_existing_layer("OpenStreetMap")
    mask = make_existing_layer("DEU_mask")
    gadm1 = make_existing_layer("gadm41_DEU_1")
    gadm2 = make_existing_layer("gadm41_DEU_2")
    other = make_existing_layer("keep_me")

    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[osm, mask, gadm1, gadm2, other],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    removed_ids = set(project.removed_layer_ids)
    assert osm.id() in removed_ids
    assert mask.id() in removed_ids
    assert gadm1.id() in removed_ids
    assert gadm2.id() in removed_ids
    assert other.id() not in removed_ids


def test_disables_custom_layer_order(monkeypatch):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    assert project.root.custom_layer_order_enabled is False


def test_adds_osm_first_when_valid(monkeypatch, capsys):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    assert len(raster_layers) == 1
    osm = raster_layers[0]
    assert osm.source() == OSM_URL
    assert osm.name() == "OpenStreetMap"
    assert osm._provider == "wms"
    assert project.added_layers[0] is osm

    captured = capsys.readouterr()
    assert "🗺️ OpenStreetMap added first (bottom)." in captured.out


def test_prints_warning_when_osm_invalid(monkeypatch, capsys):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=False,
    )

    captured = capsys.readouterr()
    assert "⚠️ Could not add OpenStreetMap." in captured.out


def test_raises_runtime_error_when_mask_layer_invalid(monkeypatch):
    with pytest.raises(RuntimeError, match="Could not load gadm41_DEU_1.json for DEU_mask."):
        import_module_with_fakes(
            monkeypatch,
            existing_layers=[],
            vector_validity_by_source={
                gadm_path("gadm41_DEU_0.json"): False,
            },
            raster_validity=True,
        )


def test_adds_mask_layer_with_inverted_polygon_renderer(monkeypatch, capsys):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    mask = next(layer for layer in vector_layers if layer.name() == "DEU_mask")
    renderer = mask.renderer()

    assert isinstance(renderer, FakeInvertedPolygonRenderer)
    assert isinstance(renderer.base_renderer, FakeSingleSymbolRenderer)
    assert renderer.base_renderer.symbol.props == {"color": "white", "outline_style": "no"}
    assert mask.opacity() == 1.0

    captured = capsys.readouterr()
    assert "🧱 DEU_mask (inverted polygons) added directly from gadm41_DEU_1 source." in captured.out


def test_adds_all_valid_gadm_layers(monkeypatch, capsys):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    gadm_names = [layer.name() for layer in vector_layers if layer.name().startswith("gadm41_DEU_")]
    assert gadm_names == ["gadm41_DEU_1", "gadm41_DEU_2", "gadm41_DEU_3", "gadm41_DEU_4"]

    captured = capsys.readouterr()
    assert "✅ Added: gadm41_DEU_1" in captured.out
    assert "✅ Added: gadm41_DEU_2" in captured.out
    assert "✅ Added: gadm41_DEU_3" in captured.out
    assert "✅ Added: gadm41_DEU_4" in captured.out


def test_prints_failure_for_invalid_gadm_layers(monkeypatch, capsys):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            gadm_path("gadm41_DEU_0.json"): True,
            gadm_path("gadm41_DEU_1.json"): True,
            gadm_path("gadm41_DEU_2.json"): False,
            gadm_path("gadm41_DEU_3.json"): True,
            gadm_path("gadm41_DEU_4.json"): False,
        },
        raster_validity=True,
    )


def test_sets_opacity_and_triggers_repaint_for_loaded_gadm_layers(monkeypatch):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": False,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    loaded_gadm = [
        layer for layer in vector_layers
        if layer.name() in {"gadm41_DEU_1", "gadm41_DEU_2", "gadm41_DEU_4"}
    ]

    for layer in loaded_gadm:
        assert layer.opacity() == 0.35
        assert layer.repaint_called is True


def test_sets_visibility_only_for_layers_in_visible_set(monkeypatch):
    module, project, vector_layers, raster_layers = import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    gadm1 = next(layer for layer in vector_layers if layer.name() == "gadm41_DEU_1")
    gadm2 = next(layer for layer in vector_layers if layer.name() == "gadm41_DEU_2")
    gadm3 = next(layer for layer in vector_layers if layer.name() == "gadm41_DEU_3")
    gadm4 = next(layer for layer in vector_layers if layer.name() == "gadm41_DEU_4")

    node1 = project.root.findLayer(gadm1.id())
    node2 = project.root.findLayer(gadm2.id())
    node3 = project.root.findLayer(gadm3.id())
    node4 = project.root.findLayer(gadm4.id())

    assert node1.visibility_checked is True
    assert node2.visibility_checked is True
    assert node3.visibility_checked is False
    assert node4.visibility_checked is False


def test_final_stack_message_is_printed(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_layers=[],
        vector_validity_by_source={
            f"{BASE_PATH}/gadm41_DEU_0.json": True,
            f"{BASE_PATH}/gadm41_DEU_1.json": True,
            f"{BASE_PATH}/gadm41_DEU_2.json": True,
            f"{BASE_PATH}/gadm41_DEU_3.json": True,
            f"{BASE_PATH}/gadm41_DEU_4.json": True,
        },
        raster_validity=True,
    )

    captured = capsys.readouterr()
    assert "✅ Final stack (bottom → top): OpenStreetMap → DEU_mask (inverted) → GADM_1..4 (1–2 visible)" in captured.out