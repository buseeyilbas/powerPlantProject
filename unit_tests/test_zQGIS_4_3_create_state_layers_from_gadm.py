# Filename: unit_tests/test_zQGIS_4_3_create_state_layers_from_gadm.py

import importlib
import os
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.4_3_create_state_layers_from_gadm"


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
# Fake fields
# -------------------------------------------------------------------

class FakeFields:
    def __init__(self, names):
        self.names = list(names)

    def indexOf(self, name):
        try:
            return self.names.index(name)
        except ValueError:
            return -1


# -------------------------------------------------------------------
# Fake layer tree classes
# -------------------------------------------------------------------

class FakeLayerTreeLayer:
    def __init__(self, layer):
        self.layer = layer


class FakeLayerTreeGroup:
    def __init__(self, name):
        self.name = name
        self.groups = []
        self.layer_nodes = []
        self.visibility_checked = None

    def findGroup(self, name):
        for grp in self.groups:
            if grp.name == name:
                return grp
        return None

    def addGroup(self, name):
        grp = FakeLayerTreeGroup(name)
        self.groups.append(grp)
        return grp

    def insertChildNode(self, index, node):
        self.layer_nodes.insert(index, node)

    def children(self):
        return list(self.groups) + list(self.layer_nodes)

    def removeChildNode(self, node):
        if node in self.groups:
            self.groups.remove(node)
        elif node in self.layer_nodes:
            self.layer_nodes.remove(node)

    def setItemVisibilityChecked(self, value):
        self.visibility_checked = value


class FakeRoot(FakeLayerTreeGroup):
    def __init__(self):
        super().__init__("root")
        self.insert_group_calls = []

    def insertGroup(self, index, name):
        grp = FakeLayerTreeGroup(name)
        self.groups.insert(index, grp)
        self.insert_group_calls.append((index, name, grp))
        return grp


# -------------------------------------------------------------------
# Fake vector layer / project
# -------------------------------------------------------------------

class FakeVectorLayer:
    _counter = 0

    def __init__(
        self,
        source,
        name,
        provider,
        *,
        is_valid=True,
        field_names=None,
        unique_values_by_index=None,
    ):
        FakeVectorLayer._counter += 1
        self._id = f"layer_{FakeVectorLayer._counter}"
        self._source = str(source)
        self._name = name
        self._provider = provider
        self._is_valid = is_valid
        self._fields = FakeFields(field_names or [])
        self._unique_values_by_index = dict(unique_values_by_index or {})
        self._subset_string = None
        self._renderer = None

    def id(self):
        return self._id

    def source(self):
        return self._source

    def name(self):
        return self._name

    def isValid(self):
        return self._is_valid

    def fields(self):
        return self._fields

    def uniqueValues(self, idx):
        return self._unique_values_by_index.get(idx, [])

    def setSubsetString(self, subset):
        self._subset_string = subset

    def subsetString(self):
        return self._subset_string

    def setRenderer(self, renderer):
        self._renderer = renderer

    def renderer(self):
        return self._renderer


class FakeProject:
    def __init__(self, root=None):
        self.root = root or FakeRoot()
        self.added_layers = []

    def layerTreeRoot(self):
        return self.root

    def addMapLayer(self, layer, add_to_root=True):
        self.added_layers.append((layer, add_to_root))


# -------------------------------------------------------------------
# Import helpers
# -------------------------------------------------------------------

BASE_PATH = r"C:/Users/jo73vure/Desktop/powerPlantProject/gadm_data/gadm41_DEU"
GADM1_FILE = "gadm41_DEU_1.json"
STATE_FIELD = "NAME_1"
GROUP_NAME = "DE States (masked)"
DEFAULT_VISIBLE_STATE = "Thüringen"


def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(
    monkeypatch,
    *,
    src_is_valid=True,
    src_field_names=None,
    src_unique_values=None,
    existing_parent_group=None,
):
    clear_module()
    FakeVectorLayer._counter = 0

    root = FakeRoot()
    if existing_parent_group is not None:
        root.groups.append(existing_parent_group)

    project = FakeProject(root=root)
    created_layers = []

    src_path = os.path.join(BASE_PATH, GADM1_FILE).replace("\\", "/")

    qgis_module = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qgis_qtgui = types.ModuleType("qgis.PyQt.QtGui")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    def fake_vector_layer(source, name, provider):
        source = str(source)
        if source == src_path and name == "gadm_1_src":
            layer = FakeVectorLayer(
                source,
                name,
                provider,
                is_valid=src_is_valid,
                field_names=src_field_names or [STATE_FIELD],
                unique_values_by_index={0: src_unique_values or ["Bayern", "Thüringen"]},
            )
        else:
            layer = FakeVectorLayer(source, name, provider, is_valid=True)
        created_layers.append(layer)
        return layer

    qgis_core.QgsProject = FakeQgsProject
    qgis_core.QgsVectorLayer = fake_vector_layer
    qgis_core.QgsFillSymbol = FakeFillSymbol
    qgis_core.QgsSingleSymbolRenderer = FakeSingleSymbolRenderer
    qgis_core.QgsInvertedPolygonRenderer = FakeInvertedPolygonRenderer
    qgis_core.QgsLayerTreeLayer = FakeLayerTreeLayer

    class FakeQColor:
        def __init__(self, *args, **kwargs):
            self.args = args

    qgis_qtgui.QColor = FakeQColor

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)

    module = importlib.import_module(MODULE_NAME)
    return module, project, created_layers, src_path


# -------------------------------------------------------------------
# Tests: failure cases
# -------------------------------------------------------------------

def test_raises_when_source_layer_is_invalid(monkeypatch):
    with pytest.raises(RuntimeError, match=r"Could not open '.*gadm41_DEU_1\.json'"):
        import_module_with_fakes(
            monkeypatch,
            src_is_valid=False,
            src_field_names=[STATE_FIELD],
            src_unique_values=["Bayern", "Thüringen"],
        )


def test_raises_when_state_field_missing(monkeypatch):
    with pytest.raises(RuntimeError, match=r"Field 'NAME_1' not found in gadm41_DEU_1\.json"):
        import_module_with_fakes(
            monkeypatch,
            src_is_valid=True,
            src_field_names=["WRONG_FIELD"],
            src_unique_values=["Bayern", "Thüringen"],
        )


# -------------------------------------------------------------------
# Tests: group creation / cleanup
# -------------------------------------------------------------------

def test_creates_parent_group_with_insert_group_when_missing(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_is_valid=True,
        src_field_names=[STATE_FIELD],
        src_unique_values=["Bayern"],
    )

    grp = project.root.findGroup(GROUP_NAME)
    assert grp is not None
    assert project.root.insert_group_calls[0][0] == 0
    assert project.root.insert_group_calls[0][1] == GROUP_NAME


def test_reuses_existing_parent_group_and_clears_previous_children(monkeypatch):
    existing = FakeLayerTreeGroup(GROUP_NAME)
    existing.groups.append(FakeLayerTreeGroup("Old subgroup"))
    existing.layer_nodes.append(FakeLayerTreeLayer(FakeVectorLayer("x", "old layer", "ogr")))

    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_is_valid=True,
        src_field_names=[STATE_FIELD],
        src_unique_values=["Bayern"],
        existing_parent_group=existing,
    )

    grp = project.root.findGroup(GROUP_NAME)
    assert grp is existing
    # old children removed, then Bayern subgroup added
    assert len(grp.groups) == 1
    assert grp.groups[0].name == "Bayern"
    assert grp.layer_nodes == []


# -------------------------------------------------------------------
# Tests: helper-renderer functions
# -------------------------------------------------------------------

def test_make_white_mask_renderer_builds_inverted_polygon_renderer(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    renderer = module.make_white_mask_renderer()
    assert isinstance(renderer, FakeInvertedPolygonRenderer)
    assert isinstance(renderer.base_renderer, FakeSingleSymbolRenderer)
    assert renderer.base_renderer.symbol.props == {
        "color": "255,255,255,255",
        "outline_color": "255,255,255,0",
        "outline_width": "0",
    }


def test_make_outline_renderer_builds_transparent_fill_with_outline(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    renderer = module.make_outline_renderer()
    assert isinstance(renderer, FakeSingleSymbolRenderer)
    assert renderer.symbol.props == {
        "color": "255,255,255,0",
        "outline_color": "0,0,0,255",
        "outline_width": "0.8",
    }


# -------------------------------------------------------------------
# Tests: add_layer_under
# -------------------------------------------------------------------

def test_add_layer_under_adds_map_layer_without_root_and_inserts_tree_layer(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    grp = FakeLayerTreeGroup("Target")
    layer = FakeVectorLayer("s", "Layer", "ogr")

    project.added_layers.clear()
    grp.layer_nodes.clear()

    module.add_layer_under(grp, layer)

    assert project.added_layers == [(layer, False)]
    assert len(grp.layer_nodes) == 1
    assert isinstance(grp.layer_nodes[0], FakeLayerTreeLayer)
    assert grp.layer_nodes[0].layer is layer


# -------------------------------------------------------------------
# Tests: main behavior / created state groups
# -------------------------------------------------------------------

def test_sorts_state_names_before_creating_groups(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Thüringen", "Bayern", "Berlin"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    assert [grp.name for grp in parent.groups] == ["Bayern", "Berlin", "Thüringen"]


def test_creates_two_layers_per_state_group(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern", "Thüringen"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    assert len(parent.groups) == 2

    for state_group in parent.groups:
        assert len(state_group.layer_nodes) == 2
        names = [node.layer.name() for node in state_group.layer_nodes]
        assert any(name.endswith("– Outline") for name in names)
        assert any(name.endswith("– Mask outside") for name in names)


def test_outline_and_mask_layers_use_source_layer_source(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    state_group = parent.groups[0]
    outline = state_group.layer_nodes[1].layer
    mask = state_group.layer_nodes[0].layer

    assert outline.source() == src_path
    assert mask.source() == src_path


def test_subset_string_is_set_correctly_for_normal_name(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    state_group = parent.groups[0]
    layers = [node.layer for node in state_group.layer_nodes]

    for layer in layers:
        assert layer.subsetString() == "\"NAME_1\" = 'Bayern'"


def test_subset_string_escapes_single_quotes_in_state_name(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["O'Brien Land"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    state_group = parent.groups[0]
    layers = [node.layer for node in state_group.layer_nodes]

    for layer in layers:
        assert layer.subsetString() == "\"NAME_1\" = 'O''Brien Land'"


def test_outline_layer_gets_outline_renderer_and_mask_layer_gets_inverted_renderer(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    state_group = parent.groups[0]

    # insertChildNode(0, ...) means mask added after outline but inserted before it
    first = state_group.layer_nodes[0].layer
    second = state_group.layer_nodes[1].layer

    assert isinstance(first.renderer(), FakeInvertedPolygonRenderer)
    assert isinstance(second.renderer(), FakeSingleSymbolRenderer)
    assert second.name() == "Bayern – Outline"
    assert first.name() == "Bayern – Mask outside"


def test_only_default_visible_state_group_is_checked(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern", "Thüringen", "Berlin"],
    )

    parent = project.root.findGroup(GROUP_NAME)
    visibility = {grp.name: grp.visibility_checked for grp in parent.groups}

    assert visibility["Thüringen"] is True
    assert visibility["Bayern"] is False
    assert visibility["Berlin"] is False


def test_project_adds_two_layers_per_state(monkeypatch):
    module, project, created_layers, src_path = import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern", "Thüringen", "Berlin"],
    )

    # 2 layers per state
    assert len(project.added_layers) == 6
    assert all(add_to_root is False for _, add_to_root in project.added_layers)


# -------------------------------------------------------------------
# Tests: print output
# -------------------------------------------------------------------

def test_prints_summary_messages(monkeypatch, capsys):
    import_module_with_fakes(
        monkeypatch,
        src_unique_values=["Bayern", "Thüringen"],
    )

    captured = capsys.readouterr()
    assert "✅ Created 2 state groups under: 'DE States (masked)'." in captured.out
    assert "ℹ️ Each group contains:" in captured.out
    assert "• an outline layer to delineate the state, and" in captured.out
    assert "• a white 'inverted polygon' mask that hides everything outside the state." in captured.out
    assert "👁️ Only 'Thüringen' is visible initially. Toggle groups to switch focus." in captured.out