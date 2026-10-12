"""Configuration helpers: API key / model loading with a tiny .env loader."""

from __future__ import annotations

import os
from pathlib import Path

# The current "Flash Lite" model id. Override with GEMINI_MODEL if Google
# changes the naming (older id: gemini-2.0-flash-lite).
DEFAULT_MODEL = "gemini-2.5-flash-lite"


def _load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from a .env file without an extra dependency.

    Real environment variables always win over .env values.
    """
    env_path = path or (Path.cwd() / ".env")
    if not env_path.exists():
        return

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_api_key() -> str | None:
    _load_dotenv()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def load_model() -> str:
    _load_dotenv()
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
