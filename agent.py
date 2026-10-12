"""The autonomous loop: screenshot -> model -> JSON action -> execute -> repeat."""

from __future__ import annotations

import json
import sys
import time

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

Only use "done" once the goal is fully achieved. Otherwise keep issuing the
single next concrete action that moves toward the goal.
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
    def __init__(self, model, dry_run: bool = False, max_steps: int = 25, delay: float = 1.0):
        self.model = model
        self.executor = ActionExecutor(dry_run=dry_run)
        self.max_steps = max_steps
        self.delay = delay
        self.history: list[dict] = []

    def run(self, goal: str) -> int:
        model_name = getattr(self.model, "model", "unknown")
        print(f"Goal : {goal}")
        print(f"Model: {model_name}")
        print(f"Mode : {'dry-run' if self.executor.dry_run else 'live'}")
        print()

        feedback = ""

        for step in range(1, self.max_steps + 1):
            png_bytes, width, height = capture_screenshot()
            self.executor.set_screen_size(width, height)

            if step == 1:
                instruction = (
                    f"Goal: {goal}\n"
                    f"The screen is {width}x{height} pixels.\n"
                    "Here is the current screen. Decide the next action."
                )
            else:
                instruction = (
                    f"Result of your last action: {feedback}\n"
                    "Here is the current screen. Decide the next action."
                )

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

            try:
                feedback = self.executor.execute(action)
            except Exception as exc:
                feedback = f"Action failed: {exc}"
            print(f"  result: {feedback}")

            if name == "done":
                print(f"\nDone: {action.get('message', '')}")
                return 0

            if self.delay > 0:
                time.sleep(self.delay)

        print(f"\nStopped: reached max steps ({self.max_steps}) without completing the goal.")
        return 2
