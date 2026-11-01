import pytest

from utils.media_types import guess_media_file_type, is_allowed_image_file


@pytest.mark.parametrize(
    ("file_name", "mime"),
    [
        ("cover.avif", "image/avif"),
        ("cover.AVIF", "image/avif"),
        ("cover.jxl", "image/jxl"),
        ("cover.JXL", "image/jxl"),
    ],
)
def test_modern_image_formats_are_served_inline(file_name: str, mime: str):
    assert is_allowed_image_file(file_name)
    assert guess_media_file_type(file_name) == mime


def test_unknown_extension_is_not_an_image():
    assert not is_allowed_image_file("cover.psd")
