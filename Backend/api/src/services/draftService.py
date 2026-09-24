"""Named drafts of a half-finished submission.

A regulatory filing is rarely completed in one sitting, so a preparer can
park the current state of any module's form under a name and pick it up
later. Drafts are per module and stored as JSON, which keeps the dates and
nested tables intact through the round trip.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database.jsonStore import deserialise, read_json, serialise, write_json
from utils.paths import drafts_dir

MAX_NAME_LENGTH = 80


def _safe_name(name: str) -> str:
    """A file name that cannot escape the drafts directory."""
    cleaned = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip()
    if not cleaned:
        raise ValueError("A draft name must contain at least one letter, digit, space, hyphen or underscore.")
    return cleaned[:MAX_NAME_LENGTH]


def _module_dir(module_key: str):
    directory = drafts_dir() / _safe_name(module_key)
    return directory


# Where an entity's name and the reporting period sit differs per regime, so
# a draft is searched for the first key that matches — a name is a name
# whether the regulator calls it uci_name, aif_name or entity_name.
_ENTITY_KEYS = ("entity_name", "uci_name", "aif_name", "aifm_name", "fund_name",
                "subfund_name", "name")
_PERIOD_KEYS = ("reference_month", "period_end", "period_start", "financial_year_end",
                "year_end", "end_month_date", "valuation_date", "closing_date")
_CODE_KEYS = ("uci_cssf_code", "aif_national_number", "aifm_national_code", "sender_id",
              "uci_id", "reporter_code", "lei")


def _dig(data: Any, keys: tuple[str, ...], depth: int = 0) -> str:
    """The first of `keys` carrying a value, looked for one level down as
    well — AIFMD nests everything under aifm_info and aif_info."""
    if not isinstance(data, dict) or depth > 2:
        return ""
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return str(value)[:80]
    for value in data.values():
        if isinstance(value, dict):
            found = _dig(value, keys, depth + 1)
            if found:
                return found
    return ""


def _completeness(data: Any) -> int:
    """How many values a draft actually carries. A rough figure, but enough
    to tell one barely started from one nearly ready to file."""
    if isinstance(data, dict):
        return sum(_completeness(value) for value in data.values())
    if isinstance(data, list):
        return sum(_completeness(item) for item in data)
    return 0 if data in (None, "", [], {}) else 1


def list_drafts_service(module_key: str) -> list[dict[str, Any]]:
    """Every saved draft of a module, most recently saved first.

    Each carries enough of itself — the entity, the period, how much is
    filled in — to be recognised from a list, because a preparer coming back
    a week later remembers the fund, not the name they typed.
    """
    directory = _module_dir(module_key)
    if not directory.exists():
        return []
    drafts = []
    for path in directory.glob("*.json"):
        payload = read_json(path, {})
        data = deserialise(payload.get("data", {}))
        drafts.append({
            "name": path.stem,
            "saved_at": payload.get("saved_at", ""),
            "saved_by": payload.get("saved_by", ""),
            "entity": _dig(data, _ENTITY_KEYS),
            "period": _dig(data, _PERIOD_KEYS),
            "code": _dig(data, _CODE_KEYS),
            "fields_filled": _completeness(data),
        })
    return sorted(drafts, key=lambda d: d["saved_at"], reverse=True)


def save_draft_service(module_key: str, name: str, data: dict[str, Any], user: str = "") -> dict[str, Any]:
    safe = _safe_name(name)
    directory = _module_dir(module_key)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "saved_by": user,
        "data": serialise(data),
    }
    write_json(directory / f"{safe}.json", payload)
    return {"name": safe, "saved_at": payload["saved_at"], "saved_by": user}


def load_draft_service(module_key: str, name: str) -> dict[str, Any]:
    path = _module_dir(module_key) / f"{_safe_name(name)}.json"
    if not path.exists():
        raise LookupError(f"No draft named '{name}' was saved for module '{module_key}'.")
    payload = read_json(path, None)
    if payload is None:
        raise LookupError(f"The draft '{name}' of module '{module_key}' could not be read.")
    return {"name": path.stem, "saved_at": payload.get("saved_at", ""),
            "saved_by": payload.get("saved_by", ""), "data": deserialise(payload.get("data", {}))}


def delete_draft_service(module_key: str, name: str) -> None:
    path = _module_dir(module_key) / f"{_safe_name(name)}.json"
    if not path.exists():
        raise LookupError(f"No draft named '{name}' was saved for module '{module_key}'.")
    path.unlink()
