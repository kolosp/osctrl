# osctrl

An autonomous OS control agent driven by **Gemini Flash Lite**.

```
initial prompt -> screenshot -> Gemini Flash Lite -> JSON action -> execute -> repeat
```

The model is shown a screenshot of your screen each step and replies with a
single JSON action (`click`, `type`, `hotkey`, `scroll`, …). The program
executes it and loops until the model says `done` or a step limit is hit.

## Install

Uses [`uv`](https://docs.astral.sh/uv/) for Python dependencies:

```bash
uv sync
```

This creates `.venv` and installs everything from `pyproject.toml` /
`uv.lock` (including `python3-xlib` for pyautogui on Linux).

> **Wayland note:** synthetic mouse/keyboard events work on X11. On Wayland
> sessions you may need to run under Xorg/XWayland or use an alternative
> input backend.

## Configure

There is no API key yet — the program is built so you just drop one in later.

Create a `.env` file (copy `.env.example`) or export an env var:

```bash
export GEMINI_API_KEY="your-key-here"
```

The default model is `gemini-2.5-flash-lite` (the current Flash Lite id).
Override it with `GEMINI_MODEL` or `--model`.

## Run

```bash
uv run python main.py --goal "open a terminal and print the date"
```

If you omit `--goal`, the app asks you for the initial prompt after launch,
then runs autonomously:

```bash
uv run python main.py
# What should I do? open firefox and search for kittens
```

### Useful flags

| Flag | Effect |
| --- | --- |
| `--goal "..."` | initial prompt / goal |
| `--max-steps N` | stop after N model actions (default 25) |
| `--delay S` | pause S seconds after each action (default 1.0) |
| `--dry-run` | print actions but don't execute them |
| `--demo` | run a scripted mock model — no API key needed |
| `--live` | execute for real even in `--demo` mode |
| `--immediate` | skip the 3-second startup countdown |

### Try it without an API key

```bash
uv run python main.py --demo --goal "demo"
```

`--demo` uses a scripted mock model that steps through a few actions so you
can watch the whole loop work. It defaults to dry-run (no real clicks/keys);
add `--live` to let it actually drive the machine.

## Safety

- Moving the mouse to any screen corner aborts the run (pyautogui FAILSAFE).
- There is a 3-second countdown before the loop starts so you can focus the
  app you want controlled.
- `--dry-run` previews every action without touching the system.

## How it works

- `main.py` — argument parsing, startup, API-key handling.
- `config.py` — `.env`/environment loading.
- `screenshot.py` — captures the primary monitor as PNG via `mss`.
- `model.py` — `GeminiModel` (google-genai SDK) and `MockModel` (no-key demo).
- `agent.py` — the loop, system prompt, and JSON action parsing.
- `actions.py` — executes actions with `pyautogui`.

Coordinates are normalized to `0..1000` in both axes so actions stay valid
across screen resolutions.

## Development

Run the headless smoke test (no display or API key needed):

```bash
uv run python tests/smoke_test.py
```

## Troubleshooting

**The model only replies with `wait` and never makes progress.** This almost
always means actions aren't taking effect, so the screen never changes and the
model keeps waiting. Check, in order:

1. **Windows display scaling / DPI.** At 125%/150% scaling the capture size and
   the input coordinate space differ, so clicks land in the wrong place. osctrl
   now enables per-monitor DPI awareness and maps coordinates in pyautogui's own
   space, but verify with the debug screenshots below.
2. **See what the model sees:** run with `--save-screenshots shots/` and open the
   PNGs. If they are black/blank, capture is failing (or the window is
   GPU-protected).
3. **Focus and elevation.** Focus the target window during the 3-second
   countdown. Input cannot reach elevated ("Run as administrator") apps unless
   osctrl is also run elevated.
4. **Repetition guard.** `--max-repeats N` (default 3) stops the run when the
   same action — or a chain of waits — repeats, instead of looping forever.

Screenshots are downscaled to at most 1600px before being sent to the model.

## License

MIT — see [LICENSE](LICENSE).
