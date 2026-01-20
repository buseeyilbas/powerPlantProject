import os
import json
from typing import Optional

def extract_year(date_str: str) -> Optional[str]:
    if isinstance(date_str, str) and len(date_str) >= 4:
        year = date_str[:4]
        if year.isdigit():
            return year
    return None

def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def filter_by_installation_years(input_folder: str, output_base_folder: str, year_key: str = "Inbetriebnahmedatum"):
    # Create output directories for years between 1900 and 2025
    valid_years = [str(y) for y in range(1900, 2026)]
    for year in valid_years:
        os.makedirs(os.path.join(output_base_folder, year), exist_ok=True)

    for file_name in os.listdir(input_folder):
        if file_name.endswith(".json"):
            input_path = os.path.join(input_folder, file_name)
            print(f"\n🔍 Processing: {file_name}")
            try:
                data = load_json(input_path)
            except Exception as e:
                print(f"⚠️ Failed to load {file_name}: {e}")
                continue

            year_groups = {year: [] for year in valid_years}

            for entry in data:
                raw_date = entry.get(year_key)
                year = extract_year(raw_date)
                if year in valid_years:
                    year_groups[year].append(entry)

            for year, entries in year_groups.items():
                if entries:
                    output_path = os.path.join(output_base_folder, year, file_name)
                    save_json(entries, output_path)
                    print(f"✔ Saved {len(entries):>4} entries → {year}/{file_name}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"
    output_base_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\filtered_json_by_year"
    filter_by_installation_years(input_folder, output_base_folder)
