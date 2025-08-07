# extract_zip.py

import os
import zipfile

# Define input/output folder structure
input_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\raw"        # Folder containing ZIP files
output_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\extracted" # Where to extract the contents

def extract_all_zips(input_dir: str, output_dir: str) -> None:

    if not os.path.exists(input_dir):
        print(f"Input folder does not exist: {input_dir}")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    zip_files = [f for f in os.listdir(input_dir) if f.endswith(".zip")]
    
    if not zip_files:
        print("No ZIP files found in input directory.")
        return

    for zip_file in zip_files:
        zip_path = os.path.join(input_dir, zip_file)
        extract_path = os.path.join(output_dir, os.path.splitext(zip_file)[0])

        print(f"Extracting {zip_file} to {extract_path}...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        print(f"✔ Done extracting {zip_file}.\n")

if __name__ == "__main__":
    extract_all_zips(input_folder, output_folder)
