import io
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest
from PIL import Image
from tools import seed_images
from tools.seed_images import (
    CORNER_COLOURS,
    CORNER_RING,
    COVER_SIZES,
    LANDSCAPE_SHARE,
    LANDSCAPE_SIZES,
    MEDIA_SIZES,
    NO_COVER_SHARE,
    RomCaption,
    RomImageJob,
    SeededImages,
    draw_rom_images,
    fact_box_cells,
    make_image,
    pick_cover_size,
    plan_rom_images,
    rom_colors,
    rom_fidelity,
    rom_hue,
    rom_rng,
)

from handler.filesystem import fs_resource_handler

CAPTION = RomCaption("Neon Harbor Racing", "Super Nintendo", "Japan")


def _picture(seed: int, size: tuple[int, int], fidelity: int) -> Image.Image:
    return make_image(
        random.Random(seed),
        size,
        fidelity,
        rom_id=42,
        kind="big",
        fmt="PNG",
        caption=CAPTION,
        path="roms/9/42/cover/big.png",
        path_column="roms.path_cover_l",
    )


def _job(
    root: Path,
    *,
    fidelity: int,
    seed: int = 0,
    rom_id: int = 42,
    with_media: bool = True,
) -> RomImageJob:
    # Skip seeds whose first draw lands in NO_COVER_SHARE, so the rom gets a cover.
    while rom_rng(seed, rom_id).random() < NO_COVER_SHARE:
        seed += 1
    return RomImageJob(
        resources_base=str(root),
        seed=seed,
        platform_id=9,
        rom_id=rom_id,
        fidelity=fidelity,
        n_screenshots=2,
        with_media=with_media,
        caption=CAPTION,
    )


def _seed(root: Path, **job_args: int | bool) -> SeededImages:
    return draw_rom_images(_job(root, **job_args))  # type: ignore[arg-type]


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_cover_sizes_follow_the_measured_mix_with_more_landscape() -> None:
    rng = random.Random(1)
    drawn = Counter(pick_cover_size(rng) for _ in range(20_000))
    total = sum(COVER_SIZES.values())
    portrait_and_square = 1 - LANDSCAPE_SHARE
    assert drawn[(600, 900)] / 20_000 == pytest.approx(
        portrait_and_square * 5418 / total, abs=0.02
    )
    landscape = sum(n for (w, h), n in drawn.items() if w > h) / 20_000
    assert landscape == pytest.approx(
        LANDSCAPE_SHARE + portrait_and_square * sum(LANDSCAPE_SIZES.values()) / total,
        abs=0.01,
    )
    assert set(drawn) <= set(COVER_SIZES)


def test_small_cover_follows_romms_resize_rule(tmp_path: Path) -> None:
    seeded = _seed(tmp_path, fidelity=2)

    with Image.open(tmp_path / seeded.large) as big:
        expected = tmp_path / "expected.png"
        fs_resource_handler.resize_cover_to_small(big, save_path=str(expected))
    with Image.open(tmp_path / seeded.small) as small, Image.open(expected) as rule:
        assert small.size == rule.size


def test_media_files_match_their_metadata_paths(tmp_path: Path) -> None:
    seeded = _seed(tmp_path, fidelity=2)

    assert set(seeded.media_paths) == {f"{kind}_path" for kind in MEDIA_SIZES}
    for path in seeded.media_paths.values():
        assert (tmp_path / path).is_file()
    assert seeded.files_written == 2 + 2 + len(MEDIA_SIZES)


def test_without_media_only_covers_and_screenshots_are_written(tmp_path: Path) -> None:
    seeded = _seed(tmp_path, fidelity=2, with_media=False)

    assert seeded.media_paths == {}
    folders = {p.name for p in (tmp_path / "roms/9/42").iterdir()}
    assert folders == {"cover", "screenshots"}


@pytest.mark.parametrize(
    "strength,measured",
    # Measured PNG covers: 10th percentile, median and 90th, in bytes per pixel.
    [(2.5, 0.89), (16.0, 1.5), (40.0, 2.02)],
)
def test_weight_level_noise_maps_to_measured_bytes_per_pixel(
    monkeypatch: pytest.MonkeyPatch, strength: float, measured: float
) -> None:
    monkeypatch.setattr(seed_images, "_noise_strength", lambda rng: strength)
    buffer = io.BytesIO()
    _picture(0, (600, 900), 3).save(buffer, "PNG")
    assert len(buffer.getvalue()) / (600 * 900) == pytest.approx(measured, rel=0.15)


def test_shapes_level_stays_small() -> None:
    buffer = io.BytesIO()
    _picture(0, (600, 900), 2).save(buffer, "PNG")
    assert len(buffer.getvalue()) < 50_000


def test_neighbouring_roms_get_distinct_in_gamut_colours() -> None:
    for rom_id in range(1, 200):
        gap = abs(rom_hue(rom_id) - rom_hue(rom_id + 1)) % 360
        assert min(gap, 360 - gap) >= 30
        base, ink = rom_colors(rom_id)
        assert all(0 <= channel <= 255 for channel in (*base, *ink))
        assert sum(base) > sum(ink) + 200


@pytest.mark.parametrize("size", [(600, 900), (204, 204), (800, 200)])
def test_each_corner_pixel_has_its_own_colour_ringed_in_black(
    size: tuple[int, int],
) -> None:
    picture = _picture(0, size, 2).convert("RGB")
    w, h = size
    dot = max(1, min(size) // 100)
    corners = {
        "TL": (0, 0, 1, 1),
        "TR": (w - 1, 0, -1, 1),
        "BL": (0, h - 1, 1, -1),
        "BR": (w - 1, h - 1, -1, -1),
    }
    for name, (x, y, dx, dy) in corners.items():
        colour = CORNER_COLOURS[name]
        assert picture.getpixel((x, y)) == colour
        assert picture.getpixel((x + dx * (dot - 1), y + dy * (dot - 1))) == colour
        assert picture.getpixel((x + dx * dot, y)) == CORNER_RING
        assert picture.getpixel((x, y + dy * dot)) == CORNER_RING


def test_the_same_seed_writes_the_same_bytes(tmp_path: Path) -> None:
    first = _seed(tmp_path / "a", fidelity=3, seed=3)
    second = _seed(tmp_path / "b", fidelity=3, seed=3)

    assert first == second
    for path in [first.large, *first.screenshots, *first.media_paths.values()]:
        assert (tmp_path / "a" / path).read_bytes() == (
            tmp_path / "b" / path
        ).read_bytes()


def _opacity(alpha: Image.Image, xy: tuple[int, int]) -> int:
    value = alpha.getpixel(xy)
    assert isinstance(value, int)
    return value


def test_png_gets_a_ring_fading_to_transparent_and_jpeg_stays_opaque() -> None:
    png = _picture(0, (600, 900), 2)
    alpha = png.getchannel("A")
    radius, line = 600 * 0.4, 600 // 150
    middle = radius - line - 2 - 1.5 * line
    # Just clockwise of 12 o'clock is opaque, just anticlockwise is clear.
    assert _opacity(alpha, (300 + 6, round(450 - middle))) > 240
    assert _opacity(alpha, (300 - 6, round(450 - middle))) < 15
    assert _opacity(alpha, (300, 450)) == 255
    jpeg = make_image(
        random.Random(0),
        (600, 900),
        2,
        rom_id=42,
        kind="big",
        fmt="JPEG",
        caption=CAPTION,
    )
    assert jpeg.mode == "RGB"


def test_stats_box_is_fixed_to_the_circle() -> None:
    small = fact_box_cells(120, 180, 96)
    big = fact_box_cells(300, 450, 240)
    scale = 240 / 96
    for (a0, b0, a1, b1), (c0, d0, c1, d1) in zip(small, big, strict=True):
        assert (c1 - c0) == pytest.approx((a1 - a0) * scale)
        assert (d1 - d0) == pytest.approx((b1 - b0) * scale)
        assert (d0 - 450) == pytest.approx((b0 - 180) * scale)
    assert small[0][0] - 120 == pytest.approx(120 - small[-1][2])


def test_a_roms_stream_depends_only_on_seed_and_id() -> None:
    assert rom_rng(5, 42).random() == rom_rng(5, 42).random()
    assert rom_rng(5, 42).random() != rom_rng(5, 43).random()
    assert rom_rng(5, 42).random() != rom_rng(6, 42).random()


def test_the_plan_names_exactly_the_files_drawn(tmp_path: Path) -> None:
    job = _job(tmp_path, fidelity=2)
    planned = plan_rom_images(job)

    drawn = draw_rom_images(job)

    assert planned == drawn
    expected = {planned.large, planned.small, *planned.screenshots}
    assert expected | set(planned.media_paths.values()) == set(_files(tmp_path))
    assert planned.files_written == len(_files(tmp_path))


def test_workers_write_the_same_bytes_as_one_process(tmp_path: Path) -> None:
    jobs = [
        _job(tmp_path / "inline", fidelity=2, rom_id=rom_id) for rom_id in range(10, 16)
    ]
    for job in jobs:
        draw_rom_images(job)
    pooled = [
        RomImageJob(**{**job.__dict__, "resources_base": str(tmp_path / "pool")})
        for job in jobs
    ]
    with ProcessPoolExecutor(2) as pool:
        list(pool.map(draw_rom_images, pooled))

    assert _files(tmp_path / "inline") == _files(tmp_path / "pool")


def test_level_two_draws_every_nth_rom_at_level_three() -> None:
    assert [rom_fidelity(2, rom_id, 10) for rom_id in (9, 10, 11, 20)] == [2, 3, 2, 3]
    assert rom_fidelity(2, 10, 0) == 2
    assert rom_fidelity(3, 11, 10) == 3


def test_media_off_writes_no_media_and_no_metadata_paths(tmp_path: Path) -> None:
    seeded = _seed(tmp_path, fidelity=2, with_media=False)

    assert seeded.media_paths == {}
    kinds = {Path(path).parts[3] for path in _files(tmp_path)}
    assert kinds <= {"cover", "screenshots"}


def test_both_tiers_draw_the_same_guides() -> None:
    flat = _picture(0, (600, 900), 2).convert("RGB")
    weighted = _picture(0, (600, 900), 3).convert("RGB")
    radius = 600 * 0.4
    points = [
        (0, 0),  # corner dot
        (599, 899),
        (1, 450),  # border
        (round(300 - radius) + 1, 450),  # circle
        (300, 450),  # cross
    ]
    cells = fact_box_cells(300, 450, radius)
    points += [(round(x0) + 3, round((y0 + y1) / 2)) for x0, y0, _, y1 in cells]
    for xy in points:
        assert flat.getpixel(xy) == weighted.getpixel(xy), xy
