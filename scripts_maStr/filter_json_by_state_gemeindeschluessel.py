import os
import json

def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_state_prefix(gemeindeschluessel: str):
    if isinstance(gemeindeschluessel, str) and len(gemeindeschluessel) >= 2:
        return gemeindeschluessel[:2]
    return None

def filter_by_state_prefix(input_folder: str, output_base_folder: str):
    if not os.path.exists(output_base_folder):
        os.makedirs(output_base_folder)

    for file_name in os.listdir(input_folder):
        if file_name.endswith(".json"):
            input_path = os.path.join(input_folder, file_name)
            print(f"\n🔍 Processing: {file_name}")
            try:
                data = load_json(input_path)
            except Exception as e:
                print(f"⚠️ Failed to load {file_name}: {e}")
                continue

            state_buckets = {}

            for entry in data:
                gkey = entry.get("Gemeindeschluessel", "")
                prefix = extract_state_prefix(gkey)
                if prefix:
                    state_buckets.setdefault(prefix, []).append(entry)

            for prefix, entries in state_buckets.items():
                output_folder = os.path.join(output_base_folder, prefix)
                os.makedirs(output_folder, exist_ok=True)
                output_path = os.path.join(output_folder, file_name)
                save_json(entries, output_path)
                print(f"✔ Saved {len(entries):>4} entries → {prefix}/{file_name}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_state_gemeindeschluessel"

    filter_by_state_prefix(input_folder, output_base_folder)
