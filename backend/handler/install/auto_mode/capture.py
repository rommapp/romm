"""Screenshot and input on the sandbox's Xvfb display."""

from __future__ import annotations

import os
import subprocess
import time

from PIL import Image, ImageGrab

from logger.logger import log

# Kept around the active window so a wrongly reported frame offset still
# leaves its buttons inside the crop.
WINDOW_PAD = 60
MIN_WINDOW_SIDE = 80
XDOTOOL_TIMEOUT = 5
FOCUS_CLICK_SETTLE = 0.5
MOVE_CANCEL_SETTLE = 0.3


def _xdotool(display: str, *args: str) -> str:
    try:
        result = subprocess.run(
            ["xdotool", *args],
            env={**os.environ, "DISPLAY": display},
            capture_output=True,
            text=True,
            timeout=XDOTOOL_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


_capture_failing = False


def grab_screen(display: str) -> Image.Image | None:
    global _capture_failing
    try:
        image = ImageGrab.grab(xdisplay=display)
    except Exception as e:  # noqa: BLE001 - X server gone or not ready yet
        # Once per streak: the display vanishes when the installer exits.
        if not _capture_failing:
            log.warning(f"Install auto mode: cannot capture display {display}: {e}")
        _capture_failing = True
        return None
    _capture_failing = False
    return image


def active_window_box(
    display: str, screen: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Padded box of the focused window, or the whole screen when unknown."""
    out = _xdotool(display, "getactivewindow", "getwindowgeometry", "--shell")
    dims = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    try:
        x, y, w, h = (int(dims[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
    except (KeyError, ValueError):
        return 0, 0, screen[0], screen[1]
    if w < MIN_WINDOW_SIDE or h < MIN_WINDOW_SIDE:
        return 0, 0, screen[0], screen[1]
    return (
        max(0, x - WINDOW_PAD),
        max(0, y - WINDOW_PAD),
        min(screen[0], x + w + WINDOW_PAD),
        min(screen[1], y + h + WINDOW_PAD),
    )


# Window-manager furniture: never the installer's own area.
_CHROME_NAMES = frozenset(
    {
        "IceTopWin",
        "IceBottom",
        "IceEdge",
        "IceRootProxy",
        "YXTrayProxy",
        "Default IME",
        "Input",
        "WindowList",
        "TaskBar",
        "TaskBarFrame",
        "ShowWindowList",
        "TaskPane",
        "TrayPane",
    }
)
# Wine keeps 1x1 helper windows (some even named like the installer) that
# cannot take focus; the visible installer is always bigger than this.
_MIN_WINDOW_AREA = 100 * 100

Rect = tuple[int, int, int, int]  # x, y, width, height


def pick_main_window(windows: list[tuple[str, str, Rect]]) -> Rect | None:
    """Area of the installer among (id, name, rect) candidates: the largest
    visible window that is not window-manager furniture or a tiny helper.
    IceWM's frame around the installer counts: it has the same rect."""
    usable = [
        rect
        for _, name, rect in windows
        if name not in _CHROME_NAMES
        and not name.startswith("IceWM ")
        and rect[2] * rect[3] >= _MIN_WINDOW_AREA
    ]
    return max(usable, key=lambda r: r[2] * r[3]) if usable else None


def _windows(display: str) -> list[tuple[str, str, Rect]]:
    found = []
    for wid in _xdotool(display, "search", "--onlyvisible", "--name", ".").split():
        name = _xdotool(display, "getwindowname", wid).strip()
        geometry = _xdotool(display, "getwindowgeometry", "--shell", wid)
        dims = dict(line.split("=", 1) for line in geometry.splitlines() if "=" in line)
        try:
            rect = tuple(int(dims[k]) for k in ("X", "Y", "WIDTH", "HEIGHT"))
        except (KeyError, ValueError):
            continue
        found.append((wid, name, rect))
    return found


def end_window_move(display: str) -> None:
    """Leave IceWM's window-move mode if it is active.

    Wine turns a click that misses every control of a custom-drawn installer
    (DODI repacks) into a drag of the window, and IceWM then stays in move
    mode (an "IceStatus" window shows the position) until the next pointer
    event, which would move the window instead of pressing the button. IceWM
    grabs the keyboard in that mode, so Escape cancels it without reaching
    the installer.
    """
    if _xdotool(display, "search", "--onlyvisible", "--name", "^IceStatus$").strip():
        _xdotool(display, "key", "Escape")
        time.sleep(MOVE_CANCEL_SETTLE)


def click(display: str, x: int, y: int) -> None:
    """Click at absolute screen coordinates."""
    end_window_move(display)
    _xdotool(display, "mousemove", str(x), str(y), "click", "1")
    time.sleep(MOVE_CANCEL_SETTLE)
    end_window_move(display)


def press_key(display: str, key: str, alt: bool = True) -> None:
    """Send a key to the installer.

    A bare key (e.g. Up on a "press up to unlock" splash) is only seen by the
    window that has the keyboard, and Wine often leaves that on a nameless
    helper, where keys vanish; ``windowfocus`` cannot move it and synthetic
    ``--window`` events are ignored. A real click inside the installer does
    give it the focus. An Alt+letter follows the click on the button that
    was just tried, so the focus is already right.
    """
    if not alt:
        area = pick_main_window(_windows(display))
        if area is not None:
            click(display, area[0] + area[2] // 2, area[1] + area[3] // 2)
            time.sleep(FOCUS_CLICK_SETTLE)
    _xdotool(display, "key", "--clearmodifiers", f"alt+{key}" if alt else key)
    end_window_move(display)
