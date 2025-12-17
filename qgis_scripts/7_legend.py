import matplotlib.pyplot as plt
from qgis.PyQt.QtGui import QColor

# --- Define color palette ---
PALETTE = {
    "pv_kw":      QColor(255, 212,   0, 255),  # yellow
    "battery_kw": QColor(126,  87, 194, 255),  # purple
    "wind_kw":    QColor(173, 216, 230, 255),  # light blue
    "hydro_kw":   QColor( 30,  58, 138, 255),  # dark blue
    "biogas_kw":  QColor( 46, 125,  50, 255),  # dark green
    "others_kw":  QColor(158, 158, 158, 255),  # gray
}

# --- Convert QColor to matplotlib RGBA ---
def qcolor_to_rgba(qcolor: QColor):
    """Convert a QColor to an RGBA tuple normalized to 0–1."""
    return (
        qcolor.redF(), 
        qcolor.greenF(), 
        qcolor.blueF(), 
        qcolor.alphaF()
    )

# --- Data for the legend ---
energy_types = [
    (PALETTE["pv_kw"], "Photovoltaics - (Photovoltaik)"),
    (PALETTE["wind_kw"], "Onshore Wind Energy - (Windenergie an Land)"),
    (PALETTE["hydro_kw"], "Hydropower - (Wasserkraft)"),
    (PALETTE["biogas_kw"], "Biogas - (Biogas)"),
    (PALETTE["battery_kw"], "Battery Storage - (Stromspeicher)"),
    (PALETTE["others_kw"], "Others - (Andere)"),
]

# --- Create plot ---
fig, ax = plt.subplots(figsize=(5, 5))
ax.axis('off')

y = 1.0
for qcolor, label in energy_types:
    rgba = qcolor_to_rgba(qcolor)
    ax.scatter(0.06, y, color=rgba, s=90, edgecolor='black')
    ax.text(0.1, y, label, fontsize=10, va='center', ha='left')
    y -= 0.05

# Add notes
y -= 0.05
lines = ["*Symbol size proportional to power capacity"]
for line in lines:
    ax.text(0.1, y, line, fontsize=8, ha='left')
    y -= 0.07

ax.set_xlim(0, 1)
ax.set_ylim(0, 1.1)
fig.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.05)

plt.show()
