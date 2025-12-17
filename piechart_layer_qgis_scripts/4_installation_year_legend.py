# QGIS Popup: Installation Year Legend (EEG-based)
# Paste into QGIS Python Console and run.

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QApplication
)
from qgis.PyQt.QtGui import QFont, QGuiApplication, QColor, QPalette
from qgis.PyQt.QtCore import Qt

# ---- data --------------------------------------------------------------
PHASES = [
    {"range":"≤1990",     "name":"Pre-EEG (pre-support era)",
     "desc":"Pre-EEG era (before the Renewable Energy Sources Act).",
     "short":"Pre-EEG"},
    {"range":"1991–1999", "name":"Post-reunification",
     "desc":"Early build-up after German reunification.",
     "short":"Post-reunif."},
    {"range":"2000–2003", "name":"EEG launch & early ramp-up",
     "desc":"Start of the Renewable Energy Sources Act (EEG) and first acceleration.",
     "short":"EEG launch"},
    {"range":"2004–2011", "name":"EEG expansion phase",
     "desc":"Strong growth under extended EEG incentives.",
     "short":"Expansion"},
    {"range":"2012–2016", "name":"EEG 2012 reform period",
     "desc":"Market adjustments following the 2012 EEG amendments.",
     "short":"2012 reform"},
    {"range":"2017–2020", "name":"Auction transition",
     "desc":"Shift to tender/auction-based support mechanisms.",
     "short":"Auction transition"},
    {"range":"2021–2025", "name":"Recent years",
     "desc":"Latest phase.",
     "short":"Recent"},
]

# Optional soft colors for chips (purely visual)
COLORS = ["#6B7280","#4B5563","#2563EB","#22C55E","#F59E0B","#A855F7","#EF4444"]

def make_chip(color_hex):
    box = QLabel("  ")
    box.setFixedSize(16,16)
    box.setStyleSheet(f"background:{color_hex}; border-radius:3px; border:1px solid rgba(0,0,0,0.25);")
    return box

def build_rows(container, compact=False):
    # clear
    for i in reversed(range(container.layout().count())):
        w = container.layout().itemAt(i).widget()
        if w:
            w.setParent(None)

    title = QLabel("Installation Year Legend (Germany, EEG context)")
    title.setFont(QFont("", 11, QFont.DemiBold))
    container.layout().addWidget(title)

    note = QLabel('“EEG” = Renewable Energy Sources Act (German: Erneuerbare-Energien-Gesetz).')
    note.setWordWrap(True)
    note.setStyleSheet("color:#60646c;")
    container.layout().addWidget(note)

    for idx, p in enumerate(PHASES):
        row = QWidget()
        h = QHBoxLayout(row); h.setContentsMargins(0,6,0,6); h.setSpacing(10)
        h.addWidget(make_chip(COLORS[idx % len(COLORS)]))
        rng = QLabel(f"<b>{p['range']}</b>")
        rng.setFixedWidth(70)
        h.addWidget(rng)

        if compact:
            main = QLabel(p["short"])
        else:
            main = QLabel(f"<b>{p['name']}</b><br><span style='color:#60646c'>{p['desc']}</span>")
        main.setWordWrap(True)
        h.addWidget(main, 1)
        container.layout().addWidget(row)

def to_markdown(compact=False):
    if compact:
        rows = ["| Year Range | Phase |",
                "|---|---|"]
        for p in PHASES:
            rows.append(f"| {p['range']} | {p['short']} |")
        return "\n".join(rows)
    else:
        rows = ["| Year Range | Phase | Description |",
                "|---|---|---|"]
        for p in PHASES:
            rows.append(f"| {p['range']} | {p['name']} | {p['desc']} |")
        return "\n".join(rows)

class LegendDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Year Legend – Germany (EEG)")
        self.resize(640, 420)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        v = QVBoxLayout(self); v.setContentsMargins(12,12,12,12); v.setSpacing(10)

        # Controls
        top = QHBoxLayout(); top.setSpacing(12)
        self.cb_compact = QCheckBox("Short legend labels")
        self.cb_compact.stateChanged.connect(self.refresh)
        top.addWidget(self.cb_compact)
        top.addStretch(1)

        btn_copy = QPushButton("Copy as Markdown")
        btn_copy.clicked.connect(self.copy_md)
        top.addWidget(btn_copy)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        top.addWidget(btn_close)

        v.addLayout(top)

        # Scroll area for content
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body.setLayout(QVBoxLayout()); self.body.layout().setContentsMargins(6,6,6,6)
        self.scroll.setWidget(self.body)
        v.addWidget(self.scroll, 1)

        self.refresh()

    def refresh(self):
        compact = self.cb_compact.isChecked()
        build_rows(self.body, compact)

    def copy_md(self):
        compact = self.cb_compact.isChecked()
        QGuiApplication.clipboard().setText(to_markdown(compact))

# Run dialog
dlg = LegendDialog()
dlg.exec_()
