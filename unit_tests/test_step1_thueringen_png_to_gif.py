"""
Unit tests for step1_thueringen_png_to_gif.py
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_thueringen_png_to_gif as mod


def create_dummy_png(path: Path, color=(255, 0, 0, 255)):
    img = Image.new("RGBA", (10, 10), color)
    img.save(path, format="PNG")


def test_pngs_to_gif_basic(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    assert output.exists()


def test_pngs_to_gif_sorted_order(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))
    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    assert output.exists()


def test_pngs_to_gif_no_files(tmp_path):
    png_folder = tmp_path / "empty"
    png_folder.mkdir()

    output = tmp_path / "out.gif"

    with pytest.raises(FileNotFoundError):
        mod.pngs_to_gif(png_folder, output, 500)


def test_pngs_to_gif_single_file(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    assert output.exists()


def test_pngs_to_gif_frame_count(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))
    create_dummy_png(png_folder / "c.png", (0, 0, 255, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    gif = Image.open(output)

    assert getattr(gif, "n_frames", 1) == 3