from pathlib import Path

import pytest
from PIL import Image
from tests.utils.test_images import animated_image_bytes, truncated_animation_bytes

from tasks.scheduled.convert_images_to_webp import ImageConverter
from utils.images import frame_durations


class TestImageConverter:
    @pytest.fixture
    def converter(self):
        return ImageConverter()

    def test_converts_static_image(self, converter: ImageConverter, tmp_path: Path):
        source = tmp_path / "big.png"
        Image.new("RGB", (8, 8), "red").save(source)

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.format == "WEBP"

    @pytest.mark.parametrize("fmt, ext", [("GIF", "gif"), ("PNG", "png")])
    def test_keeps_animation(
        self, converter: ImageConverter, tmp_path: Path, fmt: str, ext: str
    ):
        durations = [100, 250, 400]
        source = tmp_path / f"big.{ext}"
        source.write_bytes(animated_image_bytes(fmt, durations))

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.format == "WEBP"
            assert frame_durations(img) == durations

    def test_play_once_gif_stays_play_once(
        self, converter: ImageConverter, tmp_path: Path
    ):
        source = tmp_path / "big.gif"
        source.write_bytes(animated_image_bytes("GIF", [100, 100], loop=None))

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.info["loop"] == 1

    def test_damaged_animation_keeps_first_frame(
        self, converter: ImageConverter, tmp_path: Path
    ):
        source = tmp_path / "big.gif"
        source.write_bytes(truncated_animation_bytes("GIF"))

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert not img.is_animated

    def test_copies_webp_source(self, converter: ImageConverter, tmp_path: Path):
        # Providers serve WebP under any name, and covers are stored as big.png
        data = animated_image_bytes("WEBP", [100, 250])
        source = tmp_path / "big.png"
        source.write_bytes(data)

        assert converter.convert_to_webp(source, force=True)

        assert (tmp_path / "big.webp").read_bytes() == data

    def test_leaves_webp_in_place(self, converter: ImageConverter, tmp_path: Path):
        data = animated_image_bytes("WEBP", [100, 250])
        source = tmp_path / "big.webp"
        source.write_bytes(data)

        assert converter.convert_to_webp(source, force=True)

        assert source.read_bytes() == data
