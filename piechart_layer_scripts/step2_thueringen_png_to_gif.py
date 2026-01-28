

from PIL import Image
from pathlib import Path




# Disable DecompressionBomb protection (we trust our own images)
Image.MAX_IMAGE_PIXELS = None

# Folder containing PNG images
PNG_FOLDER = Path(
    r"C:\Users\jo73vure\Desktop\powerPlantProject\exports\2_statewise_landkreis_pie_yearly\thuringen_statewiseLandkreisPie_yearly_masked"
)

# Output GIF file
OUTPUT_GIF = PNG_FOLDER / "thueringen_landkreis_piecharts_statewise_gif.gif"

# Frame duration in milliseconds
FRAME_DURATION_MS = 2000  # 2 seconds per frame

def pngs_to_gif(png_folder: Path, output_gif: str, duration: int) -> None:
    png_files = sorted(png_folder.glob("*.png"))

    if not png_files:
        raise FileNotFoundError("No PNG files found in the folder.")

    frames = [Image.open(p).convert("RGBA") for p in png_files]

    frames[0].save(
        output_gif,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )

    print(f"[OK] GIF created: {output_gif}")
    print(f"[INFO] Frames used: {len(frames)}")



if __name__ == "__main__":
    pngs_to_gif(PNG_FOLDER, OUTPUT_GIF, FRAME_DURATION_MS)


