"""Filesystem locations the API relies on.

Every path the domain layer needs is resolved from here rather than from a
module's own position on disk, so the engines stay agnostic about where the
service is deployed and a test can point them somewhere else.

- ``RESOURCES_DIR`` holds everything the regulators publish and the engines
  read: the XSD schemas, the instructions and verification-rule PDFs, the
  official chart-of-accounts workbooks and the reference tables.
- ``RUNTIME_DIR`` holds what the API writes: saved drafts, the document
  store and the audit trail. It is created on demand, and its location can
  be overridden with the ``RUNTIME_DIR`` environment variable so a container
  can mount a volume there.
"""

from __future__ import annotations

import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = SRC_DIR / "resources"

RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", SRC_DIR.parent / "runtime"))
DRAFTS_DIR = RUNTIME_DIR / "drafts"
DOC_STORE_FILE = RUNTIME_DIR / "doc_store.json"
AUDIT_LOG_FILE = RUNTIME_DIR / "audit_log.json"
GENERATED_DIR = RUNTIME_DIR / "generated"


def ensure_runtime_dirs() -> None:
    """Creates the writable directories the API needs, once, at startup."""
    for directory in (RUNTIME_DIR, DRAFTS_DIR, GENERATED_DIR):
        directory.mkdir(parents=True, exist_ok=True)
