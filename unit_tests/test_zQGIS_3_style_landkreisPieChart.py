# Filename: unit_tests/test_zQGIS_3_style_landkreisPieChart.py

import importlib
import pathlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.3_style_landkreisPieChart"


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
# Fake layer tree
# -------------------------------------------------------------------

class FakeNode:
    pass


class FakeLayerNode(FakeNode):
    def __init__(self, layer):
        self.layer = layer


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

    def children(self):
        children = []
        for grp in self.groups.values():
            children.append(grp)
        for lyr in self.layers:
            children.append(FakeLayerNode(lyr))
        return children

    def removeChildNode(self, node):
        if isinstance(node, FakeLayerTreeGroup):
            for key, value in list(self.groups.items()):
                if value is node:
                    del self.groups[key]
                    return
        elif isinstance(node, FakeLayerNode):
            self.layers = [lyr for lyr in self.layers if lyr is not node.layer]


class FakeRoot(FakeLayerTreeGroup):
    pass


# -------------------------------------------------------------------
# Fake vector layer / project
# -------------------------------------------------------------------

class FakeVectorLayer:
    def __init__(self, source, name, provider, *, is_valid=True):
        self._source = str(source)
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._renderer = None
        self._repaint_called = False

    def source(self):
        return self._source

    def name(self):
        return self._name

    def isValid(self):
        return self._is_valid

    def setRenderer(self, renderer):
        self._renderer = renderer

    def renderer(self):
        return self._renderer

    def triggerRepaint(self):
        self._repaint_called = True

    def repaintCalled(self):
        return self._repaint_called


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
    dir_children = {}
    glob_map = {}

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

    def is_dir(self):
        return self.path in self.dir_children

    def iterdir(self):
        for child in self.dir_children.get(self.path, []):
            yield FakePath(child)

    def glob(self, pattern):
        for item in self.glob_map.get((self.path, pattern), []):
            yield FakePath(item)


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\pieCharts\nationwide_landkreis_pies"


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

    qgis_qtgui.QColor = FakeQColor

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
    dir_children=None,
    glob_map=None,
    layer_validity_by_source=None,
):
    clear_module()

    FakePath.existing_paths = set(existing_paths or [])
    FakePath.dir_children = dict(dir_children or {})
    FakePath.glob_map = dict(glob_map or {})

    project = FakeProject()
    created_layers = []

    layer_validity_by_source = layer_validity_by_source or {}
    vector_factory = build_vector_layer_factory(layer_validity_by_source, created_layers)

    install_fake_qgis(monkeypatch, project, vector_factory)

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
    bayern_dir = BASE_DIR + r"\bayern"
    canonical = bayern_dir + r"\de_bayern_landkreis_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, bayern_dir, canonical},
        dir_children={
            BASE_DIR: [bayern_dir],
            bayern_dir: [],
        },
        glob_map={},
        layer_validity_by_source={canonical: True},
    )
    return module, project, created_layers


# -------------------------------------------------------------------
# Tests: ensure_group
# -------------------------------------------------------------------

def test_ensure_group_creates_group_when_missing(minimal_import):
    module, project, _ = minimal_import

    grp = module.ensure_group(project.root, "my_group")

    assert grp is project.root.groups["my_group"]


def test_ensure_group_reuses_existing_group(minimal_import):
    module, project, _ = minimal_import

    grp1 = module.ensure_group(project.root, "my_group")
    grp2 = module.ensure_group(project.root, "my_group")

    assert grp1 is grp2
    assert len(project.root.groups) >= 1


# -------------------------------------------------------------------
# Tests: style_energy_type
# -------------------------------------------------------------------

def test_style_energy_type_sets_categorized_renderer(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_energy_type(lyr)

    renderer = lyr.renderer()
    assert isinstance(renderer, FakeCategorizedSymbolRenderer)
    assert renderer.field_name == "energy_type"
    assert len(renderer.categories) == len(module.PALETTE)
    assert lyr.repaintCalled() is True


def test_style_energy_type_builds_expected_palette_categories(minimal_import):
    module, _, _ = minimal_import
    lyr = FakeVectorLayer("x", "pie", "ogr")

    module.style_energy_type(lyr)

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
# Tests: load_state_layer
# -------------------------------------------------------------------

def test_load_state_layer_prefers_canonical_filename(minimal_import, capsys):
    module, project, _ = minimal_import
    group = project.root.addGroup("target")

    project.added_layers.clear()
    group.layers.clear()

    state_dir = FakePath(BASE_DIR + r"\bayern")
    module.load_state_layer(state_dir, group)

    assert len(project.added_layers) == 1
    layer, add_to_root = project.added_layers[-1]
    assert add_to_root is False
    assert layer.source() == BASE_DIR + r"\bayern\de_bayern_landkreis_pie.geojson"
    assert layer.name() == "Bayern"
    assert layer in group.layers

    captured = capsys.readouterr()
    assert "[OK] Loaded: bayern -> de_bayern_landkreis_pie.geojson" in captured.out


def test_load_state_layer_uses_fallback_glob_when_canonical_missing(monkeypatch, capsys):
    hessen_dir = BASE_DIR + r"\hessen"
    fallback = hessen_dir + r"\de_custom_landkreis_pie_v2.geojson"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, hessen_dir, fallback},
        dir_children={
            BASE_DIR: [hessen_dir],
            hessen_dir: [],
        },
        glob_map={
            (hessen_dir, "de_*_landkreis_pie*.geojson"): [fallback],
        },
        layer_validity_by_source={fallback: True},
    )

    group = project.root.addGroup("target")
    project.added_layers.clear()
    group.layers.clear()

    module.load_state_layer(FakePath(hessen_dir), group)

    assert len(project.added_layers) == 1
    layer, _ = project.added_layers[-1]
    assert layer.source() == fallback
    assert layer.name() == "Hessen"

    captured = capsys.readouterr()
    assert "[OK] Loaded: hessen -> de_custom_landkreis_pie_v2.geojson" in captured.out


def test_load_state_layer_skips_when_no_matching_file(monkeypatch, capsys):
    berlin_dir = BASE_DIR + r"\berlin"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, berlin_dir},
        dir_children={
            BASE_DIR: [berlin_dir],
            berlin_dir: [],
        },
        glob_map={},
        layer_validity_by_source={},
    )

    group = project.root.addGroup("target")
    project.added_layers.clear()
    group.layers.clear()

    module.load_state_layer(FakePath(berlin_dir), group)

    assert project.added_layers == []
    assert group.layers == []

    captured = capsys.readouterr()
    assert f"[SKIP] No pie geojson in: {berlin_dir}" in captured.out


def test_load_state_layer_skips_invalid_layer(monkeypatch, capsys):
    sachsen_dir = BASE_DIR + r"\sachsen"
    canonical = sachsen_dir + r"\de_sachsen_landkreis_pie.geojson"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, sachsen_dir, canonical},
        dir_children={
            BASE_DIR: [sachsen_dir],
            sachsen_dir: [],
        },
        glob_map={},
        layer_validity_by_source={canonical: False},
    )

    group = project.root.addGroup("target")
    project.added_layers.clear()
    group.layers.clear()

    module.load_state_layer(FakePath(sachsen_dir), group)

    assert project.added_layers == []
    assert group.layers == []

    captured = capsys.readouterr()
    assert f"[WARN] Invalid layer: {canonical}" in captured.out


def test_load_state_layer_uses_slug_when_pretty_name_missing(monkeypatch):
    custom_dir = BASE_DIR + r"\custom-state"
    canonical = custom_dir + r"\de_custom-state_landkreis_pie.geojson"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, custom_dir, canonical},
        dir_children={
            BASE_DIR: [custom_dir],
            custom_dir: [],
        },
        glob_map={},
        layer_validity_by_source={canonical: True},
    )

    group = project.root.addGroup("target")
    project.added_layers.clear()
    group.layers.clear()

    module.load_state_layer(FakePath(custom_dir), group)

    layer, _ = project.added_layers[-1]
    assert layer.name() == "custom-state"


# -------------------------------------------------------------------
# Tests: main()
# -------------------------------------------------------------------

def test_main_raises_when_base_dir_missing(monkeypatch):
    with pytest.raises(Exception, match=r"\[ERROR\] BASE_DIR not found:"):
        import_module_with_fakes(
            monkeypatch,
            existing_paths=set(),
            dir_children={},
            glob_map={},
            layer_validity_by_source={},
        )


def test_main_raises_when_no_state_folders(monkeypatch):
    with pytest.raises(Exception, match=r"\[ERROR\] No state folders under:"):
        import_module_with_fakes(
            monkeypatch,
            existing_paths={BASE_DIR},
            dir_children={
                BASE_DIR: [],
            },
            glob_map={},
            layer_validity_by_source={},
        )


def test_main_cleans_existing_group_children_before_loading(minimal_import):
    module, project, _ = minimal_import

    main_group = project.root.findGroup("landkreis_pies")
    assert main_group is not None

    old_subgroup = main_group.addGroup("old_group")
    old_layer = FakeVectorLayer("old_source", "old_layer", "ogr")
    main_group.addLayer(old_layer)

    module.main()

    main_group = project.root.findGroup("landkreis_pies")
    child_group_names = list(main_group.groups.keys())
    child_layer_names = [lyr.name() for lyr in main_group.layers]

    assert "old_group" not in child_group_names
    assert "old_layer" not in child_layer_names


def test_main_loads_state_layers_directly_under_main_group(monkeypatch, capsys):
    bayern_dir = BASE_DIR + r"\bayern"
    berlin_dir = BASE_DIR + r"\berlin"
    bayern_file = bayern_dir + r"\de_bayern_landkreis_pie.geojson"
    berlin_file = berlin_dir + r"\de_berlin_landkreis_pie.geojson"

    module, project, created_layers = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, bayern_dir, berlin_dir, bayern_file, berlin_file},
        dir_children={
            BASE_DIR: [berlin_dir, bayern_dir],
            bayern_dir: [],
            berlin_dir: [],
        },
        glob_map={},
        layer_validity_by_source={
            bayern_file: True,
            berlin_file: True,
        },
    )

    main_group = project.root.findGroup("landkreis_pies")
    assert main_group is not None

    layer_names = [lyr.name() for lyr in main_group.layers]
    assert layer_names == ["Bayern", "Berlin"]

    captured = capsys.readouterr()
    assert "✅ Folder-based state assignment complete (no spatial clipping)." in captured.out


def test_main_sorts_state_directories_by_name(monkeypatch):
    sachsen_dir = BASE_DIR + r"\sachsen"
    bayern_dir = BASE_DIR + r"\bayern"
    sachsen_file = sachsen_dir + r"\de_sachsen_landkreis_pie.geojson"
    bayern_file = bayern_dir + r"\de_bayern_landkreis_pie.geojson"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, sachsen_dir, bayern_dir, sachsen_file, bayern_file},
        dir_children={
            BASE_DIR: [sachsen_dir, bayern_dir],
            sachsen_dir: [],
            bayern_dir: [],
        },
        glob_map={},
        layer_validity_by_source={
            sachsen_file: True,
            bayern_file: True,
        },
    )

    main_group = project.root.findGroup("landkreis_pies")
    assert main_group is not None

    assert [lyr.name() for lyr in main_group.layers] == ["Bayern", "Sachsen"]


def test_main_handles_mixed_valid_invalid_and_missing_states(monkeypatch, capsys):
    bayern_dir = BASE_DIR + r"\bayern"
    sachsen_dir = BASE_DIR + r"\sachsen"
    berlin_dir = BASE_DIR + r"\berlin"

    bayern_file = bayern_dir + r"\de_bayern_landkreis_pie.geojson"
    sachsen_file = sachsen_dir + r"\de_sachsen_landkreis_pie.geojson"

    module, project, _ = import_module_with_fakes(
        monkeypatch,
        existing_paths={BASE_DIR, bayern_dir, sachsen_dir, berlin_dir, bayern_file, sachsen_file},
        dir_children={
            BASE_DIR: [berlin_dir, sachsen_dir, bayern_dir],
            bayern_dir: [],
            sachsen_dir: [],
            berlin_dir: [],
        },
        glob_map={},
        layer_validity_by_source={
            bayern_file: True,
            sachsen_file: False,
        },
    )

    main_group = project.root.findGroup("landkreis_pies")
    assert main_group is not None

    assert [lyr.name() for lyr in main_group.layers] == ["Bayern"]

    captured = capsys.readouterr()
    assert "[OK] Loaded: bayern -> de_bayern_landkreis_pie.geojson" in captured.out
    assert f"[WARN] Invalid layer: {sachsen_file}" in captured.out
    assert f"[SKIP] No pie geojson in: {berlin_dir}" in captured.out