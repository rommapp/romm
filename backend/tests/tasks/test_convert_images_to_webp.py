from pathlib import Path

import pytest
from PIL import Image
from tests.utils.test_images import (
    DURATIONS,
    animated_image_bytes,
    truncated_animation_bytes,
)

from tasks.scheduled.convert_images_to_webp import ImageConverter
from utils.images import frame_durations


class TestImageConverter:
    @pytest.fixture
    def converter(self) -> ImageConverter:
        return ImageConverter()

    def test_converts_static_image(self, converter: ImageConverter, tmp_path: Path):
        source = tmp_path / "big.png"
        Image.new("RGB", (8, 8), "red").save(source)

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.format == "WEBP"

    @pytest.mark.parametrize("fmt", ["GIF", "PNG"])
    def test_keeps_animation(self, converter: ImageConverter, tmp_path: Path, fmt: str):
        source = tmp_path / f"big.{fmt.lower()}"
        source.write_bytes(animated_image_bytes(fmt))

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.format == "WEBP"
            assert frame_durations(img) == DURATIONS

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

    # Providers serve WebP under any name, and covers are stored as big.png
    @pytest.mark.parametrize("name", ["big.png", "big.webp"])
    def test_keeps_webp_source_bytes(
        self, converter: ImageConverter, tmp_path: Path, name: str
    ):
        data = animated_image_bytes("WEBP")
        (tmp_path / name).write_bytes(data)

        assert converter.convert_to_webp(tmp_path / name, force=True)

        assert (tmp_path / "big.webp").read_bytes() == data
