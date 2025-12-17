import os
import json

def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def filter_by_state_codes(input_folder: str, output_base_folder: str, state_key: str, state_codes: list):
    if not os.path.exists(output_base_folder):
        os.makedirs(output_base_folder)

    for code in state_codes:
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

            for code in state_codes:
                filtered = [entry for entry in data if entry.get(state_key) == code]
                if filtered:
                    output_path = os.path.join(output_base_folder, code, file_name)
                    save_json(filtered, output_path)
                    print(f"✔ Saved {len(filtered):>4} entries → {code}/{file_name}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
    output_base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_state_code_bundesland"
    state_key = "Bundesland"

    state_codes = [
        "1400", "1401", "1402", "1403", "1404", "1405", "1406", "1407", 
        "1408", "1409", "1410", "1411", "1412", "1413", "1414", "1415"
    ]

    filter_by_state_codes(input_folder, output_base_folder, state_key, state_codes)
