# Filename: 8_states_energytype_counts_yearly.py
# Purpose: Yearly plant COUNTS per state, grouped into 5 main energy types + "Others", with fixed colors.

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout
from qgis.utils import iface

BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_yearly_three_checks"

# --- Supervisor-approved grouping (codes -> 5 main groups, everything else -> Others) ---
PRIMARY_TYPES = {
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
}
# These known extra codes (and any unknown code) will be folded into "Others"
OTHERS_CODES = {"2403", "2405", "2406", "2957", "2958"}

GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# --- Fixed color palette (legend & charts) ---
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def map_code_to_group(code: str) -> str:
    """Return one of the 5 main groups, otherwise 'Others'."""
    if code in PRIMARY_TYPES:
        return PRIMARY_TYPES[code]
    return "Others"

# --- Parse helper ---
def parse_energy_group(feature) -> str:
    props = feature.get("properties", {})
    code = str(props.get("Energietraeger", "")).strip()
    return map_code_to_group(code)

# --- Data collector: state → year → group → count ---
def process_geojson_files():
    result = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for state_name in os.listdir(BASE_DIR):
        state_path = os.path.join(BASE_DIR, state_name)
        if not os.path.isdir(state_path):
            continue

        for file in os.listdir(state_path):
            if not file.endswith(".geojson") or file == "unknown.geojson":
                continue

            try:
                year = int(file.replace(".geojson", ""))
            except ValueError:
                continue

            file_path = os.path.join(state_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    geo = json.load(f)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            for feature in geo.get("features", []):
                grp = parse_energy_group(feature)
                result[state_name][year][grp] += 1

    return result

# --- Plot with toolbar and tabs ---
def plot_counts_tabbed(aggregated_data):
    tab_widget = QTabWidget()

    for state, year_data in sorted(aggregated_data.items()):
        all_years = sorted(year_data.keys())

        # Build stacked series only for groups that appear at least once
        stacked_data = {
            g: [year_data[y].get(g, 0) for y in all_years]
            for g in GROUP_ORDER
            if any(year_data[y].get(g, 0) > 0 for y in all_years)
        }

        fig, ax = plt.subplots(figsize=(10, 6))
        bottom = [0] * len(all_years)

        # (Optional) background styling
        fig.patch.set_facecolor("#f7f7f5")
        ax.set_facecolor("#e6e6e6")

        for g in stacked_data:
            ax.bar(
                all_years,
                stacked_data[g],
                bottom=bottom,
                label=g,
                color=GROUP_COLORS.get(g, "gray")
            )
            bottom = [bottom[i] + stacked_data[g][i] for i in range(len(all_years))]

        ax.set_title(f"{state.upper()} - Number of Power Plants per Year (Grouped)")
        ax.set_xlabel("Year")
        ax.set_ylabel("Number of Plants")
        ax.legend(fontsize=8, loc="upper left", framealpha=1, facecolor="#f0f0f0")
        ax.grid(True)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)

        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)
        tab_widget.addTab(tab, state)

    dialog = QDialog()
    dialog.setWindowTitle("Energy Type Charts by State (Grouped)")
    dialog.setMinimumSize(1200, 700)
    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()

# Run
data = process_geojson_files()
plot_counts_tabbed(data)
