# Filename: unit_tests/test_zQGIS_8_color_legend.py

import importlib
import math
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.8_color_legend"


# -------------------------------------------------------------------
# Fake QColor
# -------------------------------------------------------------------

class FakeQColor:
    def __init__(self, r, g, b, a=255):
        self._r = r
        self._g = g
        self._b = b
        self._a = a

    def redF(self):
        return self._r / 255.0

    def greenF(self):
        return self._g / 255.0

    def blueF(self):
        return self._b / 255.0

    def alphaF(self):
        return self._a / 255.0

    def red(self):
        return self._r

    def green(self):
        return self._g

    def blue(self):
        return self._b

    def alpha(self):
        return self._a


# -------------------------------------------------------------------
# Fake matplotlib objects
# -------------------------------------------------------------------

class FakeAxes:
    def __init__(self):
        self.axis_calls = []
        self.scatter_calls = []
        self.text_calls = []
        self.xlim = None
        self.ylim = None

    def axis(self, value):
        self.axis_calls.append(value)

    def scatter(self, x, y, color=None, s=None, edgecolor=None):
        self.scatter_calls.append(
            {
                "x": x,
                "y": y,
                "color": color,
                "s": s,
                "edgecolor": edgecolor,
            }
        )

    def text(self, x, y, text, fontsize=None, va=None, ha=None):
        self.text_calls.append(
            {
                "x": x,
                "y": y,
                "text": text,
                "fontsize": fontsize,
                "va": va,
                "ha": ha,
            }
        )

    def set_xlim(self, xmin, xmax):
        self.xlim = (xmin, xmax)

    def set_ylim(self, ymin, ymax):
        self.ylim = (ymin, ymax)


class FakeFigure:
    def __init__(self):
        self.subplots_adjust_calls = []

    def subplots_adjust(self, **kwargs):
        self.subplots_adjust_calls.append(kwargs)


class FakePyplotModule(types.ModuleType):
    def __init__(self):
        super().__init__("matplotlib.pyplot")
        self.subplots_calls = []
        self.show_called = False
        self.figure = FakeFigure()
        self.axes = FakeAxes()

    def subplots(self, figsize=None):
        self.subplots_calls.append({"figsize": figsize})
        return self.figure, self.axes

    def show(self):
        self.show_called = True


# -------------------------------------------------------------------
# Import helper
# -------------------------------------------------------------------

def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(monkeypatch):
    clear_module()

    matplotlib_module = types.ModuleType("matplotlib")
    pyplot_module = FakePyplotModule()

    qgis_module = types.ModuleType("qgis")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qgis_qtgui = types.ModuleType("qgis.PyQt.QtGui")
    qgis_qtgui.QColor = FakeQColor

    monkeypatch.setitem(sys.modules, "matplotlib", matplotlib_module)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", pyplot_module)
    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qgis_qtgui)

    module = importlib.import_module(MODULE_NAME)
    return module, pyplot_module


# -------------------------------------------------------------------
# Tests: palette / helper
# -------------------------------------------------------------------

def test_palette_contains_expected_keys(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert list(module.PALETTE.keys()) == [
        "pv_kw",
        "battery_kw",
        "wind_kw",
        "hydro_kw",
        "biogas_kw",
        "others_kw",
    ]


def test_qcolor_to_rgba_converts_to_normalized_tuple(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    color = FakeQColor(255, 128, 0, 64)
    rgba = module.qcolor_to_rgba(color)

    assert rgba == (1.0, 128 / 255.0, 0.0, 64 / 255.0)


def test_energy_types_have_expected_order_and_labels(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    labels = [label for _, label in module.energy_types]
    assert labels == [
        "Photovoltaics - (Photovoltaik)",
        "Onshore Wind Energy - (Windenergie an Land)",
        "Hydropower - (Wasserkraft)",
        "Biogas - (Biogas)",
        "Battery Storage - (Stromspeicher)",
        "Others - (Andere)",
    ]


# -------------------------------------------------------------------
# Tests: matplotlib setup
# -------------------------------------------------------------------

def test_creates_figure_with_expected_size(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert plt.subplots_calls == [{"figsize": (5, 5)}]


def test_turns_axis_off(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert plt.axes.axis_calls == ["off"]


def test_adds_one_scatter_per_energy_type(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert len(plt.axes.scatter_calls) == len(module.energy_types)


def test_scatter_calls_use_expected_positions_and_style(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    expected_y_values = [1.0, 0.95, 0.90, 0.85, 0.80, 0.75]
    calls = plt.axes.scatter_calls

    for idx, call in enumerate(calls):
        assert call["x"] == 0.06
        assert math.isclose(call["y"], expected_y_values[idx], rel_tol=0, abs_tol=1e-9)
        assert call["s"] == 90
        assert call["edgecolor"] == "black"


def test_scatter_colors_match_qcolor_to_rgba(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    for (qcolor, _label), call in zip(module.energy_types, plt.axes.scatter_calls):
        assert call["color"] == module.qcolor_to_rgba(qcolor)


def test_adds_text_for_each_energy_type(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    energy_texts = plt.axes.text_calls[:len(module.energy_types)]
    labels = [entry["text"] for entry in energy_texts]

    assert labels == [label for _, label in module.energy_types]

    for entry in energy_texts:
        assert entry["x"] == 0.1
        assert entry["fontsize"] == 10
        assert entry["va"] == "center"
        assert entry["ha"] == "left"


def test_adds_note_line_after_energy_types(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    note_entry = plt.axes.text_calls[-1]
    assert note_entry["text"] == "*Symbol size proportional to power capacity"
    assert note_entry["x"] == 0.1
    assert note_entry["fontsize"] == 8
    assert note_entry["ha"] == "left"


def test_sets_expected_axis_limits(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert plt.axes.xlim == (0, 1)
    assert plt.axes.ylim == (0, 1.1)


def test_adjusts_subplot_margins(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert plt.figure.subplots_adjust_calls == [
        {
            "left": 0.1,
            "right": 0.95,
            "top": 0.95,
            "bottom": 0.05,
        }
    ]


def test_calls_show_at_end(monkeypatch):
    module, plt = import_module_with_fakes(monkeypatch)

    assert plt.show_called is True