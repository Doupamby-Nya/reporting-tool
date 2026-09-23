"""The registry of funds and share classes under mandate.

This is the PRIIPs chain's input and the global summary's subject: one
record per fund/share class, loaded from the standardised workbook or
entered by hand. It is kept in the same JSON store the workflow uses, so a
restart does not lose a registry that took a workbook upload to build.

A share class is identified by its ``fund_id``. Re-ingesting a workbook
therefore updates the rows it carries rather than duplicating them, which is
what makes an upload repeatable after a correction.
"""

from __future__ import annotations

from typing import Any

from database.jsonStore import read_json, write_json
from domain.shared import excel_io, sample_data
from utils.paths import RUNTIME_DIR

FUNDS_FILE = RUNTIME_DIR / "funds.json"


def _read() -> list[dict[str, Any]]:
    records = read_json(FUNDS_FILE, [])
    return records if isinstance(records, list) else []


def _write(records: list[dict[str, Any]]) -> None:
    write_json(FUNDS_FILE, records)


def funds_service() -> list[dict[str, Any]]:
    return _read()


def fund_template_service() -> tuple[str, bytes, str]:
    """The standardised ingestion workbook, examples included."""
    return (
        "priips_kid_ingestion_template.xlsx",
        excel_io.build_ingestion_template_workbook(include_examples=True),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def fund_parse_service(content: bytes) -> dict[str, Any]:
    """Reads a filled-in workbook without committing it. The preparer sees
    what was read, and what was rejected, before the registry changes."""
    funds, errors = excel_io.parse_ingestion_workbook(content)
    return {"funds": funds, "errors": errors}


def fund_add_service(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds or updates records, keyed by fund_id."""
    registry = {record.get("fund_id"): record for record in _read()}
    for record in records:
        fund_id = record.get("fund_id")
        if not fund_id:
            raise ValueError("Every record needs a fund_id; one row carried none.")
        registry[fund_id] = {**registry.get(fund_id, {}), **record}
    merged = list(registry.values())
    _write(merged)
    return merged


def fund_delete_service(fund_id: str) -> list[dict[str, Any]]:
    remaining = [record for record in _read() if record.get("fund_id") != fund_id]
    _write(remaining)
    return remaining


def fund_demo_service() -> list[dict[str, Any]]:
    """Loads the fictitious demo dataset, replacing whatever is there.

    The figures and ISINs are invented — this exists so the chain can be
    walked end to end without a real workbook, and it says so on the screen
    that offers it.
    """
    records = [dict(record) for record in sample_data.SAMPLE_FUNDS]
    _write(records)
    return records


def fund_reset_service() -> list[dict[str, Any]]:
    _write([])
    return []
