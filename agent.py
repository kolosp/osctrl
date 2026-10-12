"""The autonomous loop: screenshot -> model -> JSON action -> execute -> repeat."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from actions import ActionExecutor
from screenshot import capture_screenshot

SYSTEM_PROMPT = """\
You are an autonomous computer control agent. At each step you receive a
screenshot of the current screen plus a short description of what happened.

Respond with EXACTLY ONE JSON object describing the single next action to take.
Output only the JSON object — no markdown fences, no commentary, no explanation.

Available actions (x/y are normalized 0..1000; 0,0 = top-left, 1000,1000 = bottom-right):
- {"action": "click", "x": <int>, "y": <int>}                        left click
- {"action": "double_click", "x": <int>, "y": <int>}                 double left click
- {"action": "right_click", "x": <int>, "y": <int>}                  right click
- {"action": "move", "x": <int>, "y": <int>}                         move mouse (no click)
- {"action": "drag", "x1": <int>, "y1": <int>, "x2": <int>, "y2": <int>}  drag
- {"action": "type", "text": "<string>"}                             type text
- {"action": "press", "key": "<key>"}                                press one key (enter, tab, esc, ...)
- {"action": "hotkey", "keys": ["<key1>", "<key2>"]}                 keys together (e.g. ["ctrl","c"])
- {"action": "scroll", "amount": <int>}                              scroll (positive=up, negative=down)
- {"action": "wait", "seconds": <number>}                            pause briefly
- {"action": "done", "message": "<summary>"}                         goal achieved; stop now

Rules:
- Only use "done" once the goal is fully achieved.
- Do NOT issue "wait" two steps in a row. Only wait if you are confident the
  screen is loading and will change on its own.
- If your previous action did not change the screen, do something different:
  click another element, move the mouse elsewhere, use a keyboard shortcut, or
  scroll. Never repeat an action that had no effect.
- Prefer keyboard shortcuts over pixel-perfect clicking when possible.
"""


def _first_json_object(text: str) -> str | None:
    """Return the substring spanning the first balanced JSON object, if any."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_action(text: str) -> dict | None:
    """Parse the model reply into an action dict, tolerating stray text."""
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    candidate = _first_json_object(text)
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


class Agent:
    def __init__(
        self,
        model,
        dry_run: bool = False,
        max_steps: int = 25,
        delay: float = 1.0,
        max_repeats: int = 3,
        save_dir: str | Path | None = None,
    ):
        self.model = model
        self.executor = ActionExecutor(dry_run=dry_run)
        self.max_steps = max_steps
        self.delay = delay
        self.max_repeats = max_repeats
        self.save_dir = Path(save_dir) if save_dir else None
        self.history: list[dict] = []

    def _save(self, step: int, png_bytes: bytes) -> None:
        if not self.save_dir:
            return
        self.save_dir.mkdir(parents=True, exist_ok=True)
        (self.save_dir / f"step_{step:03d}.png").write_bytes(png_bytes)

    def run(self, goal: str) -> int:
        model_name = getattr(self.model, "model", "unknown")
        live = not self.executor.dry_run
        print(f"Goal : {goal}")
        print(f"Model: {model_name}")
        print(f"Mode : {'dry-run' if self.executor.dry_run else 'live'}")
        if self.save_dir:
            print(f"Debug: saving screenshots to {self.save_dir}")
        print()

        if live:
            # Use pyautogui's own coordinate space for mapping (fixes Windows
            # display-scaling mismatches between capture and input).
            try:
                self.executor.sync_screen_size()
                print(
                    f"Screen: {self.executor.screen_width}x{self.executor.screen_height} "
                    "(pyautogui coordinates)"
                )
            except Exception as exc:
                print(f"Warning: could not query screen size: {exc}", file=sys.stderr)

        feedback = ""
        repeat_signature: str | None = None
        repeat_count = 0
        consecutive_waits = 0

        for step in range(1, self.max_steps + 1):
            png_bytes, width, height = capture_screenshot()
            self._save(step, png_bytes)

            if live:
                self.executor.sync_screen_size()
            else:
                self.executor.set_screen_size(width, height)

            if len(png_bytes) < 10_000:
                print(
                    f"  warning: screenshot is only {len(png_bytes)} bytes — it may be "
                    "blank/black (capture failed or the window is GPU-protected)."
                )

            if step == 1:
                instruction = (
                    f"Goal: {goal}\n"
                    f"The screen is {width}x{height} pixels.\n"
                    "Here is the current screen. Decide the next action."
                )
            else:
                instruction = f"Result of your last action: {feedback}\n"
                if consecutive_waits >= 2 or repeat_count >= 2:
                    instruction += (
                        "WARNING: your last actions were repeated with no visible progress. "
                        "Do NOT repeat the same action — take a different action now.\n"
                    )
                instruction += "Here is the current screen. Decide the next action."

            self.history.append({"role": "user", "image": png_bytes, "text": instruction})

            print(f"Step {step:>2}: asking {model_name} ... ", end="", flush=True)
            try:
                raw = self.model.generate(self.history, SYSTEM_PROMPT)
            except Exception as exc:
                print(f"\nModel error: {exc}", file=sys.stderr)
                return 1
            print("reply received.")

            self.history.append({"role": "model", "text": raw})

            action = extract_action(raw)
            if action is None:
                feedback = (
                    "Your last reply was not valid JSON. "
                    "Reply with ONLY a single JSON action object."
                )
                print(f"  could not parse an action from reply: {raw!r}")
                continue

            name = str(action.get("action", "")).strip().lower()
            print(f"  action: {json.dumps(action)}")

            # Track stalls so a "wait forever" / no-op loop cannot run unchecked.
            signature = json.dumps(action, sort_keys=True)
            repeat_count = repeat_count + 1 if signature == repeat_signature else 1
            repeat_signature = signature
            consecutive_waits = consecutive_waits + 1 if name == "wait" else 0

            try:
                feedback = self.executor.execute(action)
            except Exception as exc:
                feedback = f"Action failed: {exc}"
            print(f"  result: {feedback}")

            if name == "done":
                print(f"\nDone: {action.get('message', '')}")
                return 0

            if consecutive_waits >= self.max_repeats:
                print(
                    f"\nStopped: the model waited {consecutive_waits} times in a row with no "
                    "progress. Actions are probably not taking effect — check display "
                    "scaling/DPI, that the target window has focus, and that the agent is "
                    "running at the same privilege level as the app."
                )
                return 3

            if repeat_count >= self.max_repeats:
                print(
                    f"\nStopped: the model repeated the same action {repeat_count} times "
                    f"({signature}) with no progress."
                )
                return 3

            if self.delay > 0:
                time.sleep(self.delay)

        print(f"\nStopped: reached max steps ({self.max_steps}) without completing the goal.")
        return 2
