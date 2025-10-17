# 6_filter_json_by_active_status.py
# This script filters all JSON files from "valid_json" and keeps only active power plants.
# Active plants are defined as entries where "EinheitBetriebsstatus" == "35" (in Betrieb).
# For each file, the script reports how many active and inactive units exist.

import os
import json

# --- Input & Output folders ---
input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"
output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\active_json"

# --- Helper functions ---
def load_json(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_active(entry: dict) -> bool:
    """Return True if the power plant is active (EinheitBetriebsstatus == '35')."""
    return str(entry.get("EinheitBetriebsstatus", "")).strip() == "35"

# --- Main processing function ---
def filter_active_jsons():
    os.makedirs(output_folder, exist_ok=True)
    total_files = 0
    total_active_entries = 0
    total_inactive_entries = 0

    for file_name in os.listdir(input_folder):
        if not file_name.endswith(".json"):
            continue
        file_path = os.path.join(input_folder, file_name)
        try:
            data = load_json(file_path)
        except json.JSONDecodeError:
            print(f"⚠️ Skipped invalid JSON: {file_name}")
            continue

        active_entries = [entry for entry in data if is_active(entry)]
        inactive_count = len(data) - len(active_entries)

        if not active_entries:
            print(f"❌ No active entries in: {file_name} ({inactive_count} inactive)")
            total_inactive_entries += inactive_count
            continue

        output_path = os.path.join(output_folder, file_name)
        save_json(active_entries, output_path)
        print(f"✅ {file_name}: {len(active_entries)} active saved, {inactive_count} inactive found.")

        total_files += 1
        total_active_entries += len(active_entries)
        total_inactive_entries += inactive_count

    print("\n📊 Summary:")
    print(f"📂 JSON files processed: {total_files}")
    print(f"✔️ Total active entries saved: {total_active_entries}")
    print(f"⚫ Total inactive entries detected: {total_inactive_entries}")

# --- Run directly ---
if __name__ == "__main__":
    filter_active_jsons()
