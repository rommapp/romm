from io import BytesIO

import pytest
from PIL import Image

from utils.images import frame_durations, is_animated, webp_loop

FRAME_COLORS = ("red", "green", "blue")


def animated_image_bytes(
    fmt: str,
    durations: list[int],
    size: tuple[int, int] = (60, 90),
    loop: int | None = 0,
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
        **({} if loop is None else {"loop": loop}),
    )
    return buf.getvalue()


def truncated_animation_bytes(fmt: str) -> bytes:
    """An animation with its last frame cut short."""
    return animated_image_bytes(fmt, [100, 250, 400])[:-40]


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

    def test_over_pixel_budget(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("utils.images.MAX_ANIMATION_PIXELS", 2 * 60 * 90 - 1)
        with Image.open(BytesIO(animated_image_bytes("GIF", [100, 100]))) as img:
            assert not is_animated(img)


class TestFrameDurations:
    @pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
    def test_reads_each_frame(self, fmt: str):
        durations = [100, 250, 400]
        with Image.open(BytesIO(animated_image_bytes(fmt, durations))) as img:
            assert frame_durations(img) == durations
            assert img.tell() == 0

    @pytest.mark.parametrize("fmt", ["GIF", "PNG"])
    def test_damaged_frame(self, fmt: str):
        with Image.open(BytesIO(truncated_animation_bytes(fmt))) as img:
            assert frame_durations(img) is None
            assert img.tell() == 0

    def test_malformed_apng_frame(self):
        data = bytearray(animated_image_bytes("PNG", [100, 250, 400]))
        second_fctl = data.find(b"fcTL", data.find(b"fcTL") + 4)
        data[second_fctl + 4 : second_fctl + 8] = (99).to_bytes(4, "big")
        with Image.open(BytesIO(bytes(data))) as img:
            assert frame_durations(img) is None

    def test_over_pixel_budget(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("utils.images.MAX_ANIMATION_PIXELS", 2 * 60 * 90)
        with Image.open(BytesIO(animated_image_bytes("GIF", [100] * 3))) as img:
            assert frame_durations(img) is None


class TestWebpLoop:
    @pytest.mark.parametrize(
        "fmt, loop, expected",
        [
            ("GIF", None, 1),
            ("GIF", 0, 0),
            ("GIF", 3, 4),
            ("GIF", 0xFFFF, 0xFFFF),
            ("PNG", 3, 3),
            ("WEBP", 0, 0),
        ],
    )
    def test_plays_as_often_as_source(self, fmt: str, loop: int | None, expected: int):
        data = animated_image_bytes(fmt, [100, 100], loop=loop)
        with Image.open(BytesIO(data)) as img:
            assert webp_loop(img) == expected
