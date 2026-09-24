from collections.abc import Callable

from PIL import Image, ImageSequence

# Multi-frame formats browsers play as animations (MPO/TIFF pages are not)
ANIMATED_FORMATS = frozenset({"GIF", "PNG", "WEBP"})

# Pixels decoded across all frames past which an animation keeps only its
# first frame, since re-encoding one holds every frame in memory.
MAX_ANIMATION_PIXELS = 100_000_000

# Largest loop count a WebP animation can store
_MAX_WEBP_LOOP = 0xFFFF


def is_animated(img: Image.Image) -> bool:
    """True for a multi-frame image that browsers play as an animation."""
    n_frames = getattr(img, "n_frames", 1)
    return (
        img.format in ANIMATED_FORMATS
        and 1 < n_frames
        and n_frames * img.width * img.height <= MAX_ANIMATION_PIXELS
    )


def frame_durations(
    img: Image.Image, on_frame: Callable[[Image.Image], None] | None = None
) -> list[float] | None:
    """Display time in milliseconds of each frame, leaving img on its first frame.

    Args:
        on_frame: Called with each frame once decoded.
    Returns:
        None for a still image, or an animation that fails to decode or
        outgrows MAX_ANIMATION_PIXELS.
    """
    if not is_animated(img):
        return None

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
            if on_frame:
                on_frame(frame)
            durations.append(frame.info.get("duration", 0))
    except OSError, SyntaxError, ValueError, Image.DecompressionBombError:
        return None
    finally:
        img.seek(0)
    return durations


def webp_loop(img: Image.Image) -> int:
    """WebP loop count (0 is forever) that plays img as often as browsers do."""
    loop = img.info.get("loop")
    if img.format != "GIF":
        return loop or 0
    # A GIF counts replays after the first play, and plays once without a count
    if loop is None:
        return 1
    return min(loop + 1, _MAX_WEBP_LOOP) if loop else 0
