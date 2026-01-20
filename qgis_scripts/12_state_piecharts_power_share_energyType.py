# Filename: 12_state_piecharts_power_share_energyType.py
# Purpose: Per-state pie charts using supervisor-approved 5 groups + "Others" with fixed colors.

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout

GEOJSON_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_three_checks"

# --- Supervisor-approved grouping & colors ---
PRIMARY_TYPES = {  # keep these five as distinct slices
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
OTHERS_CODES = {"2403", "2405", "2406", "2957", "2958"}  # fold into "Others"

GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    if code in PRIMARY_TYPES:
        return PRIMARY_TYPES[code]
    return "Others"  # includes OTHERS_CODES and any unexpected code

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0

def load_state_power_data():
    """Return dict[state][group] = kW."""
    state_power = defaultdict(lambda: defaultdict(float))

    for fname in os.listdir(GEOJSON_FOLDER):
        if not fname.endswith(".geojson"):
            continue

        fpath = os.path.join(GEOJSON_FOLDER, fname)
        state = os.path.splitext(fname)[0]

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Failed {fname}: {e}")
            continue

        for feat in data.get("features", []):
            props = feat.get("properties", {})
            code = str(props.get("Energietraeger", "")).strip()
            kw = parse_kw(props.get("Bruttoleistung", 0))
            group = map_code_to_group(code)
            state_power[state][group] += kw

    return state_power

def plot_pie_charts(state_data):
    """One tab per state; grouped into 5 + Others with fixed color palette."""
    tab_widget = QTabWidget()

    for state, powers in sorted(state_data.items()):
        total = sum(powers.values())
        if total <= 0:
            continue

        # Build arrays in a fixed, supervisor-approved order and skip empty ones
        labels = [g for g in GROUP_ORDER if powers.get(g, 0.0) > 0]
        values = [powers[g] for g in labels]
        colors = [GROUP_COLORS[g] for g in labels]

        tot = sum(values)
        legend_labels = [
            f"{g} ({powers[g]/1000:.2f} MW; {(powers[g]/tot*100 if tot > 0 else 0):.1f}%)"
            for g in labels
        ]


        fig, ax = plt.subplots(figsize=(12, 12))
        
        wedges, _texts = ax.pie(
            values,
            labels=None,
            startangle=140,
            colors=colors,
            textprops={"fontsize": 8}
        )

        
        ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)
        ax.set_title(f"{state.upper()} — Power Share by Energy Type", fontsize=12)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)
        tab_widget.addTab(tab, state)

    dialog = QDialog()
    dialog.setWindowTitle("State-wise Power Share (Grouped Pie Charts)")
    dialog.setMinimumSize(900, 700)
    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()

# Run
state_data = load_state_power_data()
plot_pie_charts(state_data)
