"""A small JSON-file store for the state the API keeps between requests.

The Streamlit predecessor held this in a per-session object; an API has no
session, so the document store, the audit trail and the saved drafts live on
disk instead, under the directory ``utils.paths.RUNTIME_DIR`` points at.

Writes go through a temporary file and an atomic replace, so a crash or two
concurrent requests can never leave a half-written file behind. A process
lock serialises writers within one worker; deployments running several
workers against the same volume should put a real database behind this
module, which is why every caller goes through it rather than touching the
files directly.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()


def _default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return {"__date__": value.isoformat()}
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def _revive(obj: Any) -> Any:
    if isinstance(obj, dict):
        if set(obj) == {"__date__"}:
            text = obj["__date__"]
            return datetime.fromisoformat(text) if "T" in text else date.fromisoformat(text)
        return {k: _revive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_revive(v) for v in obj]
    return obj


def read_json(path: Path, fallback: Any) -> Any:
    """The file's contents, or ``fallback`` when it is missing or unreadable.
    A corrupt file is never fatal: the API keeps serving, and the next write
    replaces it."""
    with _LOCK:
        try:
            return _revive(json.loads(path.read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return fallback


def write_json(path: Path, payload: Any) -> None:
    """Atomic write: a partial file is never visible to a reader.

    On an SMB share the rename can be refused even though both files are
    writable — the server denies a replace over an existing file often
    enough that it cannot be treated as an error. The fallback removes the
    target first and renames onto the free name, which gives up the
    atomicity for the width of those two calls rather than giving up the
    write. That window is acceptable here: the store is read back with a
    fallback, so a reader that catches it mid-write gets the fallback rather
    than a crash, and the next write repairs it.
    """
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, default=_default)
            try:
                os.replace(temporary, path)
            except PermissionError:
                path.unlink(missing_ok=True)
                os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise


def serialise(value: Any) -> Any:
    """Turns dates into the marker form used on disk, for payloads that are
    embedded in a larger document rather than written on their own."""
    return json.loads(json.dumps(value, default=_default))


def deserialise(value: Any) -> Any:
    return _revive(value)
