import os
import json
from collections import defaultdict

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_year(date_str):
    if isinstance(date_str, str) and len(date_str) >= 4:
        year = date_str[:4]
        if year.isdigit() and 1900 <= int(year) <= 2025:
            return year
    return None

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

def convert_jsons_by_year(input_folder, output_folder):
    grouped_features = defaultdict(list)
    total_files = 0
    matched_count = 0
    skipped_count = 0

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
                    year = extract_year(entry.get("Inbetriebnahmedatum"))
                    if not year:
                        skipped_count += 1
                        continue

                    feature = create_feature(entry)
                    if feature:
                        grouped_features[year].append(feature)
                        matched_count += 1
                    else:
                        skipped_count += 1

    os.makedirs(output_folder, exist_ok=True)

    for year, features in grouped_features.items():
        file_name = f"{year}.geojson"
        output_path = os.path.join(output_folder, file_name)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved {len(features)} features to {output_path}")

    print(f"\n📄 Processed {total_files} JSON files.")
    print(f"📌 Valid year + coordinate entries: {matched_count}")
    print(f"⚠️ Skipped entries (missing year or coords): {skipped_count}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_year"

    convert_jsons_by_year(input_folder, output_folder)
