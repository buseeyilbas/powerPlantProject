import os
from qgis.core import QgsVectorLayer

# === PATH CONFIGURATION ===
GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

# === ENERGY TYPE MAPPING ===
# Keep these five as distinct categories:
PRIMARY_TYPES =  {
    "2495": "Photovoltaics",
    "2497": "Onshore Wind",
    "2498": "Hydropower",
    "2493": "Biogas",
    "2496": "Battery",
    
#    "2403": "Deep Geothermal",
#    "2405": "Sewage Gas",
#    "2406": "Pressure Relief",
#    "2957": "Pressure Relief CHP",
#    "2958": "Pressure Relief Small"
}

# Everything below is grouped into "Others":
OTHERS_CODES = {"2403", "2405", "2406", "2957", "2958"}

# Optional: any unknown/rare codes will also fall back to "Others".
GROUP_ORDER = ["Photovoltaics", "Onshore Wind", "Hydropower", "Biogas", "Battery", "Others"]

# (Optional) color map for pie charts (same as legend)
GROUP_COLORS = {
    "Photovoltaics": "yellow",
    "Battery": "purple",
    "Onshore Wind": "lightskyblue",
    "Hydropower": "darkblue",
    "Biogas": "darkgreen",
    "Others": "gray",
}

def parse_kw(value):
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except:
        return 0.0

# === MAIN LOOP ===
for fname in os.listdir(GEOJSON_FOLDER):
    if not fname.endswith(".geojson"):
        continue

    fpath = os.path.join(GEOJSON_FOLDER, fname)
    state_name = os.path.splitext(fname)[0]
    layer = QgsVectorLayer(fpath, state_name, "ogr")

    if not layer.isValid():
        print(f"❌ Failed to load {fname}")
        continue

    # Grouped totals (five main + Others)
    power_by_group = {g: 0.0 for g in GROUP_ORDER}

    for feat in layer.getFeatures():
        code = str(feat["Energietraeger"])
        kw = parse_kw(feat["Bruttoleistung"])

        if code in PRIMARY_TYPES:
            key = PRIMARY_TYPES[code]
        elif code in OTHERS_CODES:
            key = "Others"
        else:
            key = "Others"  # fallback for any unexpected code

        power_by_group[key] += kw

    # Print in fixed order, skip zeros
    print(f"\n📍 State: {state_name}")
    for g in GROUP_ORDER:
        total_kw = power_by_group[g]
        if total_kw > 0:
            print(f"  - {g}: {total_kw:.1f} kW")

print("\n✅ Done.")
