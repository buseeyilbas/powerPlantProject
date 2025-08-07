import os
import json
from collections import defaultdict

# State name mapping by Gemeindeschlüssel prefix
STATE_PREFIXES = {
    "01": "schleswig_holstein",
    "02": "hamburg",
    "03": "niedersachsen",
    "04": "bremen",
    "05": "nordrhein_westfalen",
    "06": "hessen",
    "07": "rheinland_pfalz",
    "08": "baden_wuerttemberg",
    "09": "bayern",
    "10": "saarland",
    "11": "berlin",
    "12": "brandenburg",
    "13": "mecklenburg_vorpommern",
    "14": "sachsen",
    "15": "sachsen_anhalt",
    "16": "thueringen"
}

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def create_feature(entry):
    try:
        lon = float(entry.get("Laengengrad", "").replace(",", "."))
        lat = float(entry.get("Breitengrad", "").replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
    except (ValueError, TypeError):
        return None

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat]
        },
        "properties": {k: v for k, v in entry.items() if k not in ["Laengengrad", "Breitengrad"]}
    }

def convert_jsons_by_state_prefix(input_folder, output_folder):
    grouped_features = defaultdict(list)
    total_files = 0

    for root, _, files in os.walk(input_folder):
        for file_name in files:
            if file_name.endswith(".json"):
                print(f"📂 Scanning: {file_name}")
                file_path = os.path.join(root, file_name)
                try:
                    data = load_json(file_path)
                    total_files += 1
                except Exception as e:
                    print(f"⚠️ Could not load {file_name}: {e}")
                    continue

                for entry in data:
                    gemeindeschluessel = entry.get("Gemeindeschluessel", "")
                    if not isinstance(gemeindeschluessel, str) or len(gemeindeschluessel) < 2:
                        continue
                    state_prefix = gemeindeschluessel[:2]
                    feature = create_feature(entry)
                    if feature:
                        grouped_features[state_prefix].append(feature)

    os.makedirs(output_folder, exist_ok=True)

    for prefix, features in grouped_features.items():
        state_name = STATE_PREFIXES.get(prefix, f"state_{prefix}")
        file_name = f"{prefix}_{state_name}.geojson"
        output_path = os.path.join(output_folder, file_name)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(features)} features to {output_path}")

    print(f"\n📄 Processed {total_files} JSON files in total.")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson"

    convert_jsons_by_state_prefix(input_folder, output_folder)
