from PIL import Image, ImageSequence

# Multi-frame formats browsers play as animations (MPO/TIFF pages are not)
ANIMATED_FORMATS = frozenset({"GIF", "PNG", "WEBP"})


def is_animated(img: Image.Image) -> bool:
    """True for a multi-frame image that browsers play as an animation."""
    return img.format in ANIMATED_FORMATS and bool(getattr(img, "is_animated", False))


def frame_durations(img: Image.Image) -> list[int]:
    """Display time in milliseconds of each frame of an animated image."""
    durations = []
    for frame in ImageSequence.Iterator(img):
        # WebP only fills in a frame's duration once the frame is decoded
        frame.load()
        durations.append(frame.info.get("duration", 0))
    return durations
