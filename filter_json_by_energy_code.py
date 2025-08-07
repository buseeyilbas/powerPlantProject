import os
import json

def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def filter_by_energy_codes(input_folder: str, output_base_folder: str, energy_key: str, energy_codes: list):
    if not os.path.exists(output_base_folder):
        os.makedirs(output_base_folder)

    for code in energy_codes:
        os.makedirs(os.path.join(output_base_folder, code), exist_ok=True)

    for file_name in os.listdir(input_folder):
        if file_name.endswith(".json"):
            input_path = os.path.join(input_folder, file_name)
            print(f"\n🔍 Processing: {file_name}")
            try:
                data = load_json(input_path)
            except Exception as e:
                print(f"⚠️ Failed to load {file_name}: {e}")
                continue

            for code in energy_codes:
                filtered = [entry for entry in data if entry.get(energy_key) == code]
                if filtered:
                    output_path = os.path.join(output_base_folder, code, file_name)
                    save_json(filtered, output_path)
                    print(f"✔ Saved {len(filtered):>4} entries → {code}/{file_name}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    output_base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_energy_code"
    energy_key = "Energietraeger"

    energy_codes = [
        "2403", "2405", "2406", "2493", "2495", "2496", "2497", "2498", "2957", "2958"
    ]

    filter_by_energy_codes(input_folder, output_base_folder, energy_key, energy_codes)
