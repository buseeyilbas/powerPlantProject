

import os
import json

def list_energy_codes(folder_path: str, key: str = "Energietraeger") -> None:
    energy_codes = set()

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            print(f"→ Scanning: {filename}")
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    for entry in data:
                        code = entry.get(key)
                        if code:
                            energy_codes.add(code)
            except Exception as e:
                print(f"⚠️ Failed to process {filename}: {e}")

    print("\n✔ Unique Energieträger codes found:\n")
    for code in sorted(energy_codes):
        print(code)

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    list_energy_codes(input_folder)
