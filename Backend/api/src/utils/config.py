"""Environment configuration, loaded once before anything reads it.

``Backend/api/.env`` holds the settings an operator changes between
environments — the CORS origins above all. Nothing loads a .env file on its
own, so importing this module first is what makes that file take effect;
without it ``CORS_ORIGINS`` is silently ignored and the API answers every
origin, which is not what the file says.

Real environment variables always win: a value already set in the process
environment is never overwritten by the file, so a container's settings take
precedence over the checked-in defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    """Reads a KEY=VALUE file into the process environment."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env()
