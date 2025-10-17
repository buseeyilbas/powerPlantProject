import os
import json
import xml.etree.ElementTree as ET

def xml_file_to_json(xml_path: str, json_path: str):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        data = []
        for child in root:
            entry = {elem.tag: elem.text for elem in child}
            data.append(entry)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✔ Converted {os.path.basename(xml_path)} to {os.path.basename(json_path)}")
    except Exception as e:
        print(f"⚠️ Failed to convert {xml_path}: {e}")

def batch_convert_xml_to_json(input_folder: str, output_folder: str):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.endswith(".xml"):
                xml_path = os.path.join(root, file)
                json_filename = os.path.splitext(file)[0] + ".json"
                json_path = os.path.join(output_folder, json_filename)

                xml_file_to_json(xml_path, json_path)

if __name__ == "__main__":
    extracted_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_xml"
    json_output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\json"
    batch_convert_xml_to_json(extracted_folder, json_output_folder)
