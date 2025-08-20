

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout


BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"

# how many plants are commissioned per year, per state
def count_plants_per_year():
    counts = defaultdict(lambda: defaultdict(int))  # state → year → count

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
                    num_plants = len(geo["features"])
                    counts[state_name][year] += num_plants
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return counts

# plot per state
def plot_yearly_bar_charts(all_counts):
    tab_widget = QTabWidget()

    for state, yearly_counts in sorted(all_counts.items()):
        years = sorted(yearly_counts.keys())
        values = [yearly_counts[y] for y in years]

        fig, ax = plt.subplots(figsize=(12, 10))
        fig.patch.set_facecolor("#f7f7f5")
        ax.set_facecolor("#e6e6e6")

        bars = ax.bar(years, values, color="cornflowerblue", edgecolor="black")

        # value labels on top of the bars
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 10,
                    f"{int(height)}",
                    ha='center',
                    va='bottom',
                    fontsize=7
                )

        ax.set_title(f"Number of Power Plants Commissioned per Year ({state.title()})", fontsize=13)
        ax.set_xlabel("Year")
        ax.set_ylabel("Number of Plants")
        ax.grid(axis='y', linestyle='--', alpha=0.7)
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
    dialog.setWindowTitle("Power Plants Commissioned per Year (All States)")
    dialog.setMinimumSize(1100, 700)

    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()


counts = count_plants_per_year()
plot_yearly_bar_charts(counts)
