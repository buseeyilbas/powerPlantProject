import os
import json

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

def convert_all_json_to_geojson(input_folder, output_path):
    features = []
    total_files = 0
    total_features = 0

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
                    feature = create_feature(entry)
                    if feature:
                        features.append(feature)
                        total_features += 1

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Created {output_path}")
    print(f"📄 Processed {total_files} JSON files")
    print(f"📌 Total {total_features} features written")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_geojson_path = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\all_germany.geojson"

    convert_all_json_to_geojson(input_folder, output_geojson_path)
