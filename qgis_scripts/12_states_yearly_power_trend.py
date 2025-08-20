

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout


BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"


def compute_yearly_total_power():
    state_power = defaultdict(lambda: defaultdict(float))

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
                        brutto_raw = feature["properties"].get("Bruttoleistung", "0").replace(",", ".")
                        try:
                            brutto_kw = float(brutto_raw)
                            state_power[state_name][year] += brutto_kw
                        except ValueError:
                            continue
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return state_power


def plot_power_trend_charts(all_state_data):
    tab_widget = QTabWidget()

    for state, yearly_data in sorted(all_state_data.items()):
        years = sorted(yearly_data.keys())
        values = [yearly_data[y] for y in years]

        fig, ax = plt.subplots(figsize=(12, 6))
        fig.patch.set_facecolor("#f7f7f5")
        ax.set_facecolor("#e6e6e6")

        ax.plot(years, values, color="darkblue", marker="o", linewidth=2)


        for x, y in zip(years, values):
            if y > 0:
                ax.text(x, y + max(values) * 0.01, f"{y:,.0f}".replace(",", "."), ha="center", fontsize=8)

        ax.set_title(f"Total Installed Power per Year in {state.title()}", fontsize=13)
        ax.set_xlabel("Year")
        ax.set_ylabel("Total Power (kW)")
        ax.grid(True, linestyle="--", alpha=0.7)
        plt.xticks(rotation=45)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)

        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)

        tab_widget.addTab(tab, state)

    dialog = QDialog()
    dialog.setWindowTitle("Yearly Installed Power Trend (All States)")
    dialog.setMinimumSize(1100, 700)

    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()


data = compute_yearly_total_power()
plot_power_trend_charts(data)
