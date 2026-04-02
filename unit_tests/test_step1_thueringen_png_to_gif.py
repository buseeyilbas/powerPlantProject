"""
Unit tests for step1_thueringen_png_to_gif.py
"""

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from piechart_layer_scripts import step1_thueringen_png_to_gif as mod


def create_dummy_png(path: Path, color=(255, 0, 0, 255), size=(10, 10), mode="RGBA"):
    img = Image.new(mode, size, color)
    img.save(path, format="PNG")


def first_frame_pixel(gif_path: Path):
    with Image.open(gif_path) as gif:
        frame = gif.convert("RGBA")
        return frame.getpixel((0, 0))


def all_frame_pixels(gif_path: Path):
    pixels = []
    with Image.open(gif_path) as gif:
        for frame in ImageSequence.Iterator(gif):
            rgba = frame.convert("RGBA")
            pixels.append(rgba.getpixel((0, 0)))
    return pixels


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
    assert first_frame_pixel(output) == (255, 0, 0, 255)


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

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 1


def test_pngs_to_gif_frame_count(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))
    create_dummy_png(png_folder / "c.png", (0, 0, 255, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 3


def test_pngs_to_gif_preserves_all_frame_order(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "02.png", (0, 255, 0, 255))
    create_dummy_png(png_folder / "01.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "03.png", (0, 0, 255, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    pixels = all_frame_pixels(output)
    assert pixels == [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
    ]


def test_pngs_to_gif_keeps_frame_duration_metadata(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 750)

    with Image.open(output) as gif:
        duration = gif.info.get("duration")
        assert duration is not None
        assert duration > 0


def test_pngs_to_gif_sets_loop_forever(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert gif.info.get("loop") == 0


def test_pngs_to_gif_accepts_string_output_path(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, str(output), 500)

    assert output.exists()


def test_pngs_to_gif_overwrites_existing_output(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"
    output.write_bytes(b"not a real gif")

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 2


def test_pngs_to_gif_handles_rgb_pngs(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0), mode="RGB")
    create_dummy_png(png_folder / "b.png", (0, 255, 0), mode="RGB")

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 2


def test_pngs_to_gif_ignores_non_png_files(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))
    (png_folder / "note.txt").write_text("ignore me", encoding="utf-8")
    (png_folder / "c.jpg").write_bytes(b"not really a jpg")

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 2


def test_pngs_to_gif_uses_only_top_level_pngs(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()
    sub = png_folder / "sub"
    sub.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(sub / "b.png", (0, 255, 0, 255))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert getattr(gif, "n_frames", 1) == 1


def test_pngs_to_gif_keeps_output_image_size(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", size=(16, 12))
    create_dummy_png(png_folder / "b.png", size=(16, 12))

    output = tmp_path / "out.gif"

    mod.pngs_to_gif(png_folder, output, 500)

    with Image.open(output) as gif:
        assert gif.size == (16, 12)


def test_pngs_to_gif_raises_when_output_directory_missing(tmp_path):
    png_folder = tmp_path / "pngs"
    png_folder.mkdir()

    create_dummy_png(png_folder / "a.png", (255, 0, 0, 255))
    create_dummy_png(png_folder / "b.png", (0, 255, 0, 255))

    output = tmp_path / "missing_dir" / "out.gif"

    with pytest.raises(FileNotFoundError):
        mod.pngs_to_gif(png_folder, output, 500)