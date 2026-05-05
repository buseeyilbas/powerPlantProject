import os
import shutil
import xml.etree.ElementTree as ET

def is_valid_xml(file_path):
    print(f"📄 Scanning: {os.path.basename(file_path)}")
    try:
        ET.parse(file_path)
        return True
    except ET.ParseError as e:
        print(f"❌ Invalid XML: {file_path}\n   ↪ {e}")
        return False

def validate_and_copy_xmls(input_folder, output_folder):
    total = 0
    valid = 0

    os.makedirs(output_folder, exist_ok=True)

    for root, _, files in os.walk(input_folder):
        for file_name in files:
            if file_name.endswith(".xml"):
                total += 1
                file_path = os.path.join(root, file_name)

                if is_valid_xml(file_path):
                    valid += 1
                    dest_path = os.path.join(output_folder, file_name)
                    shutil.copy(file_path, dest_path)

    print(f"\n🔍 XML files scanned: {total}")
    print(f"✅ Valid: {valid} / ❌ Invalid: {total - valid}")
    print(f"📁 Valid XMLs copied to: {output_folder}")

if __name__ == "__main__":
    input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\extracted"
    output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\valid_xml"

    validate_and_copy_xmls(input_folder, output_folder)
