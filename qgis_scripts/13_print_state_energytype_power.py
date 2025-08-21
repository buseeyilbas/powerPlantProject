import os
from qgis.core import QgsVectorLayer

# === PATH CONFIGURATION ===
GEOJSON_FOLDER = r"C:/Users/jo73vure/Desktop/powerPlantProject/data/geojson/by_state_three_checks"

# === ENERGY TYPE MAPPING ===
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

    power_by_type = {code: 0.0 for code in ENERGY_TYPES}

    for feat in layer.getFeatures():
        et = str(feat["Energietraeger"])
        power = parse_kw(feat["Bruttoleistung"])
        if et in power_by_type:
            power_by_type[et] += power

    print(f"\n📍 State: {state_name}")
    for code, total_power in power_by_type.items():
        if total_power > 0:
            print(f"  - {ENERGY_TYPES[code]}: {total_power:.1f} kW")

print("\n✅ Done.")
