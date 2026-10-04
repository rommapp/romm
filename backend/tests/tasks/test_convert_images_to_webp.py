from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from pytest_mock import MockerFixture
from tests.utils.test_images import (
    DURATIONS,
    animated_image_bytes,
    truncated_animation_bytes,
)

from tasks import tasks as tasks_module
from tasks.scheduled.convert_images_to_webp import (
    ConvertImagesToWebPTask,
    ImageConverter,
)
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
            assert getattr(img, "n_frames", 1) == 1

    # Providers serve WebP under any name, and covers are stored as big.png
    @pytest.mark.parametrize("name", ["big.png", "big.webp"])
    def test_keeps_webp_source_bytes(
        self, converter: ImageConverter, tmp_path: Path, name: str
    ):
        data = animated_image_bytes("WEBP")
        (tmp_path / name).write_bytes(data)

        assert converter.convert_to_webp(tmp_path / name, force=True)

        assert (tmp_path / "big.webp").read_bytes() == data

    @pytest.mark.parametrize(
        ("mode", "color", "expected_mode"),
        [
            ("LA", (128, 0), "RGBA"),
            ("L", 128, "RGB"),
            ("CMYK", (0, 255, 255, 0), "RGB"),
        ],
    )
    def test_converts_the_color_mode_webp_cannot_hold(
        self,
        converter: ImageConverter,
        tmp_path: Path,
        mode: str,
        color: int | tuple[int, ...],
        expected_mode: str,
    ):
        source = tmp_path / "big.tiff"
        Image.new(mode, (4, 4), color).save(source)

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            assert img.mode == expected_mode

    def test_keeps_a_palette_image_transparent(
        self, converter: ImageConverter, tmp_path: Path
    ):
        source = tmp_path / "big.png"
        palette = Image.new("P", (4, 4), 0)
        palette.putpalette([255, 0, 0, 0, 0, 255])
        palette.info["transparency"] = 0
        palette.save(source, transparency=0)

        assert converter.convert_to_webp(source)

        with Image.open(tmp_path / "big.webp") as img:
            pixel = img.getpixel((0, 0))
        assert isinstance(pixel, tuple)
        assert pixel[3] == 0

    def test_leaves_an_existing_webp_alone(
        self, converter: ImageConverter, tmp_path: Path
    ):
        source = tmp_path / "big.png"
        Image.new("RGB", (4, 4), "red").save(source)
        (tmp_path / "big.webp").write_bytes(b"already converted")

        assert converter.convert_to_webp(source)

        assert (tmp_path / "big.webp").read_bytes() == b"already converted"

    def test_keeps_the_original(self, converter: ImageConverter, tmp_path: Path):
        source = tmp_path / "big.png"
        Image.new("RGB", (4, 4), "red").save(source)
        original = source.read_bytes()

        converter.convert_to_webp(source)

        assert source.read_bytes() == original

    def test_reports_an_unreadable_image(
        self, converter: ImageConverter, tmp_path: Path
    ):
        source = tmp_path / "big.png"
        source.write_bytes(b"not an image")

        assert not converter.convert_to_webp(source)
        assert not (tmp_path / "big.webp").exists()


def _cover(root: Path, rom: str, name: str = "big.png") -> Path:
    path = root / "roms" / "gba" / rom / "cover" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    jpeg = path.suffix.lower() in (".jpg", ".jpeg")
    Image.new("RGB", (4, 4), "red").save(path, format="JPEG" if jpeg else "PNG")
    return path


class TestConvertImagesToWebPTask:
    @pytest.fixture
    def task(self, tmp_path: Path) -> ConvertImagesToWebPTask:
        task = ConvertImagesToWebPTask()
        task.resources_path = tmp_path
        return task

    @pytest.fixture
    def job_meta(self, mocker: MockerFixture) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        mocker.patch.object(tasks_module, "update_job_meta", side_effect=updates.append)
        return updates

    def test_finds_unconverted_cover_images_only(
        self, task: ConvertImagesToWebPTask, tmp_path: Path
    ):
        wanted = [_cover(tmp_path, "zelda"), _cover(tmp_path, "metroid", "small.jpg")]
        _cover(tmp_path, "mario")
        (tmp_path / "roms" / "gba" / "mario" / "cover" / "big.webp").write_bytes(b"")
        (tmp_path / "roms" / "gba" / "zelda" / "cover" / "notes.txt").write_text("")
        (tmp_path / "roms" / "gba" / "zelda" / "cover" / "small.webp").write_bytes(b"")
        screenshot = tmp_path / "roms" / "gba" / "zelda" / "screenshots" / "1.png"
        screenshot.parent.mkdir(parents=True)
        Image.new("RGB", (4, 4)).save(screenshot)
        (tmp_path / "roms" / "gba" / "zelda" / "cover" / "link.png").symlink_to(
            screenshot
        )

        assert task._find_convertible_images() == sorted(wanted)

    def test_a_missing_resources_folder_has_nothing_to_convert(
        self, task: ConvertImagesToWebPTask, tmp_path: Path
    ):
        task.resources_path = tmp_path / "missing"

        assert task._find_convertible_images() == []

    async def test_run_converts_every_cover_and_reports_the_counts(
        self,
        task: ConvertImagesToWebPTask,
        tmp_path: Path,
        job_meta: list[dict[str, Any]],
    ):
        covers = [_cover(tmp_path, f"rom{i}") for i in range(12)]

        result = await task.run()

        assert result == {"processed": 12, "errors": 0, "total": 12}
        assert all(cover.with_suffix(".webp").exists() for cover in covers)
        assert all(cover.exists() for cover in covers)
        assert job_meta == [
            {"conversion_stats": {"processed": done, "errors": 0, "total": 12}}
            for done in range(1, 13)
        ]

    async def test_run_counts_a_broken_image_and_carries_on(
        self,
        task: ConvertImagesToWebPTask,
        tmp_path: Path,
        job_meta: list[dict[str, Any]],
    ):
        good = _cover(tmp_path, "good")
        broken = _cover(tmp_path, "broken")
        broken.write_bytes(b"not an image")

        result = await task.run()

        assert result == {"processed": 1, "errors": 1, "total": 2}
        assert good.with_suffix(".webp").exists()
        assert not broken.with_suffix(".webp").exists()
        [error] = task.errors
        assert error.startswith(f"Invalid image file: {broken} - ")
        assert job_meta == [
            {"conversion_stats": {"processed": 0, "errors": 1, "total": 2}},
            {"conversion_stats": {"processed": 1, "errors": 1, "total": 2}},
        ]

    async def test_run_counts_a_failed_conversion(
        self,
        task: ConvertImagesToWebPTask,
        tmp_path: Path,
        job_meta: list[dict[str, Any]],
        mocker: MockerFixture,
    ):
        cover = _cover(tmp_path, "zelda")
        mocker.patch.object(task.converter, "convert_to_webp", return_value=False)

        result = await task.run()

        assert result == {"processed": 0, "errors": 1, "total": 1}
        assert task.errors == [f"Conversion failed: {cover}"]
        assert job_meta == [{"conversion_stats": result}]

    async def test_run_counts_an_unexpected_error(
        self,
        task: ConvertImagesToWebPTask,
        tmp_path: Path,
        job_meta: list[dict[str, Any]],
        mocker: MockerFixture,
    ):
        cover = _cover(tmp_path, "zelda")
        mocker.patch.object(
            task.converter, "convert_to_webp", side_effect=RuntimeError("boom")
        )

        result = await task.run()

        assert result == {"processed": 0, "errors": 1, "total": 1}
        assert task.errors == [f"Unexpected error: {cover} - boom"]
        assert job_meta == [{"conversion_stats": result}]

    async def test_run_with_nothing_to_convert(
        self, task: ConvertImagesToWebPTask, job_meta: list[dict[str, Any]]
    ):
        result = await task.run()

        assert result == {"processed": 0, "errors": 0, "total": 0}
        assert job_meta == [{"conversion_stats": result}]

    async def test_a_second_run_starts_its_counts_from_zero(
        self,
        task: ConvertImagesToWebPTask,
        tmp_path: Path,
        job_meta: list[dict[str, Any]],
    ):
        _cover(tmp_path, "zelda")
        await task.run()
        _cover(tmp_path, "metroid")

        result = await task.run()

        assert result == {"processed": 1, "errors": 0, "total": 1}
