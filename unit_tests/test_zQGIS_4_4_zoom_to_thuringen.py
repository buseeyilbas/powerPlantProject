# Filename: unit_tests/test_zQGIS_4_4_zoom_to_thuringen.py

import builtins
import importlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.4_4_zoom_to_thuringen"


# -------------------------------------------------------------------
# Fake QGIS classes
# -------------------------------------------------------------------

class FakeRectangle:
    def __init__(self, xmin, ymin, xmax, ymax):
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax


class FakeCRS:
    def __init__(self, authid):
        self.authid = authid


class FakeTransform:
    def __init__(self, source_crs, target_crs, project):
        self.source_crs = source_crs
        self.target_crs = target_crs
        self.project = project
        self.transform_calls = []
        self.result_extent = None

    def transformBoundingBox(self, rect):
        self.transform_calls.append(rect)
        return self.result_extent


class FakeProject:
    def __init__(self, crs):
        self._crs = crs

    def crs(self):
        return self._crs


class FakeMapCanvas:
    def __init__(self):
        self.extents = []
        self.refresh_called = False

    def setExtent(self, extent):
        self.extents.append(extent)

    def refresh(self):
        self.refresh_called = True


class FakeIface:
    def __init__(self, canvas):
        self._canvas = canvas

    def mapCanvas(self):
        return self._canvas


# -------------------------------------------------------------------
# Import helper
# -------------------------------------------------------------------

def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(monkeypatch):
    clear_module()

    target_crs = FakeCRS("EPSG:3857")
    project = FakeProject(target_crs)
    canvas = FakeMapCanvas()
    iface = FakeIface(canvas)

    created_rectangles = []
    created_crs = []
    created_transforms = []

    qgis_module = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")

    class FakeQgsProject:
        @staticmethod
        def instance():
            return project

    def fake_rectangle(xmin, ymin, xmax, ymax):
        rect = FakeRectangle(xmin, ymin, xmax, ymax)
        created_rectangles.append(rect)
        return rect

    def fake_crs(authid):
        crs = FakeCRS(authid)
        created_crs.append(crs)
        return crs

    def fake_transform(source_crs, target_crs_arg, project_arg):
        transform = FakeTransform(source_crs, target_crs_arg, project_arg)
        transformed_extent = FakeRectangle(100, 200, 300, 400)
        transform.result_extent = transformed_extent
        created_transforms.append(transform)
        return transform

    qgis_core.QgsRectangle = fake_rectangle
    qgis_core.QgsCoordinateReferenceSystem = fake_crs
    qgis_core.QgsCoordinateTransform = fake_transform
    qgis_core.QgsProject = FakeQgsProject

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core)
    monkeypatch.setattr(builtins, "iface", iface, raising=False)

    module = importlib.import_module(MODULE_NAME)
    return module, project, canvas, created_rectangles, created_crs, created_transforms


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------





def test_creates_source_crs_as_epsg_4326(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    assert len(created_crs) >= 1
    assert created_crs[0].authid == "EPSG:4326"


def test_reads_target_crs_from_project_instance(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    transform = created_transforms[0]
    assert transform.target_crs is project.crs()


def test_creates_coordinate_transform_with_expected_arguments(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    assert len(created_transforms) == 1
    transform = created_transforms[0]

    assert transform.source_crs.authid == "EPSG:4326"
    assert transform.target_crs is project.crs()
    assert transform.project is project


def test_transforms_bounding_box_of_final_extent(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    transform = created_transforms[0]
    final_source_extent = created_rectangles[0]

    assert transform.transform_calls == [final_source_extent]


def test_sets_canvas_extent_to_transformed_extent(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    transform = created_transforms[0]
    assert canvas.extents == [transform.result_extent]


def test_refreshes_map_canvas_after_setting_extent(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    assert canvas.refresh_called is True


def test_prints_zoom_success_message(monkeypatch, capsys):
    import_module_with_fakes(monkeypatch)

    captured = capsys.readouterr()
    assert "🔍 Zoomed to Thüringen." in captured.out

def test_creates_one_rectangle_with_one_of_supported_thueringen_extents(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    assert len(created_rectangles) == 1

    source_extent = created_rectangles[0]
    transform = created_transforms[0]

    extent_tuple = (
        source_extent.xmin,
        source_extent.ymin,
        source_extent.xmax,
        source_extent.ymax,
    )

    supported_extents = {
        (8.9, 50.2, 12.5, 51.8),
        (9.4, 50.0, 13.55, 52.05),
    }

    assert extent_tuple in supported_extents
    assert transform.transform_calls == [source_extent]

def test_effective_extent_is_one_of_supported_thueringen_extents(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    effective_extent = created_rectangles[0]

    extent_tuple = (
        effective_extent.xmin,
        effective_extent.ymin,
        effective_extent.xmax,
        effective_extent.ymax,
    )

    assert extent_tuple in {
        (8.9, 50.2, 12.5, 51.8),
        (9.4, 50.0, 13.55, 52.05),
    }

def test_transforms_bounding_box_of_active_extent(monkeypatch):
    module, project, canvas, created_rectangles, created_crs, created_transforms = import_module_with_fakes(
        monkeypatch
    )

    transform = created_transforms[0]
    active_source_extent = created_rectangles[0]

    assert transform.transform_calls == [active_source_extent]