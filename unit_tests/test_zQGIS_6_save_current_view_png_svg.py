# Filename: unit_tests/test_zQGIS_6_save_current_view_png_svg.py

import builtins
import importlib
import pathlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.6_save_current_view_png_svg"


# -------------------------------------------------------------------
# Fake datetime
# -------------------------------------------------------------------

class FakeNow:
    def strftime(self, fmt):
        assert fmt == "%Y%m%d_%H%M%S"
        return "20260102_030405"


class FakeDatetime:
    @staticmethod
    def now():
        return FakeNow()


# -------------------------------------------------------------------
# Fake pathlib.Path
# -------------------------------------------------------------------

class FakePath:
    created_dirs = []

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

    def mkdir(self, parents=False, exist_ok=False):
        FakePath.created_dirs.append((self.path, parents, exist_ok))


# -------------------------------------------------------------------
# Fake Qt constants / simple geometry classes
# -------------------------------------------------------------------

class FakeQt:
    transparent = "transparent"
    white = "white"


class FakeQSize:
    def __init__(self, w, h):
        self._w = w
        self._h = h

    def width(self):
        return self._w

    def height(self):
        return self._h


class FakeQRectF:
    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


# -------------------------------------------------------------------
# Fake image / painter / svg
# -------------------------------------------------------------------

class FakeQImage:
    Format_ARGB32 = "Format_ARGB32"
    created = []

    def __init__(self, size, fmt):
        self.size = size
        self.fmt = fmt
        self.fill_color = None
        self.saved = []
        FakeQImage.created.append(self)

    def fill(self, color):
        self.fill_color = color

    def save(self, path, fmt):
        self.saved.append((path, fmt))
        return True


class FakeQPainter:
    Antialiasing = "Antialiasing"
    HighQualityAntialiasing = "HighQualityAntialiasing"
    TextAntialiasing = "TextAntialiasing"
    SmoothPixmapTransform = "SmoothPixmapTransform"

    created = []

    def __init__(self, target):
        self.target = target
        self.render_hints = []
        self.ended = False
        FakeQPainter.created.append(self)

    def setRenderHint(self, hint, value=True):
        self.render_hints.append((hint, value))

    def end(self):
        self.ended = True


class FakeQSvgGenerator:
    created = []

    def __init__(self):
        self.file_name = None
        self.size = None
        self.view_box = None
        self.title = None
        self.description = None
        FakeQSvgGenerator.created.append(self)

    def setFileName(self, value):
        self.file_name = value

    def setSize(self, value):
        self.size = value

    def setViewBox(self, value):
        self.view_box = value

    def setTitle(self, value):
        self.title = value

    def setDescription(self, value):
        self.description = value


# -------------------------------------------------------------------
# Fake map canvas / settings / iface
# -------------------------------------------------------------------

class FakeCanvasSize:
    def __init__(self, w, h):
        self._w = w
        self._h = h

    def width(self):
        return self._w

    def height(self):
        return self._h


class FakeMapSettings:
    Antialiasing = "Antialiasing"
    UseAdvancedEffects = "UseAdvancedEffects"
    DrawLabeling = "DrawLabeling"

    def __init__(self):
        self.output_size = None
        self.output_dpi = None
        self.flags = []
        self.background_color = None

    def setOutputSize(self, size):
        self.output_size = size

    def setOutputDpi(self, dpi):
        self.output_dpi = dpi

    def setFlag(self, flag, value):
        self.flags.append((flag, value))

    def setBackgroundColor(self, color):
        self.background_color = color


class FakeMapCanvas:
    def __init__(self, w=100, h=50):
        self._size = FakeCanvasSize(w, h)
        self._settings = FakeMapSettings()

    def size(self):
        return self._size

    def mapSettings(self):
        return self._settings


class FakeIface:
    def __init__(self, canvas):
        self._canvas = canvas

    def mapCanvas(self):
        return self._canvas


# -------------------------------------------------------------------
# Fake QGIS renderer job / project
# -------------------------------------------------------------------

class FakeJob:
    created = []

    def __init__(self, map_settings, painter):
        self.map_settings = map_settings
        self.painter = painter
        self.started = False
        self.finished_waited = False
        FakeJob.created.append(self)

    def start(self):
        self.started = True

    def waitForFinished(self):
        self.finished_waited = True


class FakeProject:
    @staticmethod
    def instance():
        return object()


# -------------------------------------------------------------------
# Import helper
# -------------------------------------------------------------------

def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(monkeypatch, canvas_width=100, canvas_height=50):
    clear_module()

    FakePath.created_dirs = []
    FakeQImage.created = []
    FakeQPainter.created = []
    FakeQSvgGenerator.created = []
    FakeJob.created = []

    canvas = FakeMapCanvas(canvas_width, canvas_height)
    iface = FakeIface(canvas)

    pyqt5_module = types.ModuleType("PyQt5")
    qtcore_module = types.ModuleType("PyQt5.QtCore")
    qtgui_module = types.ModuleType("PyQt5.QtGui")
    qtsvg_module = types.ModuleType("PyQt5.QtSvg")
    qgis_module = types.ModuleType("qgis")
    qgis_core_module = types.ModuleType("qgis.core")

    qtcore_module.QSize = FakeQSize
    qtcore_module.QRectF = FakeQRectF
    qtcore_module.Qt = FakeQt

    qtgui_module.QImage = FakeQImage
    qtgui_module.QPainter = FakeQPainter

    qtsvg_module.QSvgGenerator = FakeQSvgGenerator

    qgis_core_module.QgsProject = FakeProject
    qgis_core_module.QgsMapRendererCustomPainterJob = FakeJob

    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5_module)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", qtcore_module)
    monkeypatch.setitem(sys.modules, "PyQt5.QtGui", qtgui_module)
    monkeypatch.setitem(sys.modules, "PyQt5.QtSvg", qtsvg_module)
    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", qgis_core_module)

    monkeypatch.setattr(builtins, "iface", iface, raising=False)

    real_path = pathlib.Path
    pathlib.Path = FakePath
    try:
        module = importlib.import_module(MODULE_NAME)
    finally:
        pathlib.Path = real_path

    # patch datetime symbol inside imported module for deterministic direct calls too
    module.datetime = FakeDatetime
    return module, canvas


# -------------------------------------------------------------------
# Tests: safe_filename
# -------------------------------------------------------------------

def test_safe_filename_lowercases_and_replaces_invalid_chars(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    assert module.safe_filename("My File Name!!.PNG") == "my-file-name-png"


def test_safe_filename_transliterates_turkish_and_german_chars(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    assert module.safe_filename("Şİğöüç ÄÖÜ ß") == "si-gouc-aou-ss"


def test_safe_filename_collapses_multiple_separators(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    assert module.safe_filename("a---b___c") == "a-b-c"


def test_safe_filename_returns_fallback_for_empty_result(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    assert module.safe_filename("!!!") == "mapcanvas"
    assert module.safe_filename("") == "mapcanvas"
    assert module.safe_filename(None) == "mapcanvas"


# -------------------------------------------------------------------
# Tests: export_canvas
# -------------------------------------------------------------------

def test_export_canvas_creates_output_directory(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    FakePath.created_dirs.clear()
    module.export_canvas("demo")

    assert FakePath.created_dirs[-1] == (
        r"C:\Users\jo73vure\Desktop\powerPlantProject\exports",
        True,
        True,
    )


def test_export_canvas_builds_timestamped_png_and_svg_paths(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    FakeQImage.created.clear()
    FakeQSvgGenerator.created.clear()

    module.export_canvas("demo")

    img = FakeQImage.created[-1]
    svg = FakeQSvgGenerator.created[-1]

    assert img.saved[-1][0].endswith(r"exports\demo__20260102_030405.png")
    assert img.saved[-1][1] == "PNG"
    assert svg.file_name.endswith(r"exports\demo__20260102_030405.svg")
    assert svg.title == "demo__20260102_030405"


def test_export_canvas_scales_canvas_size_for_output(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch, canvas_width=120, canvas_height=80)

    module.export_canvas("demo")

    settings = canvas.mapSettings()
    assert settings.output_size.width() == 1200
    assert settings.output_size.height() == 800


def test_export_canvas_sets_dpi_and_map_settings_flags(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    module.export_canvas("demo")

    settings = canvas.mapSettings()
    assert settings.output_dpi == 1000
    assert (settings.Antialiasing, True) in settings.flags
    assert (settings.UseAdvancedEffects, True) in settings.flags
    assert (settings.DrawLabeling, True) in settings.flags


def test_export_canvas_sets_white_background_when_transparency_disabled(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)
    module.PNG_TRANSPARENT_BG = False

    module.export_canvas("demo")

    settings = canvas.mapSettings()
    img = FakeQImage.created[-1]
    assert settings.background_color == FakeQt.white
    assert img.fill_color == FakeQt.white


def test_export_canvas_sets_transparent_background_when_enabled(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)
    module.PNG_TRANSPARENT_BG = True

    module.export_canvas("demo")

    settings = canvas.mapSettings()
    img = FakeQImage.created[-1]
    assert settings.background_color == FakeQt.transparent
    assert img.fill_color == FakeQt.transparent


def test_export_canvas_creates_png_painter_with_expected_render_hints(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    module.export_canvas("demo")

    painter = FakeQPainter.created[-2]  # PNG painter
    assert (FakeQPainter.Antialiasing, True) in painter.render_hints
    assert (FakeQPainter.HighQualityAntialiasing, True) in painter.render_hints
    assert (FakeQPainter.TextAntialiasing, True) in painter.render_hints
    assert (FakeQPainter.SmoothPixmapTransform, True) in painter.render_hints
    assert painter.ended is True


def test_export_canvas_creates_svg_generator_and_svg_painter(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    module.export_canvas("demo")

    svg = FakeQSvgGenerator.created[-1]
    painter = FakeQPainter.created[-1]  # SVG painter

    assert svg.size.width() == 1000
    assert svg.size.height() == 500
    assert isinstance(svg.view_box, FakeQRectF)
    assert svg.description == "Exported from QGIS map canvas (ULTRA HQ)"
    assert (FakeQPainter.Antialiasing, True) in painter.render_hints
    assert (FakeQPainter.HighQualityAntialiasing, True) in painter.render_hints
    assert painter.ended is True


def test_export_canvas_runs_two_render_jobs_and_waits_for_both(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    module.export_canvas("demo")

    assert len(FakeJob.created) >= 2
    png_job = FakeJob.created[-2]
    svg_job = FakeJob.created[-1]

    assert png_job.started is True
    assert png_job.finished_waited is True
    assert svg_job.started is True
    assert svg_job.finished_waited is True


def test_export_canvas_prints_output_paths_and_finished(monkeypatch, capsys):
    module, canvas = import_module_with_fakes(monkeypatch)

    module.export_canvas("demo")

    captured = capsys.readouterr()
    assert "[OK] PNG ->" in captured.out
    assert "[OK] SVG ->" in captured.out
    assert "Finished." in captured.out


# -------------------------------------------------------------------
# Tests: import-time main flow
# -------------------------------------------------------------------

def test_import_prints_safe_filename_info_and_exports(monkeypatch, capsys):
    import_module_with_fakes(monkeypatch)

    captured = capsys.readouterr()
    assert "[INFO] Using base filename: maStr_pieChart -> safe stem: mastr-piechart" in captured.out
    assert "[OK] PNG ->" in captured.out
    assert "[OK] SVG ->" in captured.out


def test_import_uses_safe_filename_on_base_filename(monkeypatch):
    module, canvas = import_module_with_fakes(monkeypatch)

    img = FakeQImage.created[0]
    saved_path = img.saved[0][0]

    assert r"exports\mastr-piechart__" in saved_path
    assert saved_path.endswith(".png")