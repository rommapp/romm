"""Realistic cover and media files for `generate_test_data.py`, at a chosen fidelity.

Levels (`--image-fidelity`):
  1 mosaic     one 264x396 mosaic per rom (generate_test_data's own writer)
  2 shapes     real cover size mix, RomM's small-cover rule; debug art on flat colour
  3 weight     level 2 over texture tuned to real bytes per pixel; some JPEG in big.png

From level 2 every image carries the same debug guides: red/green/blue/white corner
pixels, named corners, percent ticks, a circle that shows stretching, and a label
naming the game and file. Each rom draws from its own random stream (seed, rom id),
so roms can be drawn in any order or in parallel and still come out the same.
"""

import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final

from PIL import Image, ImageChops, ImageDraw, ImageFont

from handler.filesystem import fs_resource_handler

# Large-cover sizes and how often each appears: the 16 most common of 134 sizes
# (97% of covers) in one library's 8,396 covers, measured 2026-10-14.
COVER_SIZES: Final[dict[tuple[int, int], int]] = {
    (600, 900): 5418,
    (680, 680): 850,
    (810, 1080): 687,
    (1024, 1024): 575,
    (441, 680): 123,
    (792, 680): 100,
    (512, 512): 88,
    (486, 680): 69,
    (496, 680): 40,
    (660, 930): 37,
    (811, 1080): 31,
    (591, 680): 30,
    (500, 450): 29,
    (481, 680): 28,
    (342, 482): 23,
    (680, 497): 20,
}
# Landscape covers are 1.8% of that library (792x680, 500x450, 680x497); seeds
# draw them more often so landscape tiles show up in any page of a gallery.
LANDSCAPE_SHARE: Final = 0.12
LANDSCAPE_SIZES: Final = {
    size: n for size, n in COVER_SIZES.items() if size[0] > size[1]
}
# Same library: ~500 of 8,897 roms have no cover, and 22% of big.png files hold JPEG bytes.
NO_COVER_SHARE: Final = 0.056
JPEG_IN_PNG_SHARE: Final = 0.22
# Noise strength for the level-3 texture, tuned so PNG output matches the measured
# spread: 2.5 / 16 / 40 give the 10th percentile / median / 90th (0.89 / 1.5 / 2.02 bytes/pixel).
NOISE_MEDIAN: Final = 16.0
NOISE_SPREAD: Final = 1.0
NOISE_RANGE: Final = (2.0, 48.0)
# Standard deviation of uniform 0-255 bytes, to scale them to a noise strength.
UNIFORM_NOISE_SPREAD: Final = 73.9

# Provisional until a media listing is measured: which media kinds a rom with
# ScreenScraper media gets, and their sizes. None means "the cover's size".
MEDIA_SIZES: Final[dict[str, tuple[int, int] | None]] = {
    "box2d": None,
    "box2d_back": None,
    "box2d_side": (80, 900),
    "box3d": (720, 1000),
    "physical": (600, 600),
    "miximage": (640, 480),
    "miximage_v2": (640, 480),
    "title_screen": (640, 480),
    "fanart": (1280, 720),
    "marquee": (800, 200),
    "logo": (600, 250),
}
SCREENSHOT_SIZE: Final = (640, 480)

# Debug art: one OKLCH hue per rom, golden-angle steps so neighbours always differ.
GOLDEN_ANGLE: Final = 137.508
BASE_LIGHTNESS, BASE_CHROMA = 0.78, 0.11
INK_LIGHTNESS, INK_CHROMA = 0.25, 0.06
# Pure colours on the exact corner pixels, so each corner can be told apart even
# when only a few pixels of it survive.
CORNER_COLOURS: Final[dict[str, tuple[int, int, int]]] = {
    "TL": (255, 0, 0),
    "TR": (0, 255, 0),
    "BL": (0, 0, 255),
    "BR": (255, 255, 255),
}
# Guides (circle, cross, ticks, boxes, corners, stats) are pure black on every rom.
GUIDE_BLACK: Final = (0, 0, 0)
CORNER_RING: Final = GUIDE_BLACK
# The stats box is black on white so it reads at a distance. Only the kind cell
# is tinted, and only for the two cover sizes, so a tile shows at a glance which
# file the client loaded.
STATS_WHITE: Final = (255, 255, 255)
KIND_CELL_COLOURS: Final[dict[str, tuple[int, int, int]]] = {
    "big": (255, 178, 120),
    "small": (120, 190, 255),
}

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class RomCaption:
    title: str = ""
    system: str = ""
    region: str = ""


@dataclass
class SeededImages:
    small: str = ""
    large: str = ""
    screenshots: list[str] = field(default_factory=list)
    # ScreenScraper metadata keys (`<kind>_path`) for the media written.
    media_paths: dict[str, str] = field(default_factory=dict)
    files_written: int = 0


def pick_cover_size(rng: random.Random) -> tuple[int, int]:
    pool = LANDSCAPE_SIZES if rng.random() < LANDSCAPE_SHARE else COVER_SIZES
    return rng.choices(list(pool), weights=list(pool.values()))[0]


def _oklch_to_srgb(lightness: float, chroma: float, hue: float) -> RGB | None:
    """sRGB for an OKLCH colour, or None when it falls outside the sRGB gamut."""
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    if any(c < -1e-4 or c > 1 + 1e-4 for c in linear):
        return None
    red, green, blue = (
        round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
        for c in (min(1.0, max(0.0, c)) for c in linear)
    )
    return red, green, blue


def _fit_oklch(lightness: float, chroma: float, hue: float) -> RGB:
    while (rgb := _oklch_to_srgb(lightness, chroma, hue)) is None:
        chroma -= 0.005
    return rgb


def rom_hue(rom_id: int) -> float:
    return (rom_id * GOLDEN_ANGLE) % 360


def rom_colors(rom_id: int) -> tuple[RGB, RGB]:
    """A rom's base and ink colours: same hue, light and dark."""
    hue = rom_hue(rom_id)
    return (
        _fit_oklch(BASE_LIGHTNESS, BASE_CHROMA, hue),
        _fit_oklch(INK_LIGHTNESS, INK_CHROMA, hue),
    )


@lru_cache(maxsize=256)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _dashed_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    dash: int,
    width: int,
    ink: RGB,
) -> None:
    x0, y0, x1, y1 = box
    for (ax, ay), (bx, by) in (
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ):
        steps = max(1, int(math.hypot(bx - ax, by - ay) // dash))
        for i in range(0, steps, 2):
            t0, t1 = i / steps, min(1.0, (i + 1) / steps)
            draw.line(
                (
                    ax + (bx - ax) * t0,
                    ay + (by - ay) * t0,
                    ax + (bx - ax) * t1,
                    ay + (by - ay) * t1,
                ),
                fill=ink,
                width=width,
            )


def _centred_box(
    width: int, height: int, ratio: tuple[int, int]
) -> tuple[float, float, float, float]:
    scale = min(width / ratio[0], height / ratio[1])
    box_w, box_h = ratio[0] * scale, ratio[1] * scale
    return (
        (width - box_w) / 2,
        (height - box_h) / 2,
        (width + box_w) / 2 - 1,
        (height + box_h) / 2 - 1,
    )


def _chord(radius: float, offset: float) -> float:
    """Width of a circle of `radius` at `offset` from its centre."""
    return 2 * math.sqrt(max(0.0, radius**2 - offset**2))


def _fitted_size(
    draw: ImageDraw.ImageDraw, texts: list[str], size: int, max_width: float
) -> int:
    """Largest font size up to `size` at which the widest of `texts` fits."""
    while (
        size > 7
        and max(draw.textlength(t, font=_font(size)) for t in texts) > max_width
    ):
        size -= 1
    return size


# The stats box is a fixed shape on the circle, the same on every tile whatever
# its values: width, height, top and column shares are fractions of the radius.
# The id column fits six digits, as ids reach 100000 at the seeder's default size.
STATS_BOX_WIDTH: Final = 1.76
STATS_BOX_HEIGHT: Final = 0.26
STATS_BOX_TOP: Final = 0.16
STATS_COLUMNS: Final = (0.245, 0.36, 0.21, 0.185)
STATS_FONT: Final = 0.105


def fact_box_cells(
    cx: float, cy: float, radius: float
) -> list[tuple[float, float, float, float]]:
    """The stats box's cell rectangles, fixed relative to the circle."""
    width, height = radius * STATS_BOX_WIDTH, radius * STATS_BOX_HEIGHT
    top = cy + radius * STATS_BOX_TOP
    x = cx - width / 2
    cells = []
    for share in STATS_COLUMNS:
        cells.append((x, top, x + width * share, top + height))
        x += width * share
    return cells


def _draw_fact_box(
    draw: ImageDraw.ImageDraw,
    cells: list[tuple[str, RGB]],
    cx: float,
    cy: float,
    radius: float,
) -> float:
    """One boxed row of (value, background) cells, black on light, fixed to the circle."""
    rects = fact_box_cells(cx, cy, radius)
    line = max(1, round(radius / 120))
    standard = max(8, round(radius * STATS_FONT))
    for (value, background), (x0, y0, x1, y1) in zip(cells, rects, strict=True):
        draw.rectangle((x0, y0, x1, y1), fill=background)
        # Only a value too long for its cell shrinks; the rest keep one size.
        size = _fitted_size(draw, [value], standard, (x1 - x0) * 0.88)
        draw.text(
            ((x0 + x1) / 2, (y0 + y1) / 2),
            value,
            fill=GUIDE_BLACK,
            font=_font(size),
            anchor="mm",
        )
    for x0, y0, _, y1 in rects[1:]:
        draw.line((x0, y0, x0, y1), fill=GUIDE_BLACK, width=line)
    left, top = rects[0][0], rects[0][1]
    right, bottom = rects[-1][2], rects[-1][3]
    draw.rectangle((left, top, right, bottom), outline=GUIDE_BLACK, width=line)
    return bottom


@lru_cache(maxsize=64)
def _fade_alpha(
    size: tuple[int, int], cx: float, cy: float, outer: float, inner: float
) -> Image.Image:
    """The ring's alpha mask; the same for every image of one size, so it is cached."""
    ring = Image.new("L", size, 0)
    ring_draw = ImageDraw.Draw(ring)
    ring_draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), fill=255)
    ring_draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=0)
    sweep = Image.new("L", size, 0)
    sweep_draw = ImageDraw.Draw(sweep)
    reach = outer + 2
    for degree in range(360):
        sweep_draw.pieslice(
            (cx - reach, cy - reach, cx + reach, cy + reach),
            start=degree - 90,
            end=degree - 89,
            fill=round(255 * (1 - degree / 359)),
        )
    alpha = Image.composite(sweep, Image.new("L", size, 255), ring)
    return ImageChops.lighter(alpha, ImageChops.invert(ring))


def _fade_ring(
    img: Image.Image, cx: float, cy: float, outer: float, inner: float
) -> Image.Image:
    """Make a ring transparent by degrees: opaque at 12 o'clock, fading clockwise to clear."""
    img.putalpha(_fade_alpha(img.size, cx, cy, outer, inner))
    return img


def draw_debug_overlay(
    img: Image.Image,
    rom_id: int,
    kind: str,
    fmt: str,
    caption: RomCaption,
    path: str = "",
    path_column: str = "",
) -> Image.Image:
    """Draw the guides that tell which game and file a tile is, and how it was cut."""
    w, h = img.size
    side = min(w, h)
    base, ink = rom_colors(rom_id)
    draw = ImageDraw.Draw(img)
    line = max(1, side // 150)

    # What a 1:1 or 2:3 tile keeps, and a circle that turns into an ellipse when stretched.
    dash = max(3, side // 40)
    _dashed_box(draw, _centred_box(w, h, (1, 1)), dash, line, GUIDE_BLACK)
    _dashed_box(draw, _centred_box(w, h, (2, 3)), dash, line, GUIDE_BLACK)
    cx, cy, radius = w / 2, h / 2, side * 0.4
    arm = side * 0.05
    draw.line((cx - arm, cy, cx + arm, cy), fill=GUIDE_BLACK, width=line)
    draw.line((cx, cy - arm, cx, cy + arm), fill=GUIDE_BLACK, width=line)

    # Percent ticks on every side tell how much was cut: long at 10%, longest at 50%.
    for pct in range(5, 100, 5):
        length = side * (0.09 if pct == 50 else 0.06 if pct % 10 == 0 else 0.035)
        x, y = w * pct / 100, h * pct / 100
        draw.line((x, 0, x, length), fill=GUIDE_BLACK, width=line)
        draw.line((x, h - 1 - length, x, h - 1), fill=GUIDE_BLACK, width=line)
        draw.line((0, y, length, y), fill=GUIDE_BLACK, width=line)
        draw.line((w - 1 - length, y, w - 1, y), fill=GUIDE_BLACK, width=line)
    draw.rectangle((0, 0, w - 1, h - 1), outline=GUIDE_BLACK, width=max(2, line * 2))

    # Named corner triangles tell which corner went missing.
    tri = side * 0.16
    corner_font = _font(max(8, round(tri * 0.3)))
    dot = max(1, side // 100)
    for name, x0, y0, dx, dy in (
        ("TL", 0, 0, 1, 1),
        ("TR", w - 1, 0, -1, 1),
        ("BL", 0, h - 1, 1, -1),
        ("BR", w - 1, h - 1, -1, -1),
    ):
        draw.polygon(
            [(x0, y0), (x0 + dx * tri, y0), (x0, y0 + dy * tri)], fill=GUIDE_BLACK
        )
        draw.text(
            (x0 + dx * tri * 0.27, y0 + dy * tri * 0.27),
            name,
            fill=base,
            font=corner_font,
            anchor="mm",
        )
        # The corner pixel itself is a pure colour, ringed in 1px black on its inner sides.
        for reach, colour in ((dot, CORNER_RING), (dot - 1, CORNER_COLOURS[name])):
            xs = sorted((x0, x0 + dx * reach))
            ys = sorted((y0, y0 + dy * reach))
            draw.rectangle((xs[0], ys[0], xs[1], ys[1]), fill=colour)

    # A band of real transparency inside the circle (2px gap, 3 strokes wide) shows
    # the page background behind the tile; the labels and circle are drawn over it
    # opaque. Where a resize or format flattens alpha the fade vanishes, and JPEG
    # files, which have no alpha, go without.
    if fmt != "JPEG":
        outer = radius - line - 2
        img = _fade_ring(img, cx, cy, outer, outer - 3 * line)
        draw = ImageDraw.Draw(img)

    # The game sits in the circle's top half, this file's facts in a box below the
    # cross (roms.id, size, kind, format), and the path on the bottom edge, so the
    # boxed stats also show which way is down. The kind (big, small, box2d,
    # fanart...) lets every kind of art share one layout. The path is where the
    # file was written; it may since have moved or changed.
    gap = side * 0.08
    margin = side * 0.05
    edge = cy - gap
    for text, relative in (
        (" · ".join(part for part in (caption.system, caption.region) if part), 0.046),
        (caption.title or f"Rom {rom_id}", 0.07),
    ):
        if not text:
            continue
        size = max(7, round(side * relative))
        size = _fitted_size(
            draw, [text], size, _chord(radius, cy - (edge - size * 1.3)) - margin
        )
        draw.text(
            (cx, edge - size * 0.65), text, fill=ink, font=_font(size), anchor="mm"
        )
        edge -= size * 1.3
    y = _draw_fact_box(
        draw,
        [
            (str(rom_id), STATS_WHITE),
            (f"{w}x{h}", STATS_WHITE),
            (kind, KIND_CELL_COLOURS.get(kind, STATS_WHITE)),
            (fmt, STATS_WHITE),
        ],
        cx,
        cy,
        radius,
    )
    # The original path runs along the bottom edge, above the ticks and between
    # the corner triangles.
    if path:
        text = f"original path: {path}"
        size = _fitted_size(
            draw, [text], max(8, round(side * 0.04)), w - 2 * tri - side * 0.06
        )
        centre = max(h - 1 - side * 0.1 - size * 0.65, y + size * 1.2)
        half = draw.textlength(text, font=_font(size)) / 2 + size * 0.4
        draw.rectangle(
            (cx - half, centre - size * 0.75, cx + half, centre + size * 0.75),
            fill=base,
        )
        draw.text((cx, centre), text, fill=ink, font=_font(size), anchor="mm")
    # Drawn last so the stretch circle always stays visible over the label.
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline=GUIDE_BLACK,
        width=line,
    )
    return img


def _noise_strength(rng: random.Random) -> float:
    low, high = NOISE_RANGE
    return min(high, max(low, rng.lognormvariate(math.log(NOISE_MEDIAN), NOISE_SPREAD)))


def make_image(
    rng: random.Random,
    size: tuple[int, int],
    fidelity: int,
    *,
    rom_id: int,
    kind: str,
    fmt: str,
    caption: RomCaption,
    path: str = "",
    path_column: str = "",
) -> Image.Image:
    """A debug picture of `size`: flat at level 2, over real-weight texture from level 3."""
    width, height = size
    base, _ = rom_colors(rom_id)
    if fidelity <= 2:
        picture = Image.new("RGB", size, base)
    else:
        blocks = Image.frombytes("RGB", (12, 18), rng.randbytes(12 * 18 * 3))
        texture = Image.blend(
            Image.linear_gradient("L").resize(size).convert("RGB"),
            blocks.resize(size, Image.Resampling.BICUBIC),
            0.7,
        )
        # Noise from `rng`, not Image.effect_noise, so `--seed` reproduces the bytes.
        noise = Image.blend(
            Image.new("L", size, 128),
            Image.frombytes("L", size, rng.randbytes(width * height)),
            _noise_strength(rng) / UNIFORM_NOISE_SPREAD,
        )
        picture = Image.blend(
            Image.new("RGB", size, base),
            Image.blend(texture, noise.convert("RGB"), 0.5),
            0.55,
        )
    return draw_debug_overlay(picture, rom_id, kind, fmt, caption, path, path_column)


def rom_rng(seed: int, rom_id: int) -> random.Random:
    """A rom's own random stream: the same for a (seed, rom id) pair in any process."""
    return random.Random(
        seed * 1_000_003 + rom_id * 0x9E3779B1
    )  # nosec B311 - fake data


def rom_fidelity(fidelity: int, rom_id: int, weighted_every: int) -> int:
    """Level 2 libraries draw every `weighted_every`-th rom id at level 3, for byte work."""
    if fidelity == 2 and weighted_every and rom_id % weighted_every == 0:
        return 3
    return fidelity


@dataclass(frozen=True)
class RomImageJob:
    """Everything needed to draw one rom's images, in this process or a worker."""

    resources_base: str
    seed: int
    platform_id: int
    rom_id: int
    fidelity: int
    n_screenshots: int
    with_media: bool
    caption: RomCaption = RomCaption()


def _has_cover(rng: random.Random) -> bool:
    return rng.random() >= NO_COVER_SHARE


def plan_rom_images(job: RomImageJob) -> SeededImages:
    """The paths a job will write, without drawing anything."""
    if not _has_cover(rom_rng(job.seed, job.rom_id)):
        return SeededImages()
    rel = f"roms/{job.platform_id}/{job.rom_id}"
    planned = SeededImages(
        large=f"{rel}/cover/big.png",
        small=f"{rel}/cover/small.png",
        screenshots=[
            f"{rel}/screenshots/{index}.jpg" for index in range(job.n_screenshots)
        ],
        media_paths=(
            {f"{kind}_path": f"{rel}/{kind}/{kind}.png" for kind in MEDIA_SIZES}
            if job.with_media
            else {}
        ),
    )
    planned.files_written = 2 + job.n_screenshots + len(planned.media_paths)
    return planned


def _save(image: Image.Image, path: Path, fmt: str, fidelity: int) -> None:
    if fmt == "JPEG":
        image.save(path, "JPEG", quality=90)
    elif fidelity <= 2:
        # Lossless either way; level 2 trades file size for speed, level 3 keeps
        # Pillow's default so its bytes per pixel stay calibrated.
        image.save(path, "PNG", compress_level=1)
    else:
        image.save(path, "PNG")


def draw_rom_images(job: RomImageJob) -> SeededImages:
    """Write one rom's covers, screenshots and (optionally) media in RomM's layout."""
    rng = rom_rng(job.seed, job.rom_id)
    if not _has_cover(rng):
        return SeededImages()
    planned = plan_rom_images(job)
    rel = f"roms/{job.platform_id}/{job.rom_id}"

    def draw(
        size: tuple[int, int], kind: str, fmt: str, path: str, path_column: str
    ) -> Image.Image:
        return make_image(
            rng,
            size,
            job.fidelity,
            rom_id=job.rom_id,
            kind=kind,
            fmt=fmt,
            caption=job.caption,
            path=path,
            path_column=path_column,
        )

    cover_size = pick_cover_size(rng)
    cover_dir = Path(job.resources_base, rel, "cover")
    cover_dir.mkdir(parents=True, exist_ok=True)
    big = cover_dir / "big.png"
    # Downloads keep the provider's bytes, so some big.png files are JPEG inside.
    big_format = (
        "JPEG" if job.fidelity >= 3 and rng.random() < JPEG_IN_PNG_SHARE else "PNG"
    )
    _save(
        draw(cover_size, "big", big_format, planned.large, "roms.path_cover_l"),
        big,
        big_format,
        job.fidelity,
    )
    # RomM's own rule picks the small size; the picture is redrawn at it so its
    # guides stay sharp and its label says "small".
    small = cover_dir / "small.png"
    with Image.open(big) as cover:
        fs_resource_handler.resize_cover_to_small(cover, save_path=str(small))
    with Image.open(small) as resized:
        small_size = resized.size
    _save(
        draw(small_size, "small", "PNG", planned.small, "roms.path_cover_s"),
        small,
        "PNG",
        job.fidelity,
    )

    if planned.screenshots:
        shot_dir = Path(job.resources_base, rel, "screenshots")
        shot_dir.mkdir(parents=True, exist_ok=True)
        for index, shot in enumerate(planned.screenshots):
            _save(
                draw(
                    SCREENSHOT_SIZE,
                    f"screenshot {index}",
                    "JPEG",
                    shot,
                    "roms.path_screenshots",
                ),
                shot_dir / f"{index}.jpg",
                "JPEG",
                job.fidelity,
            )

    for kind, size in MEDIA_SIZES.items() if planned.media_paths else ():
        media_dir = Path(job.resources_base, rel, kind)
        media_dir.mkdir(parents=True, exist_ok=True)
        _save(
            draw(
                size or cover_size,
                kind,
                "PNG",
                planned.media_paths[f"{kind}_path"],
                f"roms.ss_metadata.{kind}_path",
            ),
            media_dir / f"{kind}.png",
            "PNG",
            job.fidelity,
        )
    return planned
