from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from utils.images import frame_durations, is_animated, webp_loop

FRAME_SIZE = (60, 90)
FRAME_COLORS = ("red", "green", "blue")
DURATIONS = [100, 250, 400]


def encode_animation(
    frames: list[Image.Image], fmt: str, durations: list[int], **params: Any
) -> bytes:
    """Encode frames as an animated image of the given format."""
    buf = BytesIO()
    frames[0].save(
        buf,
        format=fmt,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        **params,
    )
    return buf.getvalue()


def animated_image_bytes(
    fmt: str, durations: list[int] = DURATIONS, loop: int | None = 0
) -> bytes:
    """Encode one solid FRAME_SIZE frame per duration as an animated image."""
    frames = [
        Image.new("RGB", FRAME_SIZE, FRAME_COLORS[i % len(FRAME_COLORS)])
        for i in range(len(durations))
    ]
    return encode_animation(
        frames, fmt, durations, **({} if loop is None else {"loop": loop})
    )


def truncated_animation_bytes(fmt: str) -> bytes:
    """An animation with its last frame cut short."""
    return animated_image_bytes(fmt)[:-40]


def growing_canvas_gif() -> bytes:
    """A 10x10 GIF whose second frame grows the canvas to 40x40."""
    parts = []
    for size in ((10, 10), (40, 40)):
        buf = BytesIO()
        Image.new("P", size).save(buf, format="GIF")
        parts.append(buf.getvalue())
    # Frames follow the header and global palette, sized alike in both files
    frames_start = 13 + 3 * 2 ** ((parts[0][10] & 0x07) + 1)
    return parts[0][:-1] + parts[1][frames_start:]


class TestIsAnimated:
    @pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
    def test_multi_frame_image(self, fmt: str):
        with Image.open(BytesIO(animated_image_bytes(fmt))) as img:
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
        pixels = len(DURATIONS) * FRAME_SIZE[0] * FRAME_SIZE[1]
        monkeypatch.setattr("utils.images.MAX_ANIMATION_PIXELS", pixels - 1)
        with Image.open(BytesIO(animated_image_bytes("GIF"))) as img:
            assert not is_animated(img)


class TestFrameDurations:
    @pytest.mark.parametrize("fmt", ["GIF", "PNG", "WEBP"])
    def test_reads_each_frame(self, fmt: str):
        with Image.open(BytesIO(animated_image_bytes(fmt))) as img:
            assert frame_durations(img) == DURATIONS
            assert img.tell() == 0

    def test_passes_each_decoded_frame(self):
        seen: list[Image.Image] = []
        with Image.open(BytesIO(animated_image_bytes("PNG"))) as img:
            frame_durations(img, lambda frame: seen.append(frame.convert("RGB")))
        assert [frame.getpixel((0, 0)) for frame in seen] == [
            (255, 0, 0),
            (0, 128, 0),
            (0, 0, 255),
        ]

    def test_still_image(self):
        buf = BytesIO()
        Image.new("RGB", (4, 4)).save(buf, format="PNG")
        with Image.open(buf) as img:
            assert frame_durations(img) is None

    @pytest.mark.parametrize("fmt", ["GIF", "PNG"])
    def test_damaged_frame(self, fmt: str):
        with Image.open(BytesIO(truncated_animation_bytes(fmt))) as img:
            assert frame_durations(img) is None
            assert img.tell() == 0

    def test_malformed_apng_frame(self):
        data = bytearray(animated_image_bytes("PNG"))
        second_fctl = data.find(b"fcTL", data.find(b"fcTL") + 4)
        data[second_fctl + 4 : second_fctl + 8] = (99).to_bytes(4, "big")
        with Image.open(BytesIO(bytes(data))) as img:
            assert frame_durations(img) is None

    def test_canvas_outgrows_pixel_budget(self, monkeypatch: pytest.MonkeyPatch):
        # Declares 2 frames of 10x10 but decodes a 40x40 second frame
        monkeypatch.setattr("utils.images.MAX_ANIMATION_PIXELS", 1000)
        with Image.open(BytesIO(growing_canvas_gif())) as img:
            assert is_animated(img)
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
