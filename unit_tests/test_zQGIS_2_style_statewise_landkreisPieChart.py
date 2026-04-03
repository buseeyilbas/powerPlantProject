# Filename: unit_tests/test_zQGIS_2_style_statewise_landkreisPieChart.py

import importlib
import pathlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.2_style_statewise_landkreisPieChart"


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

    def __init__(self):
        self.enabled = False
        self.isExpression = False
        self.fieldName = None
        self.format = None
        self.placement = None
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


# -------------------------------------------------------------------
# Fake symbols / renderers
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# Fake path / layers / groups / project
# -------------------------------------------------------------------

class FakePath:
    existing_paths = set()
    resolve_raises_for = set()

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
    def stem(self):
        name = self.name
        if "." not in name:
            return name
        return name.rsplit(".", 1)[0]

    def exists(self):
        return self.path in self.existing_paths

    def resolve(self):
        if self.path in self.resolve_raises_for:
            raise RuntimeError("resolve failed")
        normalized = self.path.replace("/", "\\").lower()
        return normalized


class FakeVectorLayer:
    def __init__(
        self,
        source,
        name,
        provider,
        *,
        is_valid=True,
    ):
        self._source = str(source)
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._renderer = None
        self._labels_enabled = None
        self._labeling = None
        self._repaint_called = False

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


class FakeLayerTreeGroup:
    def __init__(self, name):
        self.name = name
        self.groups = {}
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
    def __init__(self, existing_layers=None):
        self.root = FakeLayerTreeGroup("root")
        self._map_layers = {}
        self.added_layers = []

        if existing_layers:
            for idx, layer in enumerate(existing_layers):
                self._map_layers[f"layer_{idx}"] = layer

    def layerTreeRoot(self):
        return self.root

    def mapLayers(self):
        return self._map_layers

    def addMapLayer(self, layer, add_to_root=True):
        self.added_layers.append((layer, add_to_root))
        self._map_layers[f"added_{len(self.added_layers)}"] = layer


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

ROOT_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\statewise_landkreis_pies"


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

    qgis_qtgui.QColor = FakeQColor
    qgis_qtgui.QFont = FakeQFont

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)


def build_vector_layer_factory(layer_validity_by_source, created_layers):
    def factory(source, name, provider):
        src = str(source)
        is_valid = layer_validity_by_source.get(src, True)
        layer = FakeVectorLayer(src, name, provider, is_valid=is_valid)
        created_layers.append(layer)
        return layer
    return factory


def import_module_with_fakes(
    monkeypatch,
    *,
    existing_paths=None,
    os_walk_rows=None,
    existing_layers=None,
    layer_validity_by_source=None,
):
    clear_module()

    FakePath.existing_paths = set(existing_paths or [])
    FakePath.resolve_raises_for = set()

    project = FakeProject(existing_layers=existing_layers)
    created_layers = []

    layer_validity_by_source = layer_validity_by_source or {}
    vector_factory = build_vector_layer_factory(layer_validity_by_source, created_layers)

    install_fake_qgis(monkeypatch, project, vector_factory)

    def fake_walk(path):
        for row in os_walk_rows or []:
            yield row

    fake_os = types.ModuleType("os")
    fake_os.walk = fake_walk

    monkeypatch.setitem(sys.modules, "os", fake_os)

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
        os_walk_rows=[],
        existing_layers=[],
        layer_validity_by_source={},
    )
    return module, project, created_layers


# -------------------------------------------------------------------
# Tests: helper functions
# -------------------------------------------------------------------

def test_ensure_group_creates_group_when_missing(minimal_import, capsys):
    module, project, _ = minimal_import

    grp = module.ensure_group("my_group")

    assert grp is project.root.groups["my_group"]

    captured = capsys.readouterr()
    assert "[INFO] Created group: my_group" in captured.out


def test_ensure_group_reuses_existing_group(minimal_import, capsys):
    module, project, _ = minimal_import

    grp1 = module.ensure_group("my_group")
    grp2 = module.ensure_group("my_group")

    assert grp1 is grp2

    captured = capsys.readouterr()
    assert captured.out.count("[INFO] Created group: my_group") == 1


def test_already_loaded_returns_true_when_same_resolved_path(monkeypatch):
    existing_layer = FakeVectorLayer(
        source=ROOT_DIR + r"\bayern\abc_pie.geojson",
        name="abc_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[],
        existing_layers=[existing_layer],
        layer_validity_by_source={},
    )

    assert module.already_loaded(ROOT_DIR + r"\bayern\abc_pie.geojson") is True


def test_already_loaded_returns_false_when_no_match(monkeypatch):
    existing_layer = FakeVectorLayer(
        source=ROOT_DIR + r"\bayern\abc_pie.geojson",
        name="abc_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[],
        existing_layers=[existing_layer],
        layer_validity_by_source={},
    )

    assert module.already_loaded(ROOT_DIR + r"\bayern\different_pie.geojson") is False


def test_already_loaded_ignores_resolve_errors(monkeypatch):
    existing_layer = FakeVectorLayer(
        source=ROOT_DIR + r"\bad_source.geojson",
        name="bad_source",
        provider="ogr",
        is_valid=True,
    )

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[],
        existing_layers=[existing_layer],
        layer_validity_by_source={},
    )

    FakePath.resolve_raises_for.add(ROOT_DIR + r"\bad_source.geojson")
    assert module.already_loaded(ROOT_DIR + r"\another.geojson") is False


# -------------------------------------------------------------------
# Tests: style_one
# -------------------------------------------------------------------

def test_style_one_sets_categorized_renderer_and_disables_labels(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_one(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert lyr.labelsEnabled() is False
    assert lyr.labeling() is None
    assert lyr.repaintCalled() is True


def test_style_one_builds_expected_palette_categories(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_one(lyr)

    renderer = lyr.renderer()
    values = [cat.value for cat in renderer.categories]
    assert values == list(module.PALETTE.keys())

    for cat in renderer.categories:
        color = module.PALETTE[cat.value]
        assert cat.label == cat.value
        assert cat.symbol.props["color"] == f"{color.red()},{color.green()},{color.blue()},255"
        assert cat.symbol.props["outline_style"] == "no"
        assert cat.symbol.props["outline_color"] == "0,0,0,0"
        assert cat.symbol.props["outline_width"] == "0"


# -------------------------------------------------------------------
# Tests: main()
# -------------------------------------------------------------------

def test_main_raises_when_root_dir_missing(monkeypatch):
    with pytest.raises(Exception, match=r"\[ERROR\] ROOT_DIR not found:"):
        import_module_with_fakes(
            monkeypatch,
            existing_paths=set(),
            os_walk_rows=[],
            existing_layers=[],
            layer_validity_by_source={},
        )


def test_main_warns_when_no_targets_found(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (ROOT_DIR, ["bayern"], ["not_a_target.geojson", "also_pies.geojson"]),
        ],
        existing_layers=[],
        layer_validity_by_source={},
    )

    captured = capsys.readouterr()
    assert "[WARN] No '*_pie.geojson' found under:" in captured.out


def test_main_finds_only__pie_geojson_files_and_skips__pies_geojson(monkeypatch, capsys):
    base = ROOT_DIR + r"\bayern"
    target1 = base + r"\a_pie.geojson"
    target2 = base + r"\b_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (
                base,
                [],
                [
                    "a_pie.geojson",
                    "b_pie.geojson",
                    "a_pies.geojson",
                    "notes.txt",
                    "something.geojson",
                ],
            ),
        ],
        existing_layers=[],
        layer_validity_by_source={},
    )

    created_names = [layer.name() for layer in created_layers]
    assert "a_pie" in created_names
    assert "b_pie" in created_names
    assert "a_pies" not in created_names

    captured = capsys.readouterr()
    assert "[INFO] Found 2 pie files to load." in captured.out


def test_main_skips_already_loaded_layers(monkeypatch, capsys):
    already = FakeVectorLayer(
        source=ROOT_DIR + r"\bayern\a_pie.geojson",
        name="a_pie",
        provider="ogr",
        is_valid=True,
    )

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (
                ROOT_DIR + r"\bayern",
                [],
                ["a_pie.geojson", "b_pie.geojson"],
            ),
        ],
        existing_layers=[already],
        layer_validity_by_source={ROOT_DIR + r"\bayern\b_pie.geojson": True},
    )

    group = project.root.findGroup("statewise_landkreis_pies")
    assert group is not None

    layer_names = [layer.name() for layer in group.layers]
    assert "a_pie" not in layer_names
    assert "b_pie" in layer_names

    captured = capsys.readouterr()
    assert "[SKIP] Already loaded: a_pie.geojson" in captured.out


def test_main_skips_invalid_layers(monkeypatch, capsys):
    invalid_src = ROOT_DIR + r"\bayern\invalid_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (
                ROOT_DIR + r"\bayern",
                [],
                ["invalid_pie.geojson"],
            ),
        ],
        existing_layers=[],
        layer_validity_by_source={invalid_src: False},
    )

    group = project.root.findGroup("statewise_landkreis_pies")
    assert group is not None
    assert group.layers == []

    captured = capsys.readouterr()
    assert "[WARN] Invalid layer: invalid_pie.geojson" in captured.out


def test_main_loads_and_styles_valid_layers(monkeypatch, capsys):
    src1 = ROOT_DIR + r"\bayern\a_pie.geojson"
    src2 = ROOT_DIR + r"\sachsen\b_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (ROOT_DIR + r"\bayern", [], ["a_pie.geojson"]),
            (ROOT_DIR + r"\sachsen", [], ["b_pie.geojson"]),
        ],
        existing_layers=[],
        layer_validity_by_source={src1: True, src2: True},
    )

    group = project.root.findGroup("statewise_landkreis_pies")
    assert group is not None

    group_layer_names = [layer.name() for layer in group.layers]
    assert group_layer_names == ["a_pie", "b_pie"]

    assert len(project.added_layers) == 2
    assert all(add_to_root is False for _, add_to_root in project.added_layers)

    for layer in group.layers:
        renderer = layer.renderer()
        assert isinstance(renderer, FakeCategorizedSymbolRenderer)
        assert renderer.field_name == "energy_type"
        assert len(renderer.categories) == len(module.PALETTE)
        assert layer.labelsEnabled() is False
        assert layer.repaintCalled() is True

    captured = capsys.readouterr()
    assert "[OK] Loaded + styled: a_pie.geojson" in captured.out
    assert "[OK] Loaded + styled: b_pie.geojson" in captured.out
    assert "[DONE] Loaded 2 layers, styled 2. Labels OFF." in captured.out


def test_main_sorts_targets_before_loading(monkeypatch):
    src_a = ROOT_DIR + r"\aaa\a_pie.geojson"
    src_b = ROOT_DIR + r"\zzz\z_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (ROOT_DIR + r"\zzz", [], ["z_pie.geojson"]),
            (ROOT_DIR + r"\aaa", [], ["a_pie.geojson"]),
        ],
        existing_layers=[],
        layer_validity_by_source={src_a: True, src_b: True},
    )

    group = project.root.findGroup("statewise_landkreis_pies")
    assert group is not None

    # sorted(targets) should load aaa/a_pie before zzz/z_pie
    assert [layer.source() for layer in group.layers] == [src_a, src_b]


def test_main_creates_group_once_and_reuses_it(monkeypatch, capsys):
    src1 = ROOT_DIR + r"\bayern\a_pie.geojson"
    src2 = ROOT_DIR + r"\bayern\b_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (ROOT_DIR + r"\bayern", [], ["a_pie.geojson", "b_pie.geojson"]),
        ],
        existing_layers=[],
        layer_validity_by_source={src1: True, src2: True},
    )

    assert "statewise_landkreis_pies" in project.root.groups
    assert len(project.root.groups) == 1

    captured = capsys.readouterr()
    assert captured.out.count("[INFO] Created group: statewise_landkreis_pies") == 1


def test_main_summary_counts_only_loaded_valid_non_duplicate_layers(monkeypatch, capsys):
    existing = FakeVectorLayer(
        source=ROOT_DIR + r"\nrw\already_pie.geojson",
        name="already_pie",
        provider="ogr",
        is_valid=True,
    )

    good_src = ROOT_DIR + r"\nrw\good_pie.geojson"
    bad_src = ROOT_DIR + r"\nrw\bad_pie.geojson"

    import_module_with_fakes(
        monkeypatch,
        existing_paths={ROOT_DIR},
        os_walk_rows=[
            (
                ROOT_DIR + r"\nrw",
                [],
                ["already_pie.geojson", "good_pie.geojson", "bad_pie.geojson"],
            ),
        ],
        existing_layers=[existing],
        layer_validity_by_source={good_src: True, bad_src: False},
    )

    captured = capsys.readouterr()
    assert "[DONE] Loaded 1 layers, styled 1. Labels OFF." in captured.out