"""Execute model-issued JSON actions as real OS events via pyautogui.

pyautogui is imported lazily because it connects to an X11 display at import
time. This keeps the dry-run/demo path (and imports) working on headless
machines and gives a clearer error when no graphical session is available.
"""

from __future__ import annotations

import time

# The model emits coordinates in a normalized 0..1000 space so that actions
# remain valid even if the screen resolution changes.
SCALE = 1000

_pa = None  # cached pyautogui module


def _pyautogui():
    global _pa
    if _pa is None:
        try:
            import pyautogui
        except Exception as exc:
            raise RuntimeError(
                "Could not initialize pyautogui. A graphical (X11) session is "
                f"required to control the OS. Underlying error: {exc}"
            ) from exc
        pyautogui.FAILSAFE = True  # mouse in a screen corner aborts the run
        pyautogui.PAUSE = 0.1      # small pause between synthetic events
        _pa = pyautogui
    return _pa


class ActionExecutor:
    """Turn a JSON action dict into a real (or dry-run) OS event."""

    def __init__(self, dry_run: bool = False, screen_width: int = 1, screen_height: int = 1):
        self.dry_run = dry_run
        self.screen_width = screen_width
        self.screen_height = screen_height

    def set_screen_size(self, width: int, height: int) -> None:
        self.screen_width = width
        self.screen_height = height

    def _px(self, x: float, y: float) -> tuple[int, int]:
        px = int(round(float(x) / SCALE * self.screen_width))
        py = int(round(float(y) / SCALE * self.screen_height))
        return px, py

    def execute(self, action: dict) -> str:
        name = str(action.get("action", "")).strip().lower()

        if self.dry_run and name != "done":
            return f"[dry-run] {action!r}"

        if name == "done":
            return str(action.get("message", "done"))

        if name == "wait":
            seconds = float(action.get("seconds", 1))
            time.sleep(seconds)
            return f"waited {seconds}s"

        pa = _pyautogui()

        try:
            if name == "click":
                x, y = self._px(action["x"], action["y"])
                pa.click(x, y)
                return f"clicked ({x}, {y})"

            if name == "double_click":
                x, y = self._px(action["x"], action["y"])
                pa.doubleClick(x, y)
                return f"double-clicked ({x}, {y})"

            if name == "right_click":
                x, y = self._px(action["x"], action["y"])
                pa.rightClick(x, y)
                return f"right-clicked ({x}, {y})"

            if name == "move":
                x, y = self._px(action["x"], action["y"])
                pa.moveTo(x, y, duration=0.3)
                return f"moved mouse to ({x}, {y})"

            if name == "drag":
                x1, y1 = self._px(action["x1"], action["y1"])
                x2, y2 = self._px(action["x2"], action["y2"])
                pa.moveTo(x1, y1, duration=0.2)
                pa.dragTo(x2, y2, duration=0.5)
                return f"dragged from ({x1}, {y1}) to ({x2}, {y2})"

            if name == "type":
                text = str(action["text"])
                pa.write(text, interval=0.03)
                return f"typed {text!r}"

            if name == "press":
                key = str(action["key"])
                pa.press(key)
                return f"pressed {key!r}"

            if name == "hotkey":
                keys = [str(k) for k in action["keys"]]
                pa.hotkey(*keys)
                return f"pressed hotkey {'+'.join(keys)}"

            if name == "scroll":
                amount = int(action["amount"])
                pa.scroll(amount)
                return f"scrolled {amount}"

            return f"unknown action {name!r}"

        except pa.FailSafeException as exc:
            raise RuntimeError("pyautogui FAILSAFE triggered (mouse moved to a screen corner)") from exc
