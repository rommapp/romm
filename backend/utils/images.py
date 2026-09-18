from typing import Any

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import Blend, Disposal

# Multi-frame formats browsers play as animations (MPO/TIFF pages are not)
ANIMATED_FORMATS = frozenset({"GIF", "PNG", "WEBP"})

# Pixels decoded across all frames past which an animation keeps only its
# first frame, since re-encoding one holds every frame in memory.
MAX_ANIMATION_PIXELS = 100_000_000

# Largest loop count a WebP animation can store
_MAX_WEBP_LOOP = 0xFFFF


def is_animated(img: Image.Image) -> bool:
    """True for a multi-frame image that browsers play as an animation."""
    return (
        img.format in ANIMATED_FORMATS
        and bool(getattr(img, "is_animated", False))
        and getattr(img, "n_frames", 1) * img.width * img.height <= MAX_ANIMATION_PIXELS
    )


def frame_durations(img: Image.Image) -> list[float] | None:
    """Display time in milliseconds of each frame, leaving img on its first frame.

    Returns:
        None when a frame fails to decode or the frames outgrow MAX_ANIMATION_PIXELS.
    """
    durations: list[float] = []
    pixels = 0
    try:
        for frame in ImageSequence.Iterator(img):
            # Counted per frame since a GIF canvas can grow mid-animation
            pixels += frame.width * frame.height
            if pixels > MAX_ANIMATION_PIXELS:
                return None
            # WebP only fills in a frame's duration once the frame is decoded
            frame.load()
            durations.append(frame.info.get("duration", 0))
    except OSError, SyntaxError, ValueError, Image.DecompressionBombError:
        return None
    finally:
        img.seek(0)
    return durations


def reencode_params(img: Image.Image) -> dict[str, Any]:
    """save() params that re-encode img's decoded frames in its own format."""
    params: dict[str, Any] = {}
    if "loop" in img.info:
        params["loop"] = img.info["loop"]
    # Pillow decodes frames fully composited, so each must replace the last
    if img.format == "GIF":
        params["disposal"] = 2
    elif img.format == "PNG":
        params.update(
            disposal=Disposal.OP_NONE, blend=Blend.OP_SOURCE, default_image=False
        )
    return params


def webp_loop(img: Image.Image) -> int:
    """WebP loop count (0 is forever) that plays img as often as browsers do."""
    loop = img.info.get("loop")
    if img.format != "GIF":
        return loop or 0
    # A GIF counts replays after the first play, and plays once without a count
    if loop is None:
        return 1
    return min(loop + 1, _MAX_WEBP_LOOP) if loop else 0
