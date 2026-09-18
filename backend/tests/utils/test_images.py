from io import BytesIO

import pytest
from PIL import Image

from utils.images import frame_durations, is_animated

FRAME_COLORS = ("red", "green", "blue")


def animated_image_bytes(
    fmt: str, durations: list[int], size: tuple[int, int] = (60, 90)
) -> bytes:
    """Encode one solid frame per duration as an animated image."""
    frames = [
        Image.new("RGB", size, FRAME_COLORS[i % len(FRAME_COLORS)])
        for i in range(len(durations))
    ]
    buf = BytesIO()
    frames[0].save(
        buf,
        format=fmt,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )
    return buf.getvalue()


class TestIsAnimated:
    @pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
    def test_multi_frame_image(self, fmt: str):
        with Image.open(BytesIO(animated_image_bytes(fmt, [100, 100]))) as img:
            assert is_animated(img)

    def test_single_frame_image(self):
        buf = BytesIO()
        Image.new("RGB", (4, 4)).save(buf, format="PNG")
        with Image.open(buf) as img:
            assert not is_animated(img)

    def test_multi_page_tiff(self):
        # Browsers show the first page of a TIFF, so its pages aren't frames
        buf = BytesIO()
        pages = [Image.new("RGB", (4, 4)), Image.new("RGB", (4, 4), "red")]
        pages[0].save(buf, format="TIFF", save_all=True, append_images=pages[1:])
        with Image.open(buf) as img:
            assert img.is_animated
            assert not is_animated(img)


class TestFrameDurations:
    @pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
    def test_reads_each_frame(self, fmt: str):
        durations = [100, 250, 400]
        with Image.open(BytesIO(animated_image_bytes(fmt, durations))) as img:
            assert frame_durations(img) == durations
