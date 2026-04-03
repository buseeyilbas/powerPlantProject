# Filename: unit_tests/test_zQGIS_1_style_thueringen_statePieChart_yearly.py

import builtins
import importlib
import io
import json
import pathlib
import sys
import types
from collections import OrderedDict

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.1_style_thueringen_statePieChart_yearly"


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
    OverPoint = "OverPoint"

    def __init__(self):
        self.enabled = False
        self.isExpression = False
        self.fieldName = None
        self.format = None
        self.placement = None
        self.xOffset = 0.0
        self.yOffset = 0.0
        self._ddp = FakeDataDefinedProperties()

    def setFormat(self, fmt):
        self.format = fmt

    def dataDefinedProperties(self):
        return self._ddp

    def setDataDefinedProperties(self, ddp):
        self._ddp = ddp


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
# Fake geometry / feature classes
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
    def fromPolygonXY(rings):
        return FakeGeometry("polygon", rings)

    @staticmethod
    def fromPointXY(point):
        return FakeGeometry("point", point)


class FakeField:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeFeature:
    def __init__(self, fields=None):
        self._fields = fields or []
        self.geometry = None
        self.attrs = {}

    def setGeometry(self, geometry):
        self.geometry = geometry

    def __setitem__(self, key, value):
        self.attrs[key] = value

    def __getitem__(self, key):
        return self.attrs[key]


# -------------------------------------------------------------------
# Fake provider / layer / project / groups
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
        feature_count=0,
    ):
        self._source = source
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._field_names = field_names or []
        self._renderer = None
        self._labels_enabled = None
        self._labeling = None
        self._subset_string = None
        self._repaint_called = False
        self._features = []
        self._feature_count = feature_count
        self._provider_obj = FakeProvider(self)

    def name(self):
        return self._name

    def source(self):
        return self._source

    def isValid(self):
        return self._is_valid

    def setRenderer(self, renderer):
        self._renderer = renderer

    def setLabelsEnabled(self, enabled):
        self._labels_enabled = enabled

    def setLabeling(self, labeling):
        self._labeling = labeling

    def triggerRepaint(self):
        self._repaint_called = True

    def setSubsetString(self, subset):
        self._subset_string = subset

    def subsetString(self):
        return self._subset_string

    def renderer(self):
        return self._renderer

    def labeling(self):
        return self._labeling

    def labelsEnabled(self):
        return self._labels_enabled

    def repaintCalled(self):
        return self._repaint_called

    def fields(self):
        return [FakeField(name) for name in self._field_names]

    def dataProvider(self):
        return self._provider_obj

    def updateExtents(self):
        return None

    def featureCount(self):
        if self._features:
            return len(self._features)
        return self._feature_count


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


class FakeProject:
    def __init__(self):
        self.root = FakeLayerTreeGroup("root")
        self.added_layers = []

    def layerTreeRoot(self):
        return self.root

    def addMapLayer(self, layer, add_to_root=True):
        self.added_layers.append((layer, add_to_root))


# -------------------------------------------------------------------
# Fake filesystem path
# -------------------------------------------------------------------

class FakePath:
    existing_paths = set()
    dir_children = {}
    file_contents = {}

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

    @property
    def name(self):
        normalized = self.path.replace("/", "\\")
        return normalized.split("\\")[-1]

    def exists(self):
        return self.path in self.existing_paths

    def is_dir(self):
        return self.path in self.dir_children

    def iterdir(self):
        for child in self.dir_children.get(self.path, []):
            yield FakePath(child)

    def read_text(self, encoding="utf-8"):
        return self.file_contents[self.path]


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

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
    qgis_core.QgsVectorLayerSimpleLabeling = FakeQgsVectorLayerSimpleLabeling
    qgis_core.QgsPalLayerSettings = FakePalLayerSettings
    qgis_core.QgsTextFormat = FakeTextFormat
    qgis_core.QgsTextBufferSettings = FakeTextBufferSettings
    qgis_core.QgsProperty = FakeQgsProperty
    qgis_core.QgsMarkerSymbol = FakeMarkerSymbol
    qgis_core.QgsLineSymbol = FakeLineSymbol
    qgis_core.QgsSingleSymbolRenderer = FakeSingleSymbolRenderer
    qgis_core.QgsRuleBasedLabeling = FakeQgsRuleBasedLabeling
    qgis_core.QgsUnitTypes = FakeQgsUnitTypes
    qgis_core.QgsFeature = FakeFeature
    qgis_core.QgsGeometry = FakeGeometry
    qgis_core.QgsPointXY = FakeQgsPointXY

    qgis_qtgui.QColor = FakeQColor
    qgis_qtgui.QFont = FakeQFont

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)


def build_vector_layer_factory(layer_defs, created_layers):
    def factory(source, name, provider):
        source_str = str(source)
        cfg = layer_defs.get(source_str, {})
        layer = FakeVectorLayer(
            source=source_str,
            name=name,
            provider=provider,
            is_valid=cfg.get("is_valid", True),
            field_names=cfg.get("field_names", []),
            feature_count=cfg.get("feature_count", 0),
        )
        created_layers.append(layer)
        return layer
    return factory


def import_module_with_fakes(
    monkeypatch,
    *,
    existing_paths=None,
    dir_children=None,
    file_contents=None,
    layer_defs=None,
    yearly_chart_json_for_open=None,
):
    clear_module()

    FakePath.existing_paths = set(existing_paths or [])
    FakePath.dir_children = dict(dir_children or {})
    FakePath.file_contents = dict(file_contents or {})

    project = FakeProject()
    created_layers = []
    layer_defs = layer_defs or {}
    vector_factory = build_vector_layer_factory(layer_defs, created_layers)

    install_fake_qgis(monkeypatch, project, vector_factory)

    if yearly_chart_json_for_open is not None:
        json_text = json.dumps(yearly_chart_json_for_open)

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
# Common path constants
# -------------------------------------------------------------------

ROOT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\thueringen_state_pies_yearly"
YEARLY_CHART_PATH = ROOT_DIR + r"\thueringen_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR + r"\thueringen_yearly_totals_chart_guides.geojson"
LEGEND_PATH = ROOT_DIR + r"\thueringen_energy_legend_points.geojson"


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def minimal_import(monkeypatch):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths=set(),
        dir_children={},
        file_contents={},
        layer_defs={},
        yearly_chart_json_for_open=None,
    )
    return module, project, created_layers


# -------------------------------------------------------------------
# Tests: import-time PER_BIN_MW computation
# -------------------------------------------------------------------

def test_import_computes_period_mw(monkeypatch):
    chart = {
        "features": [
            {
                "properties": {
                    "year_bin_slug": "pre_1990",
                    "value_anchor": 1,
                    "total_kw": 5000,
                }
            },
            {
                "properties": {
                    "year_bin_slug": "1991_1992",
                    "value_anchor": "1",
                    "total_kw": 17000,
                }
            },
            {
                "properties": {
                    "year_bin_slug": "unit",
                    "value_anchor": 1,
                    "total_kw": 99999,
                }
            },
            {
                "properties": {
                    "year_bin_slug": "title",
                    "value_anchor": 1,
                    "total_kw": 99999,
                }
            },
        ]
    }

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={YEARLY_CHART_PATH},
        yearly_chart_json_for_open=chart,
    )

    assert module.PER_BIN_MW["pre_1990"] == pytest.approx(5.0)
    assert module.PER_BIN_MW["1991_1992"] == pytest.approx(12.0)


def test_import_skips_invalid_rows_in_period_mw(monkeypatch):
    chart = {
        "features": [
            {
                "properties": {
                    "year_bin_slug": "pre_1990",
                    "value_anchor": 0,
                    "total_kw": 5000,
                }
            },
            {
                "properties": {
                    "year_bin_slug": "1991_1992",
                    "value_anchor": 1,
                    "total_kw": "bad",
                }
            },
        ]
    }

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={YEARLY_CHART_PATH},
        yearly_chart_json_for_open=chart,
    )

    assert module.PER_BIN_MW == {}


# -------------------------------------------------------------------
# Tests: helper functions
# -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, True),
        (1.0, True),
        ("1", True),
        ("1.0", True),
        (True, True),
        ("True", True),
        ("true", True),
        (0, False),
        ("0", False),
        (None, False),
        ("abc", False),
    ],
)
def test_is_anchor_one(minimal_import, value, expected):
    module, _, _ = minimal_import
    assert module.is_anchor_one(value) is expected


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


def test_pretty_year_label_reads_meta_if_present(minimal_import):
    module, _, _ = minimal_import

    slug_dir = ROOT_DIR + r"\1991_1992"
    meta_path = slug_dir + r"\thueringen_state_pie_style_meta_1991_1992.json"
    FakePath.existing_paths.add(meta_path)
    FakePath.file_contents[meta_path] = json.dumps({"year_bin": "Custom Label"})

    label = module.pretty_year_label(FakePath(slug_dir))
    assert label == "Custom Label"


def test_pretty_year_label_falls_back_to_range(minimal_import):
    module, _, _ = minimal_import
    assert module.pretty_year_label(FakePath(ROOT_DIR + r"\1993_1994")) == "1993–1994"


def test_pretty_year_label_handles_pre_1990(minimal_import):
    module, _, _ = minimal_import
    assert module.pretty_year_label(FakePath(ROOT_DIR + r"\pre_1990")) == "≤1990 — Pre-EEG"


def test_pretty_year_label_returns_slug_for_unknown(minimal_import):
    module, _, _ = minimal_import
    assert module.pretty_year_label(FakePath(ROOT_DIR + r"\weird_slug")) == "weird_slug"


def test_bin_sort_key_orders_pre_1990_first(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key(FakePath(ROOT_DIR + r"\pre_1990")) == (-1, -1)


def test_bin_sort_key_orders_numeric_ranges(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key(FakePath(ROOT_DIR + r"\2001_2002")) == (2001, 2002)


def test_bin_sort_key_puts_unknown_last(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key(FakePath(ROOT_DIR + r"\abc")) == (9999, "abc")


def test_make_rect_feature_builds_polygon_and_kind(minimal_import):
    module, _, _ = minimal_import
    layer = FakeVectorLayer("memory", "rects", "memory", field_names=["kind"])

    feature = module._make_rect_feature(layer, 1, 2, 3, 4, "row")

    assert feature["kind"] == "row"
    assert feature.geometry.kind == "polygon"
    ring = feature.geometry.payload[0]
    assert [(p.x, p.y) for p in ring] == [
        (1, 2),
        (3, 2),
        (3, 4),
        (1, 4),
        (1, 2),
    ]


# -------------------------------------------------------------------
# Tests: style functions
# -------------------------------------------------------------------

def test_style_state_pie_layer_sets_categorized_renderer_and_disables_labels(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_state_pie_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_center_layer_without_numbers_disables_labels(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "centers", "ogr")

    module.style_center_layer(lyr, label_numbers=False)

    assert isinstance(lyr.renderer(), FakeSingleSymbolRenderer)
    assert lyr.labelsEnabled() is False
    assert lyr.labeling() is None
    assert lyr.repaintCalled() is True


def test_style_center_layer_with_numbers_enables_simple_labeling(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "centers", "ogr")

    module.style_center_layer(lyr, label_numbers=True)

    assert isinstance(lyr.renderer(), FakeSingleSymbolRenderer)
    assert lyr.labelsEnabled() is True
    assert isinstance(lyr.labeling(), FakeQgsVectorLayerSimpleLabeling)
    assert lyr.labeling().pal.fieldName == "state_number"
    assert lyr.repaintCalled() is True


def test_style_energy_legend_layer_adds_palette_plus_legend_note(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "legend", "ogr")

    module.style_energy_legend_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE) + 1
    assert renderer.categories[-1].value == "legend_note"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    assert len(labeling.root_rule.children) == 7
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_yearly_chart_layer_with_energy_field_uses_categorized_renderer(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer(
        "x",
        "row_chart",
        "ogr",
        field_names=["energy_type", "year_bin_slug", "label_anchor", "value_anchor"],
    )

    module.style_yearly_chart_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    rules = labeling.root_rule.children

    # Script currently creates 5 rules because "unit" is added twice when year_bin_slug exists
    assert len(rules) == 5
    assert rules[0].filter_expression == '"label_anchor" = 1'
    assert rules[1].filter_expression == '"value_anchor" = 1'
    assert rules[2].filter_expression == '"year_bin_slug" = \'title\''
    assert rules[3].filter_expression == '"year_bin_slug" = \'unit\''
    assert rules[4].filter_expression == '"year_bin_slug" = \'unit\''
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_yearly_chart_layer_without_energy_field_falls_back_to_single_symbol(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "row_chart", "ogr", field_names=["foo", "bar"])

    module.style_yearly_chart_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "200,200,200,200"
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_yearly_guides_layer_sets_dash_and_mm_units(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "guides", "ogr")

    module.style_yearly_guides_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["line_style"] == "dash"
    assert renderer.symbol.width_unit == FakeQgsUnitTypes.RenderMillimeters
    assert renderer.symbol.symbolLayer(0).width_unit == FakeQgsUnitTypes.RenderMillimeters
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


# -------------------------------------------------------------------
# Tests: frame / heading builders
# -------------------------------------------------------------------

def test_add_row_chart_frame_creates_memory_layer_with_one_rectangle(minimal_import):
    module, project, created_layers = minimal_import
    parent = project.root.addGroup("Parent")

    module.add_row_chart_frame(parent)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[0]
    assert add_to_root is False
    assert layer.name() == "thueringen_chart_frame"
    assert layer.featureCount() == 1
    assert layer in parent.layers

    renderer = layer.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"
    assert renderer.symbol.props["outline_width"] == str(module.FRAME_WIDTH_MM)


def test_add_row_chart_frame_returns_early_when_disabled(minimal_import):
    module, project, created_layers = minimal_import
    parent = project.root.addGroup("Parent")

    original = module.DRAW_CHART_FRAMES
    module.DRAW_CHART_FRAMES = False
    try:
        module.add_row_chart_frame(parent)
    finally:
        module.DRAW_CHART_FRAMES = original

    assert project.added_layers == []
    assert parent.layers == []


def test_add_year_heading_creates_two_features_and_labels(minimal_import):
    module, project, created_layers = minimal_import
    parent = project.root.addGroup("Bin")
    module.PER_BIN_MW["1991_1992"] = 12.34

    module.add_year_heading(parent, "1991_1992", "1991–1992")

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[0]
    assert add_to_root is False
    assert layer.name() == "1991_1992_heading"
    assert layer.featureCount() == 2
    assert layer in parent.layers

    labels = [feat.attrs["label"] for feat in layer._features]
    assert "1991–1992" in labels
    assert "Installed Power: 12.3 MW" in labels

    labeling = layer.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    assert len(labeling.root_rule.children) == 2


def test_add_year_heading_uses_na_when_period_missing(minimal_import):
    module, project, created_layers = minimal_import
    parent = project.root.addGroup("Bin")

    module.add_year_heading(parent, "missing_slug", "Missing")

    layer, _ = project.added_layers[0]
    labels = [feat.attrs["label"] for feat in layer._features]
    assert "Installed Power: n/a" in labels


# -------------------------------------------------------------------
# Tests: main()
# -------------------------------------------------------------------

def test_main_returns_early_when_root_dir_missing(monkeypatch, capsys):
    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths=set(),
        dir_children={},
        layer_defs={},
    )

    captured = capsys.readouterr()
    assert "[ERROR] ROOT_DIR does not exist" in captured.out
    assert project.added_layers == []


def test_main_builds_groups_and_loads_bin_layers(monkeypatch):
    existing_paths = {
        ROOT_DIR,
        YEARLY_CHART_PATH,
        GUIDES_PATH,
        LEGEND_PATH,
        ROOT_DIR + r"\pre_1990",
        ROOT_DIR + r"\1991_1992",
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson",
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson",
        ROOT_DIR + r"\1991_1992\thueringen_state_pie_1991_1992.geojson",
        ROOT_DIR + r"\1991_1992\thueringen_state_pies_1991_1992.geojson",
    }

    dir_children = {
        ROOT_DIR: [
            ROOT_DIR + r"\1991_1992",
            ROOT_DIR + r"\pre_1990",
        ],
        ROOT_DIR + r"\1991_1992": [],
        ROOT_DIR + r"\pre_1990": [],
    }

    layer_defs = {
        LEGEND_PATH: {"field_names": ["energy_type", "legend_label"]},
        YEARLY_CHART_PATH: {
            "field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]
        },
        GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson": {"field_names": ["energy_type"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson": {"field_names": ["state_number"]},
        ROOT_DIR + r"\1991_1992\thueringen_state_pie_1991_1992.geojson": {"field_names": ["energy_type"]},
        ROOT_DIR + r"\1991_1992\thueringen_state_pies_1991_1992.geojson": {"field_names": ["state_number"]},
    }

    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": 1, "total_kw": 1000}},
            {"properties": {"year_bin_slug": "1991_1992", "value_anchor": 1, "total_kw": 4000}},
        ]
    }

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        dir_children=dir_children,
        layer_defs=layer_defs,
        yearly_chart_json_for_open=chart,
    )

    parent_group = project.root.findGroup("thueringen_state_pies (yearly)")
    assert parent_group is not None

    parent_layer_names = [layer.name() for layer in parent_group.layers]
    assert "thueringen_chart_frame" in parent_layer_names
    assert "energy_legend" in parent_layer_names

    assert "≤1990 — Pre-EEG" in parent_group.groups
    assert "1991–1992" in parent_group.groups

    first_bin = parent_group.findGroup("≤1990 — Pre-EEG")
    second_bin = parent_group.findGroup("1991–1992")

    first_names = [layer.name() for layer in first_bin.layers]
    second_names = [layer.name() for layer in second_bin.layers]

    assert "thueringen_state_pie_pre_1990" in first_names
    assert "thueringen_state_pies_pre_1990" in first_names
    assert "yearly_rowChart_total_power_pre_1990" in first_names
    assert "yearly_rowChart_guides_pre_1990" in first_names
    assert "pre_1990_heading" in first_names

    assert "thueringen_state_pie_1991_1992" in second_names
    assert "thueringen_state_pies_1991_1992" in second_names
    assert "yearly_rowChart_total_power_1991_1992" in second_names
    assert "yearly_rowChart_guides_1991_1992" in second_names
    assert "1991_1992_heading" in second_names

    row_pre = next(layer for layer in first_bin.layers if layer.name() == "yearly_rowChart_total_power_pre_1990")
    row_1991 = next(layer for layer in second_bin.layers if layer.name() == "yearly_rowChart_total_power_1991_1992")

    assert row_pre.subsetString() == "(\"year_bin_slug\" IN ('pre_1990') OR \"year_bin_slug\" IN ('title','unit'))"
    assert row_1991.subsetString() == "(\"year_bin_slug\" IN ('pre_1990','1991_1992') OR \"year_bin_slug\" IN ('title','unit'))"

    guides_pre = next(layer for layer in first_bin.layers if layer.name() == "yearly_rowChart_guides_pre_1990")
    guides_1991 = next(layer for layer in second_bin.layers if layer.name() == "yearly_rowChart_guides_1991_1992")

    assert guides_pre.subsetString() == "\"year_bin_slug\" IN ('pre_1990')"
    assert guides_1991.subsetString() == "\"year_bin_slug\" IN ('pre_1990','1991_1992')"


def test_main_prints_warning_when_energy_legend_missing(monkeypatch, capsys):
    existing_paths = {
        ROOT_DIR,
        YEARLY_CHART_PATH,
        GUIDES_PATH,
        ROOT_DIR + r"\pre_1990",
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson",
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson",
    }

    dir_children = {
        ROOT_DIR: [ROOT_DIR + r"\pre_1990"],
        ROOT_DIR + r"\pre_1990": [],
    }

    layer_defs = {
        YEARLY_CHART_PATH: {"field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]},
        GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson": {"field_names": ["energy_type"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson": {"field_names": ["state_number"]},
    }

    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": 1, "total_kw": 1000}},
        ]
    }

    import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        dir_children=dir_children,
        layer_defs=layer_defs,
        yearly_chart_json_for_open=chart,
    )

    captured = capsys.readouterr()
    assert "[WARN] Energy legend file not found:" in captured.out


def test_main_prints_warning_when_yearly_chart_missing(monkeypatch, capsys):
    existing_paths = {
        ROOT_DIR,
        ROOT_DIR + r"\pre_1990",
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson",
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson",
    }

    dir_children = {
        ROOT_DIR: [ROOT_DIR + r"\pre_1990"],
        ROOT_DIR + r"\pre_1990": [],
    }

    layer_defs = {
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson": {"field_names": ["energy_type"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pies_pre_1990.geojson": {"field_names": ["state_number"]},
    }

    import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        dir_children=dir_children,
        layer_defs=layer_defs,
        yearly_chart_json_for_open=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] YEARLY_CHART_PATH not found:" in captured.out


def test_main_skips_center_layer_when_center_file_missing(monkeypatch):
    existing_paths = {
        ROOT_DIR,
        YEARLY_CHART_PATH,
        GUIDES_PATH,
        LEGEND_PATH,
        ROOT_DIR + r"\pre_1990",
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson",
    }

    dir_children = {
        ROOT_DIR: [ROOT_DIR + r"\pre_1990"],
        ROOT_DIR + r"\pre_1990": [],
    }

    layer_defs = {
        LEGEND_PATH: {"field_names": ["energy_type", "legend_label"]},
        YEARLY_CHART_PATH: {
            "field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]
        },
        GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        ROOT_DIR + r"\pre_1990\thueringen_state_pie_pre_1990.geojson": {"field_names": ["energy_type"]},
    }

    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": 1, "total_kw": 1000}},
        ]
    }

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        dir_children=dir_children,
        layer_defs=layer_defs,
        yearly_chart_json_for_open=chart,
    )

    parent_group = project.root.findGroup("thueringen_state_pies (yearly)")
    first_bin = parent_group.findGroup("≤1990 — Pre-EEG")
    first_names = [layer.name() for layer in first_bin.layers]

    assert "thueringen_state_pie_pre_1990" in first_names
    assert "thueringen_state_pies_pre_1990" not in first_names