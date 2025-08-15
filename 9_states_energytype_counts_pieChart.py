# 11_states_energytype_counts_yearly_pieChart.py

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QWidget, QVBoxLayout

# 📁 GeoJSON base folder
BASE_DIR = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"

# 🎨 Energy labels and colors (same as before)
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
energy_colors = {
    v: c for v, c in zip(energy_labels.values(), [
        "red", "purple", "pink", "lightgreen", "gold", "gray", "white", "skyblue", "orange", "orange"
    ])
}
energy_colors["unbekannt"] = "black"
energy_colors["Other"] = "lightgray"  # 👈 diğer kategorisi

# 🔍 Koddan label çözümle
def parse_energy_type(feature):
    code = str(feature.get("properties", {}).get("Energietraeger", "")).strip()
    return energy_labels.get(code, "unbekannt")

# 🧮 Tüm state’ler için enerji tipi sayıları
def aggregate_counts_per_state():
    state_counts = defaultdict(Counter)

    for state_name in os.listdir(BASE_DIR):
        state_path = os.path.join(BASE_DIR, state_name)
        if not os.path.isdir(state_path):
            continue

        for file in os.listdir(state_path):
            if not file.endswith(".geojson") or file == "unknown.geojson":
                continue

            file_path = os.path.join(state_path, file)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    geo = json.load(f)
                    for feature in geo["features"]:
                        e_type = parse_energy_type(feature)
                        state_counts[state_name][e_type] += 1
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return state_counts

# 📊 Pie chart çizimi
def plot_pie_charts(state_data):
    tab_widget = QTabWidget()

    for state, counts in sorted(state_data.items()):
        total = sum(counts.values())
        if total == 0:
            continue

        # ✅ %1'in altındakileri "Other" kategorisine topla
        grouped_counts = Counter()
        for label, count in counts.items():
            ratio = count / total
            if ratio < 0.01:
                grouped_counts["Other"] += count
            else:
                grouped_counts[label] = count

        labels = list(grouped_counts.keys())
        values = list(grouped_counts.values())
        colors = [energy_colors.get(l, "gray") for l in labels]

        fig, ax = plt.subplots(figsize=(10, 10))
        fig.patch.set_facecolor("#f7f7f5")
        ax.set_facecolor("#e6e6e6")

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            textprops={'fontsize': 7}
        )
        ax.legend(labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8, facecolor="#f0f0f0")
        
        ax.set_title(f"{state.upper()} - Energy Type Distribution", fontsize=12)

        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, None)
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        tab.setLayout(layout)

        tab_widget.addTab(tab, state)

    # 🎯 Show as floating dialog
    dialog = QDialog()
    dialog.setWindowTitle("Energy Type Pie Charts by State")
    dialog.setMinimumSize(900, 700)

    layout = QVBoxLayout()
    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec_()

# 🚀 Main
state_data = aggregate_counts_per_state()
plot_pie_charts(state_data)
