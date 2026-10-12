#!/usr/bin/env python3
"""Headless smoke test for osctrl.

Runs without a display or an API key: screenshots are stubbed and pyautogui is
never initialized because the agent runs in dry-run mode. Exits non-zero on the
first failed check.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

import agent as agent_mod  # noqa: E402
import config  # noqa: E402
from model import MockModel  # noqa: E402


def check(name: str, condition: bool) -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}")
    if not condition:
        raise SystemExit(f"smoke test failed: {name}")


def main() -> int:
    # 1) .env / config loading
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / ".env"
        env_file.write_text('GEMINI_API_KEY="test-key"\nGEMINI_MODEL=gemini-test\n')
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GEMINI_MODEL", None)
        config._load_dotenv(env_file)
        check("env: API key loaded from .env", os.environ.get("GEMINI_API_KEY") == "test-key")
        check("env: model loaded from .env", os.environ.get("GEMINI_MODEL") == "gemini-test")

    # 2) tolerant JSON action parsing
    parse_cases = [
        ('{"action": "click", "x": 1, "y": 2}', "click"),
        ('```json\n{"action": "type", "text": "hi"}\n```', "type"),
        ('{"action": "hotkey", "keys": ["ctrl", "c"]} trailing text', "hotkey"),
    ]
    for raw, expected in parse_cases:
        action = agent_mod.extract_action(raw)
        check(f"parse: {expected}", action is not None and action.get("action") == expected)
    check("parse: garbage -> None", agent_mod.extract_action("no json here") is None)

    # 3) mock model yields valid actions
    check("mock: yields a valid action", agent_mod.extract_action(MockModel().generate([], "")) is not None)

    # 4) full dry-run loop with a stubbed screenshot
    def fake_screenshot() -> tuple[bytes, int, int]:
        image = Image.new("RGB", (640, 480), (30, 30, 200))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        return buffer.getvalue(), 640, 480

    agent_mod.capture_screenshot = fake_screenshot
    agent = agent_mod.Agent(model=MockModel(), dry_run=True, max_steps=10, delay=0)
    code = agent.run("smoke test goal")
    check("agent: dry-run loop finishes with done", code == 0)

    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
