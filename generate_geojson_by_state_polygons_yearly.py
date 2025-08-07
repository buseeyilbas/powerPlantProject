import os
import json
from collections import defaultdict
from shapely.geometry import shape, MultiPolygon, Polygon, Point


# Load state polygons
with open("C:/Users/jo73vure/Desktop/powerPlantProject/data/polygon_states.json", encoding="utf-8") as f:
    polygon_data = json.load(f)

features = polygon_data["features"] if isinstance(polygon_data, dict) and "features" in polygon_data else polygon_data

state_polygons = []
for feature in features:
    state_id = feature.get("id")
    state_name = feature.get("properties", {}).get("name")
    geometry = shape(feature.get("geometry"))

    # Force all geometries to MultiPolygon for consistency
    if isinstance(geometry, Polygon):
        geometry = MultiPolygon([geometry])

    if not isinstance(geometry, MultiPolygon) or not state_name:
        continue

    state_polygons.append((state_id, state_name, geometry))


# Load JSON file
def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Convert a powerplant entry to a GeoJSON Feature
def create_feature(entry):
    try:
        lon = float(entry.get("Laengengrad", "").replace(",", "."))
        lat = float(entry.get("Breitengrad", "").replace(",", "."))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None, None
        point = Point(lon, lat)
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {k: v for k, v in entry.items() if k not in ["Laengengrad", "Breitengrad"]}
        }
        return point, feature
    except:
        return None, None


# Main conversion function
def convert_jsons(input_folder, output_folder):
    grouped_features = defaultdict(list)
    total_files = 0
    matched_count = 0
    unmatched_count = 0

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
                    point, feature = create_feature(entry)
                    if point is None:
                        continue

                    matched = False
                    for sid, state_name, polygon in state_polygons:
                        if polygon.contains(point):
                            grouped_features[state_name].append(feature)
                            matched = True
                            matched_count += 1
                            break

                    if not matched:
                        unmatched_count += 1
                        print(f"⚠️ Not matched: {entry.get('EinheitMastrNummer')} at {point}")

    # 🧠 Now split per state + year
    for state_name, features in grouped_features.items():
        year_groups = defaultdict(list)
        for feature in features:
            date_str = feature["properties"].get("Inbetriebnahmedatum", "")
            year = date_str[:4] if len(date_str) >= 4 else "unknown"
            year_groups[year].append(feature)

        # Write per year file inside subfolder
        state_folder = os.path.join(output_folder, state_name)
        os.makedirs(state_folder, exist_ok=True)

        for year, feats in year_groups.items():
            output_path = os.path.join(state_folder, f"{year}.geojson")
            geojson = {
                "type": "FeatureCollection",
                "features": feats
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(geojson, f, indent=2, ensure_ascii=False)

            print(f"✅ {state_name}/{year}.geojson → {len(feats)} features")

    print(f"\n📄 Processed {total_files} JSON files in total.")
    print(f"✅ Matched entries: {matched_count}")
    print(f"⚠️ Unmatched entries: {unmatched_count}")


# Run the conversion
if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\geojson\by_state_polygon_yearly"

    convert_jsons(input_folder, output_folder)