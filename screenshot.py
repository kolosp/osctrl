"""Screen capture via mss (fast, no scrot dependency)."""

from __future__ import annotations

import io

import mss
from PIL import Image


def capture_screenshot() -> tuple[bytes, int, int]:
    """Capture the primary monitor as PNG bytes.

    Returns ``(png_bytes, width, height)``.
    """
    with mss.mss() as sct:
        # monitors[0] is the combined virtual screen; monitors[1] is the
        # primary monitor, whose top-left corner matches pyautogui's (0, 0).
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        shot = sct.grab(monitor)

        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), shot.width, shot.height
