# Filename: unit_tests/test_zQGIS_5_installation_year_legend.py

import importlib
import sys
import types

import pytest


MODULE_NAME = "piechart_layer_qgis_scripts.5_installation_year_legend"


# -------------------------------------------------------------------
# Fake Qt constants
# -------------------------------------------------------------------

class FakeQt:
    WindowStaysOnTopHint = "WindowStaysOnTopHint"


# -------------------------------------------------------------------
# Fake clipboard / app
# -------------------------------------------------------------------

class FakeClipboard:
    def __init__(self):
        self.text_value = None

    def setText(self, text):
        self.text_value = text


class FakeQGuiApplication:
    _clipboard = FakeClipboard()

    @staticmethod
    def clipboard():
        return FakeQGuiApplication._clipboard


# -------------------------------------------------------------------
# Fake signal
# -------------------------------------------------------------------

class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in self.callbacks:
            try:
                callback(*args, **kwargs)
            except TypeError:
                callback()


# -------------------------------------------------------------------
# Fake font / palette / color
# -------------------------------------------------------------------

class FakeQFont:
    DemiBold = "DemiBold"

    def __init__(self, family="", size=None, weight=None):
        self.family = family
        self.size = size
        self.weight = weight


class FakeQColor:
    def __init__(self, *args, **kwargs):
        self.args = args


class FakeQPalette:
    pass


# -------------------------------------------------------------------
# Fake layout item wrapper
# -------------------------------------------------------------------

class FakeLayoutItem:
    def __init__(self, widget=None, layout=None):
        self._widget = widget
        self._layout = layout

    def widget(self):
        return self._widget

    def layout(self):
        return self._layout


# -------------------------------------------------------------------
# Fake layouts
# -------------------------------------------------------------------

class FakeVBoxLayout:
    def __init__(self, parent=None):
        self.parent = parent
        self.items = []
        self.contents_margins = None
        self.spacing = None
        if parent is not None:
            parent._layout = self

    def setContentsMargins(self, a, b, c, d):
        self.contents_margins = (a, b, c, d)

    def setSpacing(self, value):
        self.spacing = value

    def addWidget(self, widget, stretch=None):
        self.items.append(FakeLayoutItem(widget=widget))

    def addLayout(self, layout, stretch=None):
        self.items.append(FakeLayoutItem(layout=layout))

    def addStretch(self, stretch=0):
        self.items.append(FakeLayoutItem())

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index]


class FakeHBoxLayout(FakeVBoxLayout):
    pass


# -------------------------------------------------------------------
# Fake widgets
# -------------------------------------------------------------------

class FakeWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self._layout = None
        self.deleted = False

    def setLayout(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout

    def setParent(self, parent):
        self.parent = parent
        if parent is None:
            self.deleted = True


class FakeLabel(FakeWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.text = text
        self.word_wrap = False
        self.font = None
        self.fixed_width = None
        self.fixed_size = None
        self.stylesheet = None

    def setWordWrap(self, value):
        self.word_wrap = value

    def setFont(self, font):
        self.font = font

    def setFixedWidth(self, value):
        self.fixed_width = value

    def setFixedSize(self, w, h):
        self.fixed_size = (w, h)

    def setStyleSheet(self, style):
        self.stylesheet = style


class FakePushButton(FakeWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.text = text
        self.clicked = FakeSignal()


class FakeCheckBox(FakeWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.text = text
        self._checked = False
        self.stateChanged = FakeSignal()

    def isChecked(self):
        return self._checked

    def setChecked(self, value):
        self._checked = bool(value)
        self.stateChanged.emit(value)


class FakeScrollArea(FakeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget_resizable = None
        self.widget_obj = None

    def setWidgetResizable(self, value):
        self.widget_resizable = value

    def setWidget(self, widget):
        self.widget_obj = widget


class FakeDialog(FakeWidget):
    last_instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.window_title = None
        self.size = None
        self.window_flags = []
        self.closed = False
        self.exec_called = False
        FakeDialog.last_instance = self

    def setWindowTitle(self, title):
        self.window_title = title

    def resize(self, w, h):
        self.size = (w, h)

    def setWindowFlag(self, flag, enabled=True):
        self.window_flags.append((flag, enabled))

    def close(self):
        self.closed = True

    def exec_(self):
        self.exec_called = True
        return 0


class FakeApplication:
    pass


# -------------------------------------------------------------------
# Import helper
# -------------------------------------------------------------------

def clear_module():
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def import_module_with_fakes(monkeypatch):
    clear_module()

    FakeDialog.last_instance = None
    FakeQGuiApplication._clipboard = FakeClipboard()

    qgis_module = types.ModuleType("qgis")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")
    qtgui = types.ModuleType("qgis.PyQt.QtGui")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")

    qtwidgets.QDialog = FakeDialog
    qtwidgets.QVBoxLayout = FakeVBoxLayout
    qtwidgets.QHBoxLayout = FakeHBoxLayout
    qtwidgets.QLabel = FakeLabel
    qtwidgets.QPushButton = FakePushButton
    qtwidgets.QCheckBox = FakeCheckBox
    qtwidgets.QScrollArea = FakeScrollArea
    qtwidgets.QWidget = FakeWidget
    qtwidgets.QApplication = FakeApplication

    qtgui.QFont = FakeQFont
    qtgui.QGuiApplication = FakeQGuiApplication
    qtgui.QColor = FakeQColor
    qtgui.QPalette = FakeQPalette

    qtcore.Qt = FakeQt

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", qgis_pyqt)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtCore", qtcore)

    module = importlib.import_module(MODULE_NAME)
    return module


# -------------------------------------------------------------------
# Utility helpers for tests
# -------------------------------------------------------------------

def layout_widgets(layout):
    result = []
    for item in layout.items:
        w = item.widget()
        if w is not None and not getattr(w, "deleted", False):
            result.append(w)
    return result


# -------------------------------------------------------------------
# Tests: static data
# -------------------------------------------------------------------

def test_phases_and_colors_lengths_match_expected(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    assert len(module.PHASES) == 7
    assert len(module.COLORS) == 7


def test_phases_have_required_keys(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    for phase in module.PHASES:
        assert set(phase.keys()) == {"range", "name", "desc", "short"}


# -------------------------------------------------------------------
# Tests: make_chip
# -------------------------------------------------------------------

def test_make_chip_creates_label_with_expected_visual_properties(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    chip = module.make_chip("#123456")

    assert isinstance(chip, FakeLabel)
    assert chip.text == "  "
    assert chip.fixed_size == (16, 16)
    assert "background:#123456" in chip.stylesheet
    assert "border-radius:3px" in chip.stylesheet


# -------------------------------------------------------------------
# Tests: to_markdown
# -------------------------------------------------------------------

def test_to_markdown_full_contains_header_and_descriptions(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    md = module.to_markdown(compact=False)

    assert "| Year Range | Phase | Description |" in md
    assert "| ≤1990 | Pre-EEG (pre-support era) | Pre-EEG era (before the Renewable Energy Sources Act). |" in md
    assert "| 2021–2025 | Recent years | Latest phase. |" in md


def test_to_markdown_compact_contains_short_labels_only(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    md = module.to_markdown(compact=True)

    assert "| Year Range | Phase |" in md
    assert "| ≤1990 | Pre-EEG |" in md
    assert "| 2004–2011 | Expansion |" in md
    assert "Description" not in md


# -------------------------------------------------------------------
# Tests: build_rows
# -------------------------------------------------------------------

def test_build_rows_adds_title_note_and_phase_rows_in_full_mode(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    container = FakeWidget()
    container.setLayout(FakeVBoxLayout())

    module.build_rows(container, compact=False)

    widgets = layout_widgets(container.layout())
    assert len(widgets) == 2 + len(module.PHASES)

    title = widgets[0]
    note = widgets[1]

    assert isinstance(title, FakeLabel)
    assert title.text == "Installation Year Legend (Germany, EEG context)"
    assert isinstance(title.font, FakeQFont)
    assert title.font.size == 11
    assert title.font.weight == FakeQFont.DemiBold

    assert isinstance(note, FakeLabel)
    assert "Renewable Energy Sources Act" in note.text
    assert note.word_wrap is True


def test_build_rows_adds_short_labels_in_compact_mode(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    container = FakeWidget()
    container.setLayout(FakeVBoxLayout())

    module.build_rows(container, compact=True)

    widgets = layout_widgets(container.layout())
    first_phase_row = widgets[2]
    row_layout = first_phase_row.layout()
    row_widgets = layout_widgets(row_layout)

    main_label = row_widgets[2]
    assert main_label.text == module.PHASES[0]["short"]


def test_build_rows_replaces_existing_widgets_when_recalled(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    container = FakeWidget()
    container.setLayout(FakeVBoxLayout())

    old_widget = FakeLabel("old")
    container.layout().addWidget(old_widget)

    module.build_rows(container, compact=False)

    assert old_widget.deleted is True
    widgets = layout_widgets(container.layout())
    assert widgets[0].text == "Installation Year Legend (Germany, EEG context)"


def test_build_rows_sets_range_label_width(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    container = FakeWidget()
    container.setLayout(FakeVBoxLayout())

    module.build_rows(container, compact=False)

    first_phase_row = layout_widgets(container.layout())[2]
    row_widgets = layout_widgets(first_phase_row.layout())
    range_label = row_widgets[1]

    assert range_label.fixed_width == 70
    assert "<b>" in range_label.text


# -------------------------------------------------------------------
# Tests: LegendDialog UI setup
# -------------------------------------------------------------------

def test_dialog_is_created_and_exec_called_on_import(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    assert dlg is not None
    assert dlg.exec_called is True


def test_dialog_window_title_size_and_flag(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    assert dlg.window_title == "Year Legend – Germany (EEG)"
    assert dlg.size == (640, 420)
    assert (FakeQt.WindowStaysOnTopHint, True) in dlg.window_flags


def test_dialog_has_checkbox_and_buttons(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    top_layout = dlg.layout().items[0].layout()

    widgets = []
    for item in top_layout.items:
        w = item.widget()
        if w is not None:
            widgets.append(w)

    assert any(isinstance(w, FakeCheckBox) and w.text == "Short legend labels" for w in widgets)
    assert any(isinstance(w, FakePushButton) and w.text == "Copy as Markdown" for w in widgets)
    assert any(isinstance(w, FakePushButton) and w.text == "Close" for w in widgets)


def test_dialog_initial_refresh_populates_body(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    body_widgets = layout_widgets(dlg.body.layout())

    assert len(body_widgets) == 2 + len(module.PHASES)
    assert body_widgets[0].text == "Installation Year Legend (Germany, EEG context)"


# -------------------------------------------------------------------
# Tests: LegendDialog behavior
# -------------------------------------------------------------------

def test_refresh_switches_between_full_and_compact(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance

    # initial full mode
    first_phase_row = layout_widgets(dlg.body.layout())[2]
    main_label_full = layout_widgets(first_phase_row.layout())[2]
    assert module.PHASES[0]["name"] in main_label_full.text

    dlg.cb_compact.setChecked(True)

    first_phase_row = layout_widgets(dlg.body.layout())[2]
    main_label_compact = layout_widgets(first_phase_row.layout())[2]
    assert main_label_compact.text == module.PHASES[0]["short"]


def test_copy_md_uses_full_markdown_when_checkbox_unchecked(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    dlg.cb_compact._checked = False

    dlg.copy_md()

    copied = FakeQGuiApplication.clipboard().text_value
    assert "| Year Range | Phase | Description |" in copied
    assert "Description" in copied


def test_copy_md_uses_compact_markdown_when_checkbox_checked(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    dlg.cb_compact._checked = True

    dlg.copy_md()

    copied = FakeQGuiApplication.clipboard().text_value
    assert "| Year Range | Phase |" in copied
    assert "Description" not in copied


def test_close_button_is_connected_to_dialog_close(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    top_layout = dlg.layout().items[0].layout()

    close_button = None
    for item in top_layout.items:
        w = item.widget()
        if isinstance(w, FakePushButton) and w.text == "Close":
            close_button = w
            break

    assert close_button is not None
    close_button.clicked.emit()

    assert dlg.closed is True


def test_copy_button_is_connected_and_writes_clipboard(monkeypatch):
    module = import_module_with_fakes(monkeypatch)

    dlg = FakeDialog.last_instance
    top_layout = dlg.layout().items[0].layout()

    copy_button = None
    for item in top_layout.items:
        w = item.widget()
        if isinstance(w, FakePushButton) and w.text == "Copy as Markdown":
            copy_button = w
            break

    assert copy_button is not None
    copy_button.clicked.emit()

    copied = FakeQGuiApplication.clipboard().text_value
    assert copied is not None
    assert copied.startswith("| Year Range |")