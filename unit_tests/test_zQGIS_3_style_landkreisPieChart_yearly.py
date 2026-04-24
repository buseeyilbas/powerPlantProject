# Filename: unit_tests/test_zQGIS_3_style_landkreisPieChart_yearly.py

import builtins
import importlib
import io
import json
import pathlib
import sys
import types
from collections import OrderedDict

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.3_style_landkreisPieChart_yearly"




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
        self.source_symbol = None

    def setSourceSymbol(self, symbol):
        self.source_symbol = symbol


class FakeSingleSymbolRenderer:
    def __init__(self, symbol):
        self.symbol = symbol


class FakeQgsUnitTypes:
    RenderMillimeters = "RenderMillimeters"


# -------------------------------------------------------------------
# Fake geometry / feature / field classes
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

    def __getitem__(self, key):
        return self.attrs.get(key)

    def __setitem__(self, key, value):
        self.attrs[key] = value


# -------------------------------------------------------------------
# Fake provider / layer / tree / project
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

    def exists(self):
        return self.path in self.existing_paths


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

ROOT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies_yearly"
YEARLY_CHART_PATH = ROOT_DIR + r"\de_yearly_totals_chart.geojson"
GUIDES_PATH = ROOT_DIR + r"\de_yearly_totals_chart_guides.geojson"
LEGEND_PATH = ROOT_DIR + r"\de_energy_legend_points.geojson"
STATE_COL_BARS_PATH = ROOT_DIR + r"\de_state_totals_columnChart_bars.geojson"
STATE_COL_LABELS_PATH = ROOT_DIR + r"\de_state_totals_columnChart_labels.geojson"

ENERGY_LEGEND_PATH = ROOT_DIR + r"\de_energy_legend_points.geojson"
PIE_SIZE_LEGEND_CIRCLES_PATH = ROOT_DIR + r"\de_pie_size_legend_circles.geojson"
PIE_SIZE_LEGEND_LABELS_PATH = ROOT_DIR + r"\de_pie_size_legend_labels.geojson"
LEGEND_FRAMES_PATH = ROOT_DIR + r"\de_legend_frames.geojson"

LEGEND_PATH = ENERGY_LEGEND_PATH


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
    qgis_core.QgsSingleSymbolRenderer = FakeSingleSymbolRenderer
    qgis_core.QgsRuleBasedLabeling = FakeQgsRuleBasedLabeling
    qgis_core.QgsPalLayerSettings = FakePalLayerSettings
    qgis_core.QgsTextFormat = FakeTextFormat
    qgis_core.QgsTextBufferSettings = FakeTextBufferSettings
    qgis_core.QgsMarkerSymbol = FakeMarkerSymbol
    qgis_core.QgsLineSymbol = FakeLineSymbol
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
        src = str(source)
        cfg = layer_defs.get(src, {})
        layer = FakeVectorLayer(
            src,
            name,
            provider,
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


def test_bin_sort_key_slug_orders_pre_1990_first(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key_slug("pre_1990") == (-1, -1)


def test_bin_sort_key_slug_orders_numeric_ranges(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key_slug("2001_2002") == (2001, 2002)


def test_bin_sort_key_slug_puts_unknown_last(minimal_import):
    module, _, _ = minimal_import
    assert module.bin_sort_key_slug("abc") == (9999, "abc")


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


def test_style_energy_legend_layer_adds_palette_plus_legend_title(minimal_import):
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

    rules = labeling.root_rule.children
    assert len(rules) == 7
    assert rules[-1].filter_expression == "\"energy_type\" = 'legend_title'"
    assert rules[-1].pal.format.font.weight == FakeQFont.Bold

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
    assert len(rules) == 4
    assert rules[0].filter_expression == '"label_anchor" = 1'
    assert rules[1].filter_expression == '"value_anchor" = 1'
    assert rules[2].filter_expression == '"year_bin_slug" = \'title\''
    assert rules[3].filter_expression == '"year_bin_slug" = \'unit\''
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


def test_style_state_column_bars_layer_sets_categories_and_default_symbol(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "bars", "ogr")

    module.style_state_column_bars_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert renderer.source_symbol.props["color"] == "0,0,0,0"
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_state_column_labels_layer_builds_three_rules(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "labels", "ogr")

    module.style_state_column_labels_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)
    rules = labeling.root_rule.children
    assert len(rules) == 3
    assert rules[0].filter_expression == "\"kind\" = 'state_label'"
    assert rules[1].filter_expression == "\"kind\" = 'value_label'"
    assert rules[2].filter_expression == "\"kind\" = 'title'"
    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


# -------------------------------------------------------------------
# Tests: frame / heading builders
# -------------------------------------------------------------------

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


def test_add_chart_frames_creates_memory_layer_with_two_rectangles(minimal_import):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Parent")

    project.added_layers.clear()

    module.add_chart_frames(parent)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[-1]
    assert add_to_root is False
    assert layer.name() == "chart_frames"
    assert layer.featureCount() == 2
    assert layer in parent.layers

    renderer = layer.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"
    assert renderer.symbol.props["outline_width"] == str(module.FRAME_WIDTH_MM)


def test_add_chart_frames_returns_early_when_disabled(minimal_import):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Parent")

    project.added_layers.clear()
    parent.layers.clear()

    original = module.DRAW_CHART_FRAMES
    module.DRAW_CHART_FRAMES = False
    try:
        module.add_chart_frames(parent)
    finally:
        module.DRAW_CHART_FRAMES = original

    assert project.added_layers == []
    assert parent.layers == []


def test_add_year_heading_creates_two_features_and_labels(minimal_import):
    module, project, _ = minimal_import
    parent = project.root.addGroup("Bin")

    project.added_layers.clear()

    module.add_year_heading(parent, "1991_1992", "1991–1992", 1.2345)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[-1]
    assert add_to_root is False
    assert layer.name() == "1991_1992_heading"
    assert layer in parent.layers

    labels = [feat.attrs["label"] for feat in layer._features]
    assert "1991–1992" in labels
    assert "Installed Power: 1.23 GW" in labels

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


def test_main_prints_warning_when_legend_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Legend file not found:" in captured.out


def test_main_replaces_old_group_before_creating_new_one(monkeypatch):
    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    assert "nationwide_landkreis_pies (yearly)" in project.root.groups
    old_group = project.root.groups["nationwide_landkreis_pies (yearly)"]

    module.main()

    assert "nationwide_landkreis_pies (yearly)" in project.root.groups
    assert project.root.groups["nationwide_landkreis_pies (yearly)"] is not old_group


def test_main_happy_path_loads_pies_charts_guides_column_chart_and_heading(monkeypatch):
    pie_pre = ROOT_DIR + r"\pre_1990\de_landkreis_pie_pre_1990.geojson"
    pie_1991 = ROOT_DIR + r"\1991_1992\de_landkreis_pie_1991_1992.geojson"

    existing_paths = {
        ROOT_DIR,
        LEGEND_PATH,
        YEARLY_CHART_PATH,
        GUIDES_PATH,
        STATE_COL_BARS_PATH,
        STATE_COL_LABELS_PATH,
        PIE_SIZE_LEGEND_CIRCLES_PATH,
        PIE_SIZE_LEGEND_LABELS_PATH,
        LEGEND_FRAMES_PATH,
        pie_pre,
        pie_1991,
    }

    layer_defs = {
        LEGEND_PATH: {"field_names": ["energy_type", "legend_label"]},
        YEARLY_CHART_PATH: {
            "field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]
        },
        GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        STATE_COL_BARS_PATH: {"field_names": ["year_bin_slug", "energy_type"], "feature_count": 3},
        STATE_COL_LABELS_PATH: {"field_names": ["year_bin_slug", "kind", "state_number", "total_kw", "year_bin_label"]},
        PIE_SIZE_LEGEND_CIRCLES_PATH: {"field_names": ["legend_gw", "radius_m"]},
        PIE_SIZE_LEGEND_LABELS_PATH: {"field_names": ["kind", "legend_label"]},
        LEGEND_FRAMES_PATH: {"field_names": ["frame_type"]},
        pie_pre: {"field_names": ["energy_type"]},
        pie_1991: {"field_names": ["energy_type"]},
    }

    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": 1, "total_kw": 1000000}},
            {"properties": {"year_bin_slug": "1991_1992", "value_anchor": 1, "total_kw": 3000000}},
            {"properties": {"year_bin_slug": "title", "value_anchor": 1, "total_kw": 999}},
        ]
    }

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths=existing_paths,
        layer_defs=layer_defs,
        chart_json=chart,
    )

    parent_group = project.root.findGroup("nationwide_landkreis_pies (yearly)")
    assert parent_group is not None

    parent_layer_names = [layer.name() for layer in parent_group.layers]
    assert "chart_frames" in parent_layer_names
    assert "energy_legend" in parent_layer_names
    assert "pie_size_legend_circles" in parent_layer_names
    assert "pie_size_legend_labels" in parent_layer_names
    assert "legend_frames" in parent_layer_names

    assert "≤1990" in parent_group.groups
    assert "1991–1992" in parent_group.groups

    first_bin = parent_group.findGroup("≤1990")
    second_bin = parent_group.findGroup("1991–1992")

    first_names = [layer.name() for layer in first_bin.layers]
    second_names = [layer.name() for layer in second_bin.layers]

    assert "landkreis_pies_pre_1990" in first_names
    assert "yearly_rowChart_total_power_pre_1990" in first_names
    assert "yearly_rowChart_guides_pre_1990" in first_names
    assert "state_columnBars_pre_1990" in first_names
    assert "state_columnLabels_pre_1990" in first_names
    assert "pre_1990_heading" in first_names

    assert "landkreis_pies_1991_1992" in second_names
    assert "yearly_rowChart_total_power_1991_1992" in second_names
    assert "yearly_rowChart_guides_1991_1992" in second_names
    assert "state_columnBars_1991_1992" in second_names
    assert "state_columnLabels_1991_1992" in second_names
    assert "1991_1992_heading" in second_names

    row_pre = next(layer for layer in first_bin.layers if layer.name() == "yearly_rowChart_total_power_pre_1990")
    row_1991 = next(layer for layer in second_bin.layers if layer.name() == "yearly_rowChart_total_power_1991_1992")

    assert row_pre.subsetString() == "(\"year_bin_slug\" IN ('pre_1990') OR \"year_bin_slug\" IN ('title','unit'))"
    assert row_1991.subsetString() == "(\"year_bin_slug\" IN ('pre_1990','1991_1992') OR \"year_bin_slug\" IN ('title','unit'))"

    guides_pre = next(layer for layer in first_bin.layers if layer.name() == "yearly_rowChart_guides_pre_1990")
    guides_1991 = next(layer for layer in second_bin.layers if layer.name() == "yearly_rowChart_guides_1991_1992")

    assert guides_pre.subsetString() == "\"year_bin_slug\" IN ('pre_1990')"
    assert guides_1991.subsetString() == "\"year_bin_slug\" IN ('pre_1990','1991_1992')"

    bars_pre = next(layer for layer in first_bin.layers if layer.name() == "state_columnBars_pre_1990")
    labels_pre = next(layer for layer in first_bin.layers if layer.name() == "state_columnLabels_pre_1990")

    assert bars_pre.subsetString() == "\"year_bin_slug\" = 'pre_1990'"
    assert labels_pre.subsetString() == "(\"year_bin_slug\" = 'pre_1990' OR \"year_bin_slug\" = 'state_title')"


def test_main_logs_info_when_pie_file_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[INFO] Pie file missing for bin pre_1990:" in captured.out


def test_main_warns_when_invalid_pie_layer(monkeypatch, capsys):
    pie_pre = ROOT_DIR + r"\pre_1990\de_landkreis_pie_pre_1990.geojson"

    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, pie_pre},
        layer_defs={
            pie_pre: {"is_valid": False},
        },
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert f"[WARN] Invalid pie layer: {pie_pre}" in captured.out


def test_main_warns_when_state_column_paths_missing(monkeypatch, capsys):
    chart = {
        "features": [
            {"properties": {"year_bin_slug": "pre_1990", "value_anchor": 1, "total_kw": 1000000}},
        ]
    }

    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, YEARLY_CHART_PATH, GUIDES_PATH},
        layer_defs={
            YEARLY_CHART_PATH: {"field_names": ["energy_type", "year_bin_slug", "label_anchor", "value_anchor", "total_kw"]},
            GUIDES_PATH: {"field_names": ["year_bin_slug"]},
        },
        chart_json=chart,
    )

    captured = capsys.readouterr()
    assert "[WARN] STATE_COL_BARS_PATH not found:" in captured.out
    assert "[WARN] STATE_COL_LABELS_PATH not found:" in captured.out


def test_main_warns_when_legend_layer_invalid(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR, LEGEND_PATH},
        layer_defs={
            LEGEND_PATH: {"is_valid": False},
        },
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Legend layer invalid:" in captured.out


def test_main_handles_period_gw_computation_failure(monkeypatch, capsys):
    def fake_open_raises(path, mode="r", encoding=None):
        raise ValueError("boom")

    clear_module()
    FakePath.existing_paths = {ROOT_DIR, YEARLY_CHART_PATH}

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
    assert "[WARN] Could not compute PER_BIN_GW:" in captured.out


def test_style_pie_size_legend_circles_layer_sets_outline_only_symbol(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie_size_circles", "ogr")

    module.style_pie_size_legend_circles_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"
    assert renderer.symbol.props["outline_color"] == "90,90,90,255"
    assert renderer.symbol.output_unit == FakeQgsUnitTypes.RenderMillimeters
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_style_pie_size_legend_labels_layer_builds_title_and_item_rules(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie_size_labels", "ogr")

    module.style_pie_size_legend_labels_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"

    labeling = lyr.labeling()
    assert isinstance(labeling, FakeQgsRuleBasedLabeling)

    rules = labeling.root_rule.children
    assert len(rules) == 2
    assert rules[0].filter_expression == "\"kind\" = 'title'"
    assert rules[0].pal.format.font.weight == FakeQFont.Bold
    assert rules[1].filter_expression == "\"kind\" = 'item'"

    assert lyr.labelsEnabled() is True
    assert lyr.repaintCalled() is True


def test_style_legend_frames_layer_sets_transparent_frame_style(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "legend_frames", "ogr")

    module.style_legend_frames_layer(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props["color"] == "0,0,0,0"
    assert renderer.symbol.props["outline_color"] == "150,150,150,255"
    assert renderer.symbol.output_unit == FakeQgsUnitTypes.RenderMillimeters
    assert lyr.labelsEnabled() is False
    assert lyr.repaintCalled() is True


def test_make_unified_title_format_is_bold_and_shared_size(minimal_import):
    module, _, _ = minimal_import

    fmt = module.make_unified_title_format()

    assert fmt.font.family == module.UNIFIED_TITLE_FONT_FAMILY
    assert fmt.font.size == module.UNIFIED_TITLE_FONT_SIZE
    assert fmt.font.weight == FakeQFont.Bold
    assert fmt.size == module.UNIFIED_TITLE_FONT_SIZE
    assert fmt.buffer.enabled is False


def test_style_state_column_labels_layer_uses_state_abbrev(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "labels", "ogr")

    module.style_state_column_labels_layer(lyr)

    rules = lyr.labeling().root_rule.children
    assert rules[0].pal.fieldName == (
        "CASE WHEN \"kind\" = 'state_label' THEN \"state_abbrev\" ELSE NULL END"
    )
    assert rules[0].pal.format.font.weight == FakeQFont.Bold
    assert rules[2].pal.format.font.weight == FakeQFont.Bold


def test_main_warns_when_pie_size_legend_and_frames_missing(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        layer_defs={},
        chart_json=None,
    )

    captured = capsys.readouterr()
    assert "[WARN] Pie size legend circles file not found:" in captured.out
    assert "[WARN] Pie size legend labels file not found:" in captured.out
    assert "[WARN] Legend frames file not found:" in captured.out