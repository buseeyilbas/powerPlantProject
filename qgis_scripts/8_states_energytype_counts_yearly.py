

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout
from qgis.utils import iface


BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"

# Energy source color map
ENERGY_TYPE_COLORS = {
    "Deep Geothermal Energy (Tiefe Geothermie)": "red",
    "Sewage Gas (Klärgas)": "purple",
    "Pressure Relief Energy (Druckentspannung)": "pink",
    "Biogas (Biogas)": "lightgreen",
    "Photovoltaics (Photovoltaik)": "gold",
    "Battery Storage (Stromspeicher)": "gray",
    "Onshore Wind Energy (Windenergie an Land)": "white",
    "Hydropower (Wasserkraft)": "skyblue",
    "Pressure Relief (CHP Mix) (Druckentspannung - BHKW, Mischform)": "orange",
    "Pressure Relief (Small-scale Plants) (Druckentspannung - kleine Anlagen)": "orange",
    "unbekannt": "black"
}

# Energy type labels (code to label)
energy_labels = {
    "2403": "Deep Geothermal Energy (Tiefe Geothermie)",
    "2405": "Sewage Gas (Klärgas)",
    "2406": "Pressure Relief Energy (Druckentspannung)",
    "2493": "Biogas (Biogas)",
    "2495": "Photovoltaics (Photovoltaik)",
    "2496": "Battery Storage (Stromspeicher)",
    "2497": "Onshore Wind Energy (Windenergie an Land)",
    "2498": "Hydropower (Wasserkraft)",
    "2957": "Pressure Relief (CHP Mix) (Druckentspannung - BHKW, Mischform)",
    "2958": "Pressure Relief (Small-scale Plants) (Druckentspannung - kleine Anlagen)"
}


ALLOWED_ENERGY_TYPES = set(energy_labels.values())

# Energy type parse
def parse_energy_type(feature):
    props = feature.get("properties", {})
    code = str(props.get("Energietraeger", "")).strip()
    label = energy_labels.get(code, "unbekannt")
    return label.strip()

# Data collector
def process_geojson_files():
    result = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # state → year → type → count

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
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    geo = json.load(f)
                    for feature in geo["features"]:
                        e_type = parse_energy_type(feature)
                        result[state_name][year][e_type] += 1
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return result

# Plot with toolbar and tabs
def plot_counts_tabbed(aggregated_data):
    tab_widget = QTabWidget()

    for state, year_data in sorted(aggregated_data.items()):
        all_years = sorted(year_data.keys())
        all_types = [label for label in energy_labels.values()] + ["unbekannt"]

        # Prepare stacked bar data
        stacked_data = {
            t: [year_data[y].get(t, 0) for y in all_years]
            for t in all_types
            if any(year_data[y].get(t, 0) > 0 for y in all_years)
        }

        fig, ax = plt.subplots(figsize=(10, 6))
        bottom = [0] * len(all_years)
        
        
        fig.patch.set_facecolor("#f7f7f5")  # figure outer background
        ax.set_facecolor("#e6e6e6")         # plot area background

        for t in stacked_data:
            ax.bar(
                all_years,
                stacked_data[t],
                bottom=bottom,
                label=t,
                color=ENERGY_TYPE_COLORS.get(t, "gray")
            )
            bottom = [bottom[i] + stacked_data[t][i] for i in range(len(all_years))]

        ax.set_title(f"{state.upper()} - Number of Power Plants per Year")
        ax.set_xlabel("Year")
        ax.set_ylabel("Number of Plants")
        ax.legend(fontsize=8, loc='upper left', framealpha=1, facecolor="#f0f0f0")
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
    dialog.setWindowTitle("Energy Type Charts by State")
    dialog.setMinimumSize(1200, 700)

    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()


data = process_geojson_files()
plot_counts_tabbed(data)
