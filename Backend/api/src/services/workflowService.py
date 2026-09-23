"""The document lifecycle and the audit trail, shared by every regime.

A generated filing moves through the same states whatever regulator it is
destined for — generated, under review, approved or rejected, published —
and every transition is written to one audit trail. That is the four-eyes
control the platform is built around, so it lives here rather than in any
one regime's service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.jsonStore import read_json, write_json
from utils.paths import AUDIT_LOG_FILE, DOC_STORE_FILE

STATUS_NOT_STARTED = "Not started"
STATUS_GENERATED = "Generated"
STATUS_REVIEW = "Under review"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_PUBLISHED = "Published"

STATUSES = (STATUS_NOT_STARTED, STATUS_GENERATED, STATUS_REVIEW,
            STATUS_APPROVED, STATUS_REJECTED, STATUS_PUBLISHED)

# Which states a document may move to next. A rejected filing goes back to
# the preparer, so it returns to "generated" rather than moving forward.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    STATUS_NOT_STARTED: (STATUS_GENERATED,),
    STATUS_GENERATED: (STATUS_REVIEW, STATUS_GENERATED),
    STATUS_REVIEW: (STATUS_APPROVED, STATUS_REJECTED),
    STATUS_APPROVED: (STATUS_PUBLISHED, STATUS_REVIEW),
    STATUS_REJECTED: (STATUS_GENERATED,),
    STATUS_PUBLISHED: (),
}

#: The most entries one read of the trail will return. This caps a *page*,
#: not the trail itself — nothing is deleted, a caller simply cannot ask for
#: the whole of a file that only grows.
MAX_AUDIT_PAGE = 1000


def _documents() -> dict[str, dict[str, Any]]:
    return read_json(DOC_STORE_FILE, {})


def _save_documents(store: dict[str, Any]) -> None:
    write_json(DOC_STORE_FILE, store)


def list_documents_service(module_key: str | None = None) -> dict[str, Any]:
    store = _documents()
    if module_key is None:
        return store
    return store.get(module_key, {})


def get_document_service(module_key: str, document_id: str) -> dict[str, Any] | None:
    return _documents().get(module_key, {}).get(document_id)


def record_generated_service(module_key: str, document_id: str, label: str, user: str) -> dict[str, Any]:
    """Registers a freshly generated filing, or a new version of one."""
    store = _documents()
    module = store.setdefault(module_key, {})
    entry = module.get(document_id, {"version": 0, "history": []})
    entry["version"] = int(entry.get("version", 0)) + 1
    entry["label"] = label
    entry["status"] = STATUS_GENERATED
    entry["last_generated"] = datetime.now().isoformat(timespec="seconds")
    entry["last_generated_by"] = user
    entry.setdefault("history", []).append({
        "version": entry["version"], "status": STATUS_GENERATED,
        "timestamp": entry["last_generated"], "user": user, "comment": "",
    })
    module[document_id] = entry
    _save_documents(store)
    log_audit_service(f"{module_key.upper()} generation", document_id, user, f"{label} generated")
    return entry


def transition_document_service(module_key: str, document_id: str, new_status: str,
                                user: str, comment: str = "") -> dict[str, Any]:
    """Moves a filing to its next state. Refuses a move the lifecycle does not
    allow, so an approval can never skip the review it depends on."""
    if new_status not in STATUSES:
        raise ValueError(f"Unknown status '{new_status}'; expected one of {', '.join(STATUSES)}.")

    store = _documents()
    module = store.get(module_key, {})
    entry = module.get(document_id)
    if entry is None:
        raise LookupError(f"No document '{document_id}' has been generated for module '{module_key}'.")

    current = entry.get("status", STATUS_NOT_STARTED)
    if new_status not in ALLOWED_TRANSITIONS.get(current, ()):
        allowed = ", ".join(ALLOWED_TRANSITIONS.get(current, ())) or "nothing further"
        raise ValueError(f"A document that is '{current}' can only move to {allowed}, not to '{new_status}'.")

    _enforce_four_eyes(entry, new_status, user)

    entry["status"] = new_status
    entry.setdefault("history", []).append({
        "version": entry.get("version", 1), "status": new_status,
        "timestamp": datetime.now().isoformat(timespec="seconds"), "user": user, "comment": comment,
    })
    module[document_id] = entry
    store[module_key] = module
    _save_documents(store)
    log_audit_service(f"{module_key.upper()} {new_status.lower()}", document_id, user, comment)
    return entry


#: The states whose whole purpose is that somebody other than the preparer
#: reaches them. Rejecting is one of them: a preparer who can reject their own
#: filing can clear it off the review queue without anybody having looked.
REVIEW_STATES = (STATUS_APPROVED, STATUS_REJECTED)


def _enforce_four_eyes(entry: dict[str, Any], new_status: str, user: str) -> None:
    """The four-eyes principle, actually enforced.

    The control the whole review exists for is that the person who approves
    a filing is not the person who prepared it. Offering the buttons and
    recording a name is not that control — without this check one person can
    generate a filing and approve it a second later, and the audit trail
    will faithfully record them doing it.

    Identity is a typed-in name until the platform has authentication, so
    this is as strong as the honesty of the name entered. That is a real
    limit, and it is a reason to add authentication rather than a reason to
    leave the check out: it already stops the accidental case, which is the
    common one.
    """
    if new_status not in REVIEW_STATES:
        return

    reviewer = (user or "").strip()
    if not reviewer:
        raise ValueError(f"A filing cannot be {new_status.lower()} by nobody: name the reviewer.")

    preparer = str(entry.get("last_generated_by") or "").strip()
    if preparer and preparer.casefold() == reviewer.casefold():
        raise ValueError(
            f"Four-eyes review: '{reviewer}' prepared this filing and cannot also "
            f"{'approve' if new_status == STATUS_APPROVED else 'reject'} it. "
            f"It has to be reviewed by somebody else.")


def log_audit_service(action: str, subject: str, user: str, detail: str = "") -> None:
    """Appends to the single trail every module writes to.

    The trail is never trimmed. It was capped at 500 entries, which quietly
    deleted the oldest — the ones a control review is most likely to ask
    for. A file that grows is a problem to solve by archiving it, not by
    dropping evidence.
    """
    entries = read_json(AUDIT_LOG_FILE, [])
    entries.insert(0, {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "action": action, "subject": subject, "user": user, "detail": detail,
    })
    write_json(AUDIT_LOG_FILE, entries)


def audit_log_service(limit: int = 100, module_key: str | None = None) -> list[dict[str, Any]]:
    entries = read_json(AUDIT_LOG_FILE, [])
    if module_key:
        prefix = module_key.upper()
        entries = [e for e in entries if str(e.get("action", "")).upper().startswith(prefix)]
    return entries[: max(1, min(limit, MAX_AUDIT_PAGE))]
