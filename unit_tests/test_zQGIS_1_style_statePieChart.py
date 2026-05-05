# Filename: tests/test_zQGIS_1_style_statePieChart.py

import builtins
import importlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.1_style_statePieChart"


class FakeQColor:
    def __init__(self, r, g, b, a=255):
        self._r = r
        self._g = g
        self._b = b
        self._a = a

    def red(self):
        return self._r

    def green(self):
        return self._g

    def blue(self):
        return self._b

    def alpha(self):
        return self._a


class FakeQFont:
    def __init__(self, family, size=None, weight=None):
        self.family = family
        self.size = size
        self.weight = weight


class FakeDataDefinedProperties:
    def __init__(self):
        self.properties = {}

    def setProperty(self, key, value):
        self.properties[key] = value


class FakeQgsProperty:
    @staticmethod
    def fromExpression(expr):
        return {"expression": expr}


class FakeTextBufferSettings:
    def __init__(self):
        self.enabled = None
        self.size = None
        self.color = None

    def setEnabled(self, value):
        self.enabled = value

    def setSize(self, value):
        self.size = value

    def setColor(self, value):
        self.color = value


class FakeTextFormat:
    def __init__(self):
        self.font = None
        self.size = None
        self.color = None
        self.buffer = None

    def setFont(self, font):
        self.font = font

    def setSize(self, size):
        self.size = size

    def setColor(self, color):
        self.color = color

    def setBuffer(self, buffer):
        self.buffer = buffer


class FakePalLayerSettings:
    Size = "Size"
    OverPolygon = "OverPolygon"

    def __init__(self):
        self.enabled = False
        self.isExpression = False
        self.fieldName = None
        self.format = None
        self._ddp = FakeDataDefinedProperties()
        self.placement = None

    def setFormat(self, fmt):
        self.format = fmt

    def dataDefinedProperties(self):
        return self._ddp

    def setDataDefinedProperties(self, ddp):
        self._ddp = ddp


class FakeQgsVectorLayerSimpleLabeling:
    def __init__(self, pal):
        self.pal = pal


class FakeFillSymbol:
    def __init__(self, props):
        self.props = props

    @staticmethod
    def createSimple(props):
        return FakeFillSymbol(props)


class FakeRendererCategory:
    def __init__(self, value, symbol, label):
        self.value = value
        self.symbol = symbol
        self.label = label


class FakeCategorizedSymbolRenderer:
    def __init__(self, field_name, categories):
        self.field_name = field_name
        self.categories = categories


class FakeVectorLayer:
    def __init__(self, source, name, provider, is_valid=True):
        self._source = source
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self.renderer = None
        self.labels_enabled = None
        self.labeling = None
        self.repaint_called = False
        self.id_value = f"{name}_id"

    def name(self):
        return self._name

    def source(self):
        return self._source

    def isValid(self):
        return self._is_valid

    def setRenderer(self, renderer):
        self.renderer = renderer

    def setLabelsEnabled(self, value):
        self.labels_enabled = value

    def setLabeling(self, labeling):
        self.labeling = labeling

    def triggerRepaint(self):
        self.repaint_called = True

    def id(self):
        return self.id_value


class FakeProject:
    def __init__(self, existing_layers=None):
        self._layers = {}
        self.added_layers = []

        if existing_layers:
            for idx, layer in enumerate(existing_layers):
                self._layers[f"layer_{idx}"] = layer

    def mapLayers(self):
        return self._layers

    def addMapLayer(self, layer):
        self.added_layers.append(layer)
        self._layers[f"added_{len(self.added_layers)}"] = layer


class FakeLayerTreeView:
    def __init__(self):
        self.refreshed_layer_ids = []

    def refreshLayerSymbology(self, layer_id):
        self.refreshed_layer_ids.append(layer_id)


class FakeIface:
    def __init__(self):
        self._layer_tree_view = FakeLayerTreeView()

    def layerTreeView(self):
        return self._layer_tree_view


class FakePath:
    existing_paths = set()

    def __init__(self, path):
        self.path = str(path)

    def __truediv__(self, other):
        return FakePath(f"{self.path}\\{other}")

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"FakePath({self.path!r})"

    @property
    def name(self):
        normalized = self.path.replace("/", "\\")
        return normalized.split("\\")[-1]

    def exists(self):
        return self.path in self.existing_paths


def install_fake_qgis_modules(monkeypatch, project, created_layers, new_layer_valid=True):
    qgis_module = types.ModuleType("qgis")
    qgis_core_module = types.ModuleType("qgis.core")
    qgis_pyqt_module = types.ModuleType("qgis.PyQt")
    qgis_qtgui_module = types.ModuleType("qgis.PyQt.QtGui")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    def fake_vector_layer(source, name, provider):
        layer = FakeVectorLayer(source, name, provider, is_valid=new_layer_valid)
        created_layers.append(layer)
        return layer

    qgis_core_module.QgsProject = FakeQgsProject
    qgis_core_module.QgsVectorLayer = fake_vector_layer
    qgis_core_module.QgsCategorizedSymbolRenderer = FakeCategorizedSymbolRenderer
    qgis_core_module.QgsRendererCategory = FakeRendererCategory
    qgis_core_module.QgsFillSymbol = FakeFillSymbol
    qgis_core_module.QgsVectorLayerSimpleLabeling = FakeQgsVectorLayerSimpleLabeling
    qgis_core_module.QgsPalLayerSettings = FakePalLayerSettings
    qgis_core_module.QgsTextFormat = FakeTextFormat
    qgis_core_module.QgsTextBufferSettings = FakeTextBufferSettings
    qgis_core_module.QgsProperty = FakeQgsProperty

    qgis_qtgui_module.QColor = FakeQColor
    qgis_qtgui_module.QFont = FakeQFont

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui_module)


def import_target_module(monkeypatch, existing_layers=None, geojson_exists=True, new_layer_valid=True):
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]

    FakePath.existing_paths = set()
    geojson_path = (
        r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\state_pies"
        r"\de_state_pie.geojson"
    )
    if geojson_exists:
        FakePath.existing_paths.add(geojson_path)

    project = FakeProject(existing_layers=existing_layers)
    created_layers = []
    iface = FakeIface()

    install_fake_qgis_modules(
        monkeypatch=monkeypatch,
        project=project,
        created_layers=created_layers,
        new_layer_valid=new_layer_valid,
    )

    monkeypatch.setattr("pathlib.Path", FakePath, raising=True)
    monkeypatch.setattr(builtins, "iface", iface, raising=False)

    module = importlib.import_module(MODULE_NAME)
    return module, project, created_layers, iface


def test_uses_existing_layer_by_exact_name_without_loading_new_one(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\anything\already_here.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert module.lyr is existing
    assert created_layers == []
    assert project.added_layers == []


def test_uses_existing_layer_by_source_suffix_without_loading_new_one(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="some_other_name",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert module.lyr is existing
    assert created_layers == []
    assert project.added_layers == []


def test_raises_when_geojson_missing_and_no_existing_layer(monkeypatch):
    with pytest.raises(Exception, match="GeoJSON not found"):
        import_target_module(
            monkeypatch,
            existing_layers=[],
            geojson_exists=False,
        )


def test_loads_new_layer_when_missing_and_geojson_exists(monkeypatch):
    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[],
        geojson_exists=True,
        new_layer_valid=True,
    )

    assert len(created_layers) == 1
    new_layer = created_layers[0]

    assert module.lyr is new_layer
    assert new_layer.name() == "de_state_pie"
    assert new_layer.source().endswith("de_state_pie.geojson")
    assert project.added_layers == [new_layer]


def test_raises_when_new_layer_is_invalid(monkeypatch):
    with pytest.raises(Exception, match="Failed to load layer."):
        import_target_module(
            monkeypatch,
            existing_layers=[],
            geojson_exists=True,
            new_layer_valid=False,
        )


def test_renderer_is_categorized_by_energy_type(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    renderer = existing.renderer
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"


def test_renderer_contains_one_category_per_palette_entry(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    renderer = existing.renderer
    assert len(renderer.categories) == len(module.PALETTE)

    category_values = [cat.value for cat in renderer.categories]
    assert category_values == list(module.PALETTE.keys())


def test_renderer_category_symbols_have_expected_style(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    renderer = existing.renderer

    for category in renderer.categories:
        color = module.PALETTE[category.value]
        assert category.label == category.value
        assert category.symbol.props["color"] == (
            f"{color.red()},{color.green()},{color.blue()},255"
        )
        assert category.symbol.props["outline_style"] == "no"
        assert category.symbol.props["outline_color"] == "0,0,0,0"
        assert category.symbol.props["outline_width"] == "0"


def test_labels_are_disabled_when_show_labels_is_false(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert module.SHOW_LABELS is False
    assert existing.labels_enabled is False
    assert existing.labeling is None


def test_repaint_is_triggered(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert existing.repaint_called is True


def test_refresh_layer_symbology_is_called_with_layer_id(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert iface.layerTreeView().refreshed_layer_ids == [existing.id()]


def test_palette_contains_expected_energy_keys(monkeypatch):
    existing = FakeVectorLayer(
        source=r"C:\tmp\de_state_pie.geojson",
        name="de_state_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[existing],
        geojson_exists=False,
    )

    assert list(module.PALETTE.keys()) == [
        "pv_kw",
        "battery_kw",
        "wind_kw",
        "hydro_kw",
        "biogas_kw",
        "others_kw",
    ]


def test_loaded_layer_uses_ogr_provider(monkeypatch):
    module, project, created_layers, iface = import_target_module(
        monkeypatch,
        existing_layers=[],
        geojson_exists=True,
        new_layer_valid=True,
    )

    assert len(created_layers) == 1
    assert created_layers[0]._provider == "ogr"