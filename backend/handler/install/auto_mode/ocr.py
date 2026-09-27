"""Tesseract wrapper: image in, positioned words out."""

from __future__ import annotations

import io
import subprocess
from typing import Literal

from PIL import Image, ImageFilter, ImageOps

from config import INSTALL_AUTO_OCR_DEEP_LANGS
from logger.logger import log

from .matcher import Word

OCR_TIMEOUT = 30

# A UI label is rarely plain dark-on-light: "light" catches a bright label on
# a dark background (a white tile caption); "edge" catches everything else a
# brightness threshold misses (a mid-brightness "ghost button" outline drawn
# over artwork, or text on a solid colored tile) by reading outlines instead
# of absolute pixel value, regardless of what is on either side of them.
Mode = Literal["plain", "light", "edge"]

LIGHT_TEXT_THRESHOLD = 170
EDGE_THRESHOLD = 28

# Added to every word's block id, per mode: three independent tesseract calls
# on the same image can otherwise reuse the same (block, par, line) tuple for
# unrelated text, and combining their words would merge them into one bogus
# multi-word "line" (see matcher._group_lines) instead of keeping them apart.
_MODE_TAG: dict[Mode, int] = {"plain": 0, "light": 100_000, "edge": 200_000}


def _preprocess(image: Image.Image, mode: Mode) -> Image.Image:
    gray = image.convert("L")
    if mode == "light":
        return gray.point(lambda p: 0 if p > LIGHT_TEXT_THRESHOLD else 255)
    if mode == "edge":
        edges = ImageOps.autocontrast(gray).filter(ImageFilter.FIND_EDGES)
        return ImageOps.invert(edges.point(lambda p: 255 if p > EDGE_THRESHOLD else 0))
    return ImageOps.autocontrast(gray)


def upscale_factor(width: int, height: int) -> int:
    """Installer text is ~9pt and tesseract misreads it below ~4x, so small
    crops (a lone dialog) get more magnification than a full screen."""
    longest = max(width, height)
    if longest <= 700:
        return 4
    if longest <= 1100:
        return 3
    return 2


def ocr_words(
    image: Image.Image,
    langs: str = INSTALL_AUTO_OCR_DEEP_LANGS,
    mode: Mode = "plain",
) -> list[Word]:
    """OCR ``image`` and return words in the image's own pixel coordinates."""
    gray = _preprocess(image, mode)
    scale = upscale_factor(gray.width, gray.height)
    # An edge mask is a thin, aliased line; BICUBIC keeps a small glyph's
    # stroke a readable shape at 3-4x, where LANCZOS's ringing breaks it up.
    resample = Image.BICUBIC if mode == "edge" else Image.LANCZOS
    big = gray.resize((gray.width * scale, gray.height * scale), resample)
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", langs, "--psm", "11", "tsv"],
            input=buf.getvalue(),
            capture_output=True,
            timeout=OCR_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning(f"Install auto mode: tesseract failed: {e}")
        return []
    if result.returncode != 0:
        log.warning(
            "Install auto mode: tesseract exited with "
            f"{result.returncode}: {result.stderr.decode(errors='replace')[:200]}"
        )
    words = parse_tsv(result.stdout.decode("utf-8", errors="replace"), scale)
    tag = _MODE_TAG[mode]
    if tag:
        words = [
            Word(
                w.text,
                w.left,
                w.top,
                w.width,
                w.height,
                w.conf,
                (w.line_id[0] + tag, w.line_id[1], w.line_id[2]),
            )
            for w in words
        ]
    return words


def parse_tsv(tsv: str, scale: int = 1) -> list[Word]:
    words: list[Word] = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5":
            continue
        text = cols[11].strip()
        if not text:
            continue
        try:
            block, par, line = int(cols[2]), int(cols[3]), int(cols[4])
            left, top, width, height = (int(c) // scale for c in cols[6:10])
            conf = float(cols[10])
        except ValueError:
            continue
        words.append(Word(text, left, top, width, height, conf, (block, par, line)))
    return words
