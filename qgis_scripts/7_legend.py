import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7, 5))
ax.axis('off')

energy_types = [
    ("red", "Deep Geothermal Energy - (Tiefe Geothermie)"),
    ("purple", "Sewage Gas - (Klärgas)"),
    ("pink", "Pressure Relief Energy - (Druckentspannung)"),
    ("lightgreen", "Biogas - (Biogas)"),
    ("gold", "Photovoltaics - (Photovoltaik)"),
    ("gray", "Battery Storage - (Stromspeicher)"),
    ("white", "Onshore Wind Energy - (Windenergie an Land)"),
    ("skyblue", "Hydropower - (Wasserkraft)"),
    ("orange", "Pressure Relief (CHP Mix) - (Druckentspannung - BHKW, Mischform)"),
    ("orange", "Pressure Relief (Small-scale Plants) - (Druckentspannung - kleine Anlagen)")
]

y = 1.0
for color, label in energy_types:
    ax.scatter(0.06, y, color=color, s=90, edgecolor='black')
    ax.text(0.1, y, label, fontsize=10, verticalalignment='center', horizontalalignment='left')
    y -= 0.05

y -= 0.05

lines = [
    "*Symbol size proportional to power capacity",
    "OUTLINES",
    "-Green: remotely controllable",
    "-Black: not remotely controllable"
]

for line in lines:
    ax.text(0.1, y, line, fontsize=8, horizontalalignment='left')
    y -= 0.07


ax.set_xlim(0, 1)
ax.set_ylim(0, 1.1)


fig.subplots_adjust(left=0.1, right=0.95, top=0.95, bottom=0.05)

plt.show()
