# Filename: unit_tests/test_zQGIS_2_style_thueringen_statewise_landkreisPieChart_yearly.py

import builtins
import importlib
import io
import json
import pathlib
import sys
import types
from collections import OrderedDict

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.2_style_thueringen_statewise_landkreisPieChart_yearly"


# -------------------------------------------------------------------
# Fake Qt classes
# -------------------------------------------------------------------

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
    Bold = 75

    def __init__(self, family, size=None, weight=None):
        self.family = family
        self.size = size
        self.weight = weight


# -------------------------------------------------------------------
# Fake labeling / text classes
# -------------------------------------------------------------------

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
    OverPoint = "OverPoint"

    def __init__(self):
        self.enabled = False
        self.isExpression = False
        self.fieldName = None
        self.placement = None
        self.xOffset = 0.0
        self.yOffset = 0.0
        self.format = None

    def setFormat(self, fmt):
        self.format = fmt


class FakeQgsVectorLayerSimpleLabeling:
    def __init__(self, pal):
        self.pal = pal


class FakeRule:
    def __init__(self, pal):
        self.pal = pal
        self.filter_expression = None
        self.children = []

    def setFilterExpression(self, expr):
        self.filter_expression = expr

    def appendChild(self, rule):
        self.children.append(rule)


class FakeQgsRuleBasedLabeling:
    Rule = FakeRule

    def __init__(self, root_rule):
        self.root_rule = root_rule


# -------------------------------------------------------------------
# Fake symbols / renderers
# -------------------------------------------------------------------

class FakeFillSymbol:
    def __init__(self, props):
        self.props = props
        self.output_unit = None

    @staticmethod
    def createSimple(props):
        return FakeFillSymbol(props)

    def setOutputUnit(self, unit):
        self.output_unit = unit


class FakeMarkerSymbol:
    def __init__(self, props):
        self.props = props

    @staticmethod
    def createSimple(props):
        return FakeMarkerSymbol(props)


class FakeLineSymbolLayer:
    def __init__(self):
        self.width_unit = None

    def setWidthUnit(self, unit):
        self.width_unit = unit


class FakeLineSymbol:
    def __init__(self, props):
        self.props = props
        self.width_unit = None
        self.layer0 = FakeLineSymbolLayer()

    @staticmethod
    def createSimple(props):
        return FakeLineSymbol(props)

    def setWidthUnit(self, unit):
        self.width_unit = unit

    def symbolLayer(self, idx):
        assert idx == 0
        return self.layer0


class FakeRendererCategory:
    def __init__(self, value, symbol, label):
        self.value = value
        self.symbol = symbol
        self.label = label


class FakeCategorizedSymbolRenderer:
    def __init__(self, field_name, categories):
        self.field_name = field_name
        self.categories = categories


class FakeSingleSymbolRenderer:
    def __init__(self, symbol):
        self.symbol = symbol


class FakeQgsUnitTypes:
    RenderMillimeters = "RenderMillimeters"


# -------------------------------------------------------------------
# Fake geometry / features / fields
# -------------------------------------------------------------------

class FakeQgsPointXY:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class FakeGeometry:
    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload

    @staticmethod
    def fromPointXY(point):
        return FakeGeometry("point", point)

    @staticmethod
    def fromPolygonXY(rings):
        return FakeGeometry("polygon", rings)


class FakeField:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeFeature:
    def __init__(self, fields=None, attrs=None):
        self._fields = fields or []
        self.geometry = None
        self.attrs = dict(attrs or {})

    def setGeometry(self, geometry):
        self.geometry = geometry

    def __getitem__(self, key):
        return self.attrs.get(key)

    def __setitem__(self, key, value):
        self.attrs[key] = value


# -------------------------------------------------------------------
# Fake provider / layer / groups / project
# -------------------------------------------------------------------

class FakeProvider:
    def __init__(self, layer):
        self.layer = layer
        self.added_features = []

    def addFeatures(self, features):
        self.added_features.extend(features)
        self.layer._features.extend(features)


class FakeVectorLayer:
    def __init__(
        self,
        source,
        name,
        provider,
        *,
        is_valid=True,
        field_names=None,
        features=None,
    ):
        self._source = str(source)
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._field_names = field_names or []
        self._renderer = None
        self._labels_enabled = None
        self._labeling = None
        self._subset_string = None
        self._repaint_called = False
        self._provider_obj = FakeProvider(self)
        self._features = []
        self._iter_features = list(features or [])

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

    def setLabelsEnabled(self, enabled):
        self._labels_enabled = enabled

    def labelsEnabled(self):
        return self._labels_enabled

    def setLabeling(self, labeling):
        self._labeling = labeling

    def labeling(self):
        return self._labeling

    def triggerRepaint(self):
        self._repaint_called = True

    def repaintCalled(self):
        return self._repaint_called

    def setSubsetString(self, subset):
        self._subset_string = subset

    def subsetString(self):
        return self._subset_string

    def fields(self):
        return [FakeField(name) for name in self._field_names]

    def dataProvider(self):
        return self._provider_obj

    def updateExtents(self):
        return None

    def getFeatures(self):
        for feat in self._iter_features:
            yield feat


class FakeLayerTreeGroup:
    def __init__(self, name):
        self.name = name
        self.groups = OrderedDict()
        self.layers = []

    def findGroup(self, name):
        return self.groups.get(name)

    def addGroup(self, name):
        grp = FakeLayerTreeGroup(name)
        self.groups[name] = grp
        return grp

    def addLayer(self, layer):
        self.layers.append(layer)


class FakeRoot(FakeLayerTreeGroup):
    def removeChildNode(self, node):
        for key, value in list(self.groups.items()):
            if value is node:
                del self.groups[key]
                return


class FakeProject:
    def __init__(self):
        self.root = FakeRoot("root")
        self.added_layers = []

    def layerTreeRoot(self):
        return self.root

    def addMapLayer(self, layer, add_to_root=True):
        self.added_layers.append((layer, add_to_root))


# -------------------------------------------------------------------
# Fake path
# -------------------------------------------------------------------

class FakePath:
    existing_paths = set()

    def __init__(self, path):
        self.path = str(path)

    def __truediv__(self, other):
        sep = "\\" if "\\" in self.path else "/"
        if self.path.endswith(sep):
            return FakePath(f"{self.path}{other}")
        return FakePath(f"{self.path}{sep}{other}")

    def __str__(self):
        return self.path

    def __repr__(self):
        return f"FakePath({self.path!r})"

    def __lt__(self, other):
        return str(self.path) < str(other.path)

    @property
    def name(self):
        normalized = self.path.replace("/", "\\")
        return normalized.split("\\")[-1]

    @property
    def parent(self):
        normalized = self.path.replace("/", "\\")
        if "\\" not in normalized:
            return FakePath(normalized)
        return FakePath(normalized.rsplit("\\", 1)[0])

    def exists(self):
        return self.path in self.existing_paths


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

ROOT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_statewise_landkreis_pies_yearly"
CHART_PATH = ROOT_DIR + r"\thueringen_landkreis_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR + r"\thueringen_landkreis_yearly_totals_chart_guides.geojson"
FRAME_PATH = ROOT_DIR + r"\thueringen_landkreis_yearly_totals_chart_frame.geojson"
LEGEND_PATH = ROOT_DIR + r"\thueringen_landkreis_energy_legend_points.geojson"
NUMBER_POINTS_PATH = ROOT_DIR + r"\thueringen_landkreis_number_points.geojson"
NUMBER_LIST_PATH = ROOT_DIR + r"\thueringen_landkreis_number_list_points.geojson"
COL_BARS_PATH = ROOT_DIR + r"\thu_landkreis_totals_columnChart_bars.geojson"
COL_LABELS_PATH = ROOT_DIR + r"\thu_landkreis_totals_columnChart_labels.geojson"
CENTERS_PATH = (
    r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts"
    r"\thueringen_landkreis_centers\thueringen_landkreis_centers.geojson"
)
COL_FRAME_PATH = ROOT_DIR + r"\thu_landkreis_totals_columnChart_frame.geojson"


def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def install_fake_qgis(monkeypatch, project, vector_layer_factory):
    qgis_module = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qgis_qtgui = types.ModuleType("qgis.PyQt.QtGui")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    qgis_core.QgsProject = FakeQgsProject
    qgis_core.QgsVectorLayer = vector_layer_factory
    qgis_core.QgsLayerTreeGroup = FakeLayerTreeGroup
    qgis_core.QgsCategorizedSymbolRenderer = FakeCategorizedSymbolRenderer
    qgis_core.QgsRendererCategory = FakeRendererCategory
    qgis_core.QgsFillSymbol = FakeFillSymbol
    qgis_core.QgsPalLayerSettings = FakePalLayerSettings
    qgis_core.QgsTextFormat = FakeTextFormat
    qgis_core.QgsTextBufferSettings = FakeTextBufferSettings
    qgis_core.QgsSingleSymbolRenderer = FakeSingleSymbolRenderer
    qgis_core.QgsRuleBasedLabeling = FakeQgsRuleBasedLabeling
    qgis_core.QgsMarkerSymbol = FakeMarkerSymbol
    qgis_core.QgsLineSymbol = FakeLineSymbol
    qgis_core.QgsUnitTypes = FakeQgsUnitTypes
    qgis_core.QgsFeature = FakeFeature
    qgis_core.QgsGeometry = FakeGeometry
    qgis_core.QgsPointXY = FakeQgsPointXY
    qgis_core.QgsVectorLayerSimpleLabeling = FakeQgsVectorLayerSimpleLabeling

    qgis_qtgui.QColor = FakeQColor
    qgis_qtgui.QFont = FakeQFont

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)


def build_vector_layer_factory(layer_defs, created_layers):
    def factory(source, name, provider):
        src = str(source)
        cfg = layer_defs.get(src, {})
        layer = FakeVectorLayer(
            src,
            name,
            provider,
            is_valid=cfg.get("is_valid", True),
            field_names=cfg.get("field_names", []),
            features=cfg.get("features", []),
        )
        created_layers.append(layer)
        return layer
    return factory


def import_module_with_fakes(
    monkeypatch,
    *,
    existing_paths=None,
    layer_defs=None,
    chart_json=None,
):
    clear_module()

    FakePath.existing_paths = set(existing_paths or [])

    project = FakeProject()
    created_layers = []
    layer_defs = layer_defs or {}
    vector_factory = build_vector_layer_factory(layer_defs, created_layers)

    install_fake_qgis(monkeypatch, project, vector_factory)

    if chart_json is not None:
        json_text = json.dumps(chart_json)

        def fake_open(path, mode="r", encoding=None):
            return io.StringIO(json_text)

        monkeypatch.setattr(builtins, "open", fake_open, raising=True)

    real_path = pathlib.Path
    pathlib.Path = FakePath
    try:
        module = importlib.import_module(MODULE_NAME)
    finally:
        pathlib.Path = real_path

    return module, project, created_layers


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def minimal_import(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )
    return module, project, created_layers


# -------------------------------------------------------------------
# Tests: helper functions
# -------------------------------------------------------------------

def test_ensure_group_reuses_existing_group(minimal_import):
    module, project, _ = minimal_import

    grp1 = module.ensure_group(project.root, "A")
    grp2 = module.ensure_group(project.root, "A")

    assert grp1 is grp2
    assert "A" in project.root.groups


def test_ensure_group_with_non_group_parent_uses_root(minimal_import):
    module, project, _ = minimal_import

    grp = module.ensure_group(object(), "RootChild")

    assert grp is project.root.groups["RootChild"]


# -------------------------------------------------------------------
# Tests: style functions
# -------------------------------------------------------------------

def test_style_pie_polygons_sets_categorized_renderer_and_disables_labels(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_pie_polygons(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_energy_legend_adds_palette_plus_legend_note(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "legend", "ogr")

    module.style_energy_legend_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE) + 1
    assert renderer.categories[-1].value == "legend_title"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    assert len(labeling.root_rule.children) == 7
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_row_chart_with_energy_field_uses_categorized_renderer(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer(
        "x",
        "row_chart",
        "ogr",
        field_names=["energy_type", "year_bin_slug", "label_anchor", "value_anchor"],
    )

    module.style_row_chart(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    rules = labeling.root_rule.children
    assert len(rules) == 4
    assert rules[0].filter_expression == '"label_anchor" = 1'
    assert rules[1].filter_expression == '"value_anchor" = 1'
    assert rules[2].filter_expression == '"year_bin_slug" = \'title\''
    assert rules[3].filter_expression == '"year_bin_slug" = \'unit\''
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_row_chart_without_energy_field_falls_back_to_single_symbol(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "row_chart", "ogr", field_names=["foo", "bar"])

    module.style_row_chart(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "200,200,200,200"
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_row_guides_sets_dash_and_mm_units(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "guides", "ogr")

    module.style_row_guides(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["line_style"] == "dash"
    assert renderer.symbol.width_unit == FakeQgsUnitTypes.RenderMillimeters
    assert renderer.symbol.symbolLayer(0).width_unit == FakeQgsUnitTypes.RenderMillimeters
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_row_frame_sets_outline_only(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "frame", "ogr")

    module.style_row_frame(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"
    assert renderer.symbol.props["outline_color"] == "160,160,160,255"
    assert renderer.symbol.props["outline_width"] == "0.35"
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_column_frame_calls_same_logic_as_row_frame(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "frame", "ogr")

    module.style_column_frame(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["outline_color"] == "160,160,160,255"


def test_style_column_bars_sets_categorized_renderer_and_disables_labels(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "bars", "ogr")

    module.style_column_bars(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_column_labels_builds_three_rules(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "labels", "ogr")

    module.style_column_labels(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    rules = labeling.root_rule.children
    assert len(rules) == 3
    assert rules[0].filter_expression == '"kind" = \'landkreis_label\''
    assert rules[1].filter_expression == '"kind" = \'value_label\''
    assert rules[2].filter_expression == '"kind" = \'title\''
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_kreis_number_points_layer_uses_simple_labeling(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "num_points", "ogr")

    module.style_kreis_number_points_layer(lyr)

    assert isinstance(lyr.renderer(), FakeSingleSymbolRenderer)
    assert isinstance(lyr.labeling(), FakeQgsVectorLayerSimpleLabeling)
    assert lyr.labeling().pal.fieldName == 'to_string("num")'
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_kreis_number_list_layer_uses_label_field(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "num_list", "ogr")

    module.style_kreis_number_list_layer(lyr)

    assert isinstance(lyr.renderer(), FakeSingleSymbolRenderer)
    assert isinstance(lyr.labeling(), FakeQgsVectorLayerSimpleLabeling)
    assert lyr.labeling().pal.fieldName == '"label"'
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


# -------------------------------------------------------------------
# Tests: year heading / HUD
# -------------------------------------------------------------------

def test_add_year_heading_creates_two_features_and_labels(minimal_import):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Bin")

    project.added_layers.clear()

    module.add_year_heading(parent, "1991_1992", "1991–1992", 12.34)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[-1]
    assert add_to_root is False
    assert layer.name() == "1991_1992_heading"
    assert layer in parent.layers

    labels = [feat.attrs["label"] for feat in layer._features]
    assert "1991–1992" in labels
    assert "Installed Power: 12.3 MW" in labels

    labeling = layer.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    assert len(labeling.root_rule.children) == 2


def test_add_year_heading_uses_na_when_period_missing(minimal_import):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Bin")

    project.added_layers.clear()

    module.add_year_heading(parent, "missing_slug", "Missing", None)

    layer, _ = project.added_layers[-1]
    labels = [feat.attrs["label"] for feat in layer._features]
    assert "Installed Power: n/a" in labels


def test_add_landkreis_hud_names_warns_when_centers_missing(minimal_import, capsys):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Parent")

    project.added_layers.clear()

    module.add_landkreis_hud_names(parent)

    captured = capsys.readouterr()
    assert "[WARN] CENTERS_PATH not found (HUD names skipped):" in captured.out


def test_add_landkreis_hud_names_warns_when_centers_invalid(monkeypatch, capsys):
    layer_defs = {
        CENTERS_PATH: {"is_valid": False},
    }
    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, CENTERS_PATH},
        layer_defs=layer_defs,
        chart_json=None,
    )
    parent = project.root.addGroup("Parent")
    project.added_layers.clear()

    module.add_landkreis_hud_names(parent)

    captured = capsys.readouterr()
    assert "[WARN] Could not load centers layer for HUD names." in captured.out


def test_add_landkreis_hud_names_warns_when_name_column_missing(monkeypatch, capsys):
    features = [
        FakeFeature(attrs={"num": 1, "slug": "a"}),
    ]
    layer_defs = {
        CENTERS_PATH: {
            "is_valid": True,
            "field_names": ["num", "slug"],
            "features": features,
        },
    }
    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, CENTERS_PATH},
        layer_defs=layer_defs,
        chart_json=None,
    )
    parent = project.root.addGroup("Parent")
    project.added_layers.clear()

    module.add_landkreis_hud_names(parent)

    captured = capsys.readouterr()
    assert "[WARN] Centers layer has no name column for HUD names." in captured.out


def test_add_landkreis_hud_names_creates_memory_layer_from_centers(monkeypatch):
    features = [
        FakeFeature(attrs={"num": 2, "landkreis_name": "B"}),
        FakeFeature(attrs={"num": 1, "landkreis_name": "A"}),
        FakeFeature(attrs={"num": 3, "landkreis_name": "C"}),
    ]
    layer_defs = {
        CENTERS_PATH: {
            "is_valid": True,
            "field_names": ["num", "landkreis_name"],
            "features": features,
        },
    }
    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, CENTERS_PATH},
        layer_defs=layer_defs,
        chart_json=None,
    )
    parent = project.root.addGroup("Parent")
    project.added_layers.clear()

    module.add_landkreis_hud_names(parent)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[-1]
    assert add_to_root is False
    assert layer.name() == "thueringen_landkreis_hud_names"
    assert layer in parent.layers

    labels = [feat.attrs["label"] for feat in layer._features]
    assert labels[0] == "01  A"
    assert labels[1] == "02  B"
    assert labels[2] == "03  C"


# -------------------------------------------------------------------
# Tests: main()
# -------------------------------------------------------------------

def test_main_returns_early_when_root_dir_missing(monkeypatch, capsys):
    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths=set(),
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[ERROR] ROOT_DIR does not exist:" in captured.out
    assert project.added_layers == []


def test_main_warns_when_legend_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] ENERGY_LEGEND_PATH not found:" in captured.out


def test_main_warns_when_number_points_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Number points not found:" in captured.out



def test_main_happy_path_loads_all_major_layers(monkeypatch):
    pie_pre = ROOT_DIR + r"\pre_1990\thueringen_landkreis_pie_pre_1990.geojson"
    pie_1991 = ROOT_DIR + r"\1991_1992\thueringen_landkreis_pie_1991_1992.geojson"

    existing_paths = {
        ROOT_DIR,
        LEGEND_PATH,
        NUMBER_POINTS_PATH,
        CHART_PATH,
        GUIDES_PATH,
        FRAME_PATH,
        COL_BARS_PATH,
        COL_LABELS_PATH,
        COL_FRAME_PATH,
        pie_pre,
        pie_1991,
    }

    layer_defs = {
        LEGEND_PATH: {"field_names": ["energy_type", "legend_label"]},
        NUMBER_POINTS_PATH: {"field_names": ["num"]},
        CHART_PATH: {"field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]},
        GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        FRAME_PATH: {"field_names": ["kind"]},
        COL_BARS_PATH: {"field_names": ["year_bin_slug", "energy_type"]},
        COL_LABELS_PATH: {"field_names": ["year_bin_slug", "kind", "landkreis_number", "text", "year_bin_label", "total_kw"]},
        COL_FRAME_PATH: {"field_names": ["kind"]},
        pie_pre: {"field_names": ["energy_type"]},
        pie_1991: {"field_names": ["energy_type"]},
    }

    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": "1", "total_kw": 1000}},
            {"properties": {"year_bin_slug": "1991_1992", "value_anchor": "1", "total_kw": 4000}},
            {"properties": {"year_bin_slug": "title", "value_anchor": "1", "total_kw": 9999}},
        ]
    }

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        layer_defs=layer_defs,
        chart_json=chart,
    )

    parent_group = project.root.findGroup("thueringen_statewise_landkreis_pies (yearly)")
    assert parent_group is not None

    parent_layer_names = [layer.name() for layer in parent_group.layers]
    assert "energy_legend" in parent_layer_names
    assert "thueringen_landkreis_numbers" in parent_layer_names

    assert "≤1990" in parent_group.groups
    assert "1991–1992" in parent_group.groups

    first_bin = parent_group.findGroup("≤1990")
    second_bin = parent_group.findGroup("1991–1992")

    first_names = [layer.name() for layer in first_bin.layers]
    second_names = [layer.name() for layer in second_bin.layers]

    assert "thueringen_landkreis_pie_pre_1990" in first_names
    assert "thueringen_rowChart_pre_1990" in first_names
    assert "thueringen_rowGuides_pre_1990" in first_names
    assert "thueringen_rowFrame_pre_1990" in first_names
    assert "thueringen_colBars_pre_1990" in first_names
    assert "thueringen_colLabels_pre_1990" in first_names
    assert "thueringen_colFrame_pre_1990" in first_names
    assert "pre_1990_heading" in first_names

    assert "thueringen_landkreis_pie_1991_1992" in second_names
    assert "thueringen_rowChart_1991_1992" in second_names
    assert "thueringen_rowGuides_1991_1992" in second_names
    assert "thueringen_rowFrame_1991_1992" in second_names
    assert "thueringen_colBars_1991_1992" in second_names
    assert "thueringen_colLabels_1991_1992" in second_names
    assert "thueringen_colFrame_1991_1992" in second_names
    assert "1991_1992_heading" in second_names

    row_pre = next(layer for layer in first_bin.layers if layer.name() == "thueringen_rowChart_pre_1990")
    row_1991 = next(layer for layer in second_bin.layers if layer.name() == "thueringen_rowChart_1991_1992")

    assert row_pre.subsetString() == "(\"year_bin_slug\" IN ('pre_1990') OR \"year_bin_slug\" IN ('title','unit'))"
    assert row_1991.subsetString() == "(\"year_bin_slug\" IN ('pre_1990','1991_1992') OR \"year_bin_slug\" IN ('title','unit'))"

    guides_pre = next(layer for layer in first_bin.layers if layer.name() == "thueringen_rowGuides_pre_1990")
    guides_1991 = next(layer for layer in second_bin.layers if layer.name() == "thueringen_rowGuides_1991_1992")

    assert guides_pre.subsetString() == "\"year_bin_slug\" IN ('pre_1990')"
    assert guides_1991.subsetString() == "\"year_bin_slug\" IN ('pre_1990','1991_1992')"

    col_bars_pre = next(layer for layer in first_bin.layers if layer.name() == "thueringen_colBars_pre_1990")
    col_labels_pre = next(layer for layer in first_bin.layers if layer.name() == "thueringen_colLabels_pre_1990")

    assert col_bars_pre.subsetString() == "\"year_bin_slug\" = 'pre_1990'"
    assert col_labels_pre.subsetString() == "(\"year_bin_slug\" = 'pre_1990' OR \"year_bin_slug\" = 'landkreis_title')"


def test_main_warns_when_pie_missing_for_bin(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Pie polygons missing for pre_1990:" in captured.out


def test_main_warns_when_column_paths_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Column bars not found:" in captured.out
    assert "[WARN] Column labels not found:" in captured.out


def test_main_logs_period_mw_loaded_when_chart_exists(monkeypatch, capsys):
    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": "1", "total_kw": 1000}},
            {"properties": {"year_bin_slug": "1991_1992", "value_anchor": "1", "total_kw": 5000}},
        ]
    }

    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, CHART_PATH},
        layer_defs={
            CHART_PATH: {"field_names": ["year_bin_slug", "label_anchor", "value_anchor", "total_kw", "energy_type"]},
        },
        chart_json=chart,
    )

    captured = capsys.readouterr()
    assert "[INFO] Loaded PERIOD Installed Power (MW) for 2 bins" in captured.out


def test_main_handles_chart_read_failure(monkeypatch, capsys):
    def fake_open_raises(path, mode="r", encoding=None):
        raise ValueError("boom")

    clear_module()
    FakePath.existing_paths = {ROOT_DIR, CHART_PATH}

    project = FakeProject()
    created_layers = []
    vector_factory = build_vector_layer_factory({}, created_layers)
    install_fake_qgis(monkeypatch, project, vector_factory)
    monkeypatch.setattr(builtins, "open", fake_open_raises, raising=True)

    real_path = pathlib.Path
    pathlib.Path = FakePath
    try:
        importlib.import_module(MODULE_NAME)
    finally:
        pathlib.Path = real_path

    captured = capsys.readouterr()
    assert "[WARN] Could not compute per_bin_mw:" in captured.out

def test_style_energy_legend_adds_palette_plus_title(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "legend", "ogr")

    module.style_energy_legend_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE) + 1
    assert renderer.categories[-1].value == "legend_title"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    assert len(labeling.root_rule.children) == 7

    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True

def test_main_warns_when_legend_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] ENERGY_LEGEND_PATH not found:" in captured.out