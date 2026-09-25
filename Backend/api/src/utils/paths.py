"""Filesystem locations the API relies on.

Every path the domain layer needs is resolved from here rather than from a
module's own position on disk, so the engines stay agnostic about where the
service is deployed and a test can point them somewhere else.

- ``RESOURCES_DIR`` holds everything the regulators publish and the engines
  read: the XSD schemas, the instructions and verification-rule PDFs, the
  official chart-of-accounts workbooks and the reference tables.
- ``RUNTIME_DIR`` holds what the API writes. Its location can be overridden
  with the ``RUNTIME_DIR`` environment variable so a container can mount a
  volume there.

Each organisation's data — drafts, the document store, the audit trail, the
fund registry and its own configuration — lives under
``RUNTIME_DIR/orgs/<id>/``. Which organisation a request belongs to is set
once, by the authentication dependency, in a context variable; the functions
below read it, so no service has to carry the organisation through its
signatures and none can reach another organisation's files.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = SRC_DIR / "resources"

RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", SRC_DIR.parent / "runtime"))

_CURRENT_ORG: ContextVar[int | None] = ContextVar("current_org", default=None)


def set_current_org(org_id: int | None) -> None:
    _CURRENT_ORG.set(org_id)


def org_dir(org_id: int | None = None) -> Path:
    """The organisation's own directory. Outside a request (scripts, engine
    tests) there is no organisation, and nothing may be written for one."""
    org = org_id if org_id is not None else _CURRENT_ORG.get()
    if org is None:
        raise RuntimeError("No organisation is bound to this request.")
    return RUNTIME_DIR / "orgs" / str(int(org))


def drafts_dir() -> Path:
    return org_dir() / "drafts"


def doc_store_file() -> Path:
    return org_dir() / "doc_store.json"


def audit_log_file(org_id: int | None = None) -> Path:
    return org_dir(org_id) / "audit_log.json"


def funds_file() -> Path:
    return org_dir() / "funds.json"


def org_config_dir(org_id: int | None = None) -> Path:
    """What an organisation configures for itself: its FATCA preparers, its
    PRIIPs settings and logo, its client records."""
    return org_dir(org_id) / "config"


def ensure_runtime_dirs() -> None:
    """Creates the writable root once, at startup."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
