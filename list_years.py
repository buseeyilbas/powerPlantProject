

import os
import json
from collections import Counter

def extract_year(date_str: str) -> str:
    if isinstance(date_str, str) and len(date_str) >= 4:
        return date_str[:4]  # "2009-04-30" → "2009"
    return None

def list_installation_years(folder_path: str, key: str = "Inbetriebnahmedatum") -> None:
    year_counter = Counter()

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            print(f"→ Scanning: {filename}")
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    for entry in data:
                        raw_date = entry.get(key)
                        year = extract_year(raw_date)
                        if year:
                            year_counter[year] += 1
            except Exception as e:
                print(f"⚠️ Failed to process {filename}: {e}")

    print("\n✔ Installation years found:\n")
    for year, count in sorted(year_counter.items()):
        print(f"{year}: {count} entries")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
    list_installation_years(input_folder)
