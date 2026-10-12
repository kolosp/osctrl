"""Screen capture via mss, plus DPI-scaling and payload-size helpers."""

from __future__ import annotations

import io
import sys

import mss
from PIL import Image

# Downscale very large screenshots before sending them to the model. This keeps
# requests small/fast and within the model's image limits. Coordinates are
# normalized, so resizing does not affect click accuracy.
MAX_DIMENSION = 1600


def enable_dpi_awareness() -> None:
    """Make the process DPI-aware on Windows.

    Without this, ``mss`` captures physical pixels while ``pyautogui`` reports
    logical (scaled) pixels under display scaling (125%, 150%, ...). Clicks then
    land in the wrong place, the screen never changes, and the model can end up
    stuck waiting forever. Must run before any screenshot / input call.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            # PROCESS_PER_MONITOR_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def capture_screenshot(max_dimension: int | None = MAX_DIMENSION) -> tuple[bytes, int, int]:
    """Capture the primary monitor as PNG bytes.

    Returns ``(png_bytes, width, height)`` where width/height are the *real*
    screen dimensions; the returned image may be downscaled.
    """
    with mss.mss() as sct:
        # monitors[0] is the combined virtual screen; monitors[1] is the
        # primary monitor, whose top-left corner matches pyautogui's (0, 0).
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        shot = sct.grab(monitor)

        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if max_dimension and max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            image = image.resize(
                (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                Image.LANCZOS,
            )

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), shot.width, shot.height
