import os
import json

# 📁 Paths
input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\json"
output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_json"

# ✅ Required keys to keep the entry
REQUIRED_KEYS = ["Bundesland", "Energietraeger", "Gemeindeschluessel", "LokationMaStRNummer", "EegMaStRNummer"]

os.makedirs(output_folder, exist_ok=True)

total_files = 0
total_valid_entries = 0

def is_valid(entry: dict) -> bool:
    return all(key in entry and entry[key] not in ["", None] for key in REQUIRED_KEYS)

for file_name in os.listdir(input_folder):
    if not file_name.endswith(".json"):
        continue

    file_path = os.path.join(input_folder, file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Skipped invalid JSON: {file_name}")
            continue

    valid_entries = [entry for entry in data if is_valid(entry)]

    if not valid_entries:
        print(f"❌ No valid entries in: {file_name}")
        continue

    output_path = os.path.join(output_folder, f"{file_name}")
    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(valid_entries, out_f, indent=2, ensure_ascii=False)

    print(f"✅ {file_name}: {len(valid_entries)} valid entries saved.")
    total_files += 1
    total_valid_entries += len(valid_entries)

# 📊 Summary
print("\n📊 Summary:")
print(f"📂 JSON files processed: {total_files}")
print(f"✔️ Total valid entries extracted: {total_valid_entries}")
