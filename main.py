#!/usr/bin/env python3
"""osctrl — autonomous OS control agent driven by Gemini Flash Lite.

Flow: initial prompt -> screenshot -> Gemini Flash Lite -> JSON action ->
execute on the OS -> repeat until "done" or max steps.
"""

from __future__ import annotations

import argparse
import sys
import time

from agent import Agent
from config import load_api_key, load_model
from model import GeminiModel, MockModel


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="osctrl",
        description="Autonomous OS control agent driven by Gemini Flash Lite.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--goal", "-g", help="Initial prompt / goal. If omitted, you are asked interactively.")
    p.add_argument("--model", default=None, help="Gemini model id (default: GEMINI_MODEL env or gemini-2.5-flash-lite).")
    p.add_argument("--max-steps", type=int, default=25, help="Maximum number of agent steps before giving up.")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds to wait after each action so the UI settles.")
    p.add_argument("--dry-run", action="store_true", help="Print actions instead of executing them.")
    p.add_argument("--demo", action="store_true", help="Use a scripted mock model instead of Gemini (no API key needed).")
    p.add_argument("--live", action="store_true", help="Execute for real even in --demo mode (use with caution).")
    p.add_argument("--immediate", action="store_true", help="Skip the startup countdown.")
    return p


def main() -> int:
    args = build_parser().parse_args()

    goal = args.goal
    if goal is None:
        try:
            goal = input("What should I do? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
    if not goal:
        print("No goal provided — nothing to do.")
        return 1

    if args.demo:
        model = MockModel()
        print("Running in DEMO mode with a scripted mock model (no API key required).")
    else:
        api_key = load_api_key()
        if not api_key:
            print("No Gemini API key found.", file=sys.stderr)
            print("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment,", file=sys.stderr)
            print("or create a .env file containing:", file=sys.stderr)
            print("    GEMINI_API_KEY=your-key-here", file=sys.stderr)
            print("Tip: run with --demo to exercise the loop without an API key.", file=sys.stderr)
            return 1
        model_name = args.model or load_model()
        print(f"Using Gemini model: {model_name}")
        model = GeminiModel(api_key=api_key, model=model_name)

    # Demo defaults to previewing actions unless the user explicitly opts into
    # real execution with --live. Gemini mode is live unless --dry-run.
    dry_run = args.dry_run or (args.demo and not args.live)

    if not args.immediate:
        print("Starting in 3 seconds — switch to the app you want controlled.")
        try:
            for remaining in (3, 2, 1):
                print(f"  {remaining}...")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            return 130
        print("Go!\n")

    agent = Agent(model=model, dry_run=dry_run, max_steps=args.max_steps, delay=args.delay)
    try:
        return agent.run(goal)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
