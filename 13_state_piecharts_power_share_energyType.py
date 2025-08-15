import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout

# 📁 Input path for GeoJSON files
GEOJSON_FOLDER = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_three_checks"

# 🗂️ Energy codes and labels
ENERGY_TYPES = {
    "2403": "Deep Geothermal",
    "2405": "Sewage Gas",
    "2406": "Pressure Relief",
    "2493": "Biogas",
    "2495": "Photovoltaics",
    "2496": "Battery",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2957": "Pressure Relief CHP",
    "2958": "Pressure Relief Small"
}
ENERGY_COLORS = {
    "Deep Geothermal": "red",
    "Sewage Gas": "purple",
    "Pressure Relief": "pink",
    "Biogas": "lightgreen",
    "Photovoltaics": "gold",
    "Battery": "gray",
    "Onshore Wind": "white",
    "Hydropower": "skyblue",
    "Pressure Relief CHP": "orange",
    "Pressure Relief Small": "orange",
    "Other": "lightgray",
    "Unknown": "black"
}

def parse_kw(value):
    try:
        return float(str(value).replace(",", "."))
    except:
        return 0.0

def load_state_power_data():
    state_power = defaultdict(lambda: defaultdict(float))

    for fname in os.listdir(GEOJSON_FOLDER):
        if not fname.endswith(".geojson"):
            continue
        fpath = os.path.join(GEOJSON_FOLDER, fname)
        state = fname.replace(".geojson", "")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for feat in data.get("features", []):
                    props = feat.get("properties", {})
                    code = str(props.get("Energietraeger", "")).strip()
                    label = ENERGY_TYPES.get(code, "Unknown")
                    kw = parse_kw(props.get("Bruttoleistung", 0))
                    state_power[state][label] += kw
        except Exception as e:
            print(f"❌ Failed {fname}: {e}")
    return state_power

def plot_pie_charts(state_data):
    tab_widget = QTabWidget()

    for state, powers in sorted(state_data.items()):
        total = sum(powers.values())
        if total == 0:
            continue

        labels = []
        values = []
        colors = []

        for label, val in powers.items():
            labels.append(f"{label} ({val/1000:.2f} MW)")
            values.append(val)
            colors.append(ENERGY_COLORS.get(label, "gray"))

        fig, ax = plt.subplots(figsize=(8, 8))
        fig.patch.set_facecolor("#f9f9f9")
        ax.set_facecolor("#f0f0f0")

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            textprops={'fontsize': 7}
        )
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8)
        ax.set_title(f"{state.upper()} - Power Share per Energy Type", fontsize=12)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)
        tab_widget.addTab(tab, state)

    dialog = QDialog()
    dialog.setWindowTitle("State-wise Power Share (Pie Charts)")
    dialog.setMinimumSize(900, 700)
    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()


    tab_widget = QTabWidget()

    for state, powers in sorted(state_data.items()):
        total = sum(powers.values())
        if total == 0:
            continue

        grouped = defaultdict(float)
        for label, val in powers.items():
            share = val / total
            if share < 0.01:
                grouped["Other"] += val
            else:
                grouped[label] += val

        labels = list(grouped.keys())
        values = list(grouped.values())
        colors = [ENERGY_COLORS.get(l, "gray") for l in labels]

        fig, ax = plt.subplots(figsize=(8, 8))
        fig.patch.set_facecolor("#f9f9f9")
        ax.set_facecolor("#f0f0f0")

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            textprops={'fontsize': 7}
        )
        ax.legend(labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8)
        ax.set_title(f"{state.upper()} - Power Share per Energy Type", fontsize=12)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)
        tab_widget.addTab(tab, state)

    dialog = QDialog()
    dialog.setWindowTitle("State-wise Power Share (Pie Charts)")
    dialog.setMinimumSize(900, 700)
    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()

# 🚀 Main
state_data = load_state_power_data()
plot_pie_charts(state_data)
