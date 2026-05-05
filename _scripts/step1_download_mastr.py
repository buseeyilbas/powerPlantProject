

import os
import requests

raw_data_folder = r"C:\Users\jo73vure\Desktop\powerPlantProject\data\raw"

def download_file(url: str, destination_folder: str = raw_data_folder) -> str:

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    filename = os.path.basename(url)
    filepath = os.path.join(destination_folder, filename)

    print(f"Downloading {filename} to {destination_folder}...")

    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(filepath, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

    print(f"✔ Download completed: {filepath}")
    return filepath

if __name__ == "__main__":
    mastr_url = "https://download.marktstammdatenregister.de/Stichtag/Gesamtdatenexport_20250701_25.1.zip"
    download_file(mastr_url)
