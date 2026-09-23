"""What may legitimately differ between two runs of the same filing.

Only the moment a document was produced: creation timestamps inside it and
the time-stamp tokens some regulators put in file names. Everything else —
every code, amount, date and element — has to match the Streamlit original
byte for byte. The masks are deliberately narrow so they cannot hide a
business difference: a date without a time part is data and is never
masked.
"""

from __future__ import annotations

import re
from typing import Any

# A date *with* a time part is a production timestamp (creationDateTime,
# CreationDateAndTime, the AEOI Timestamp...). A bare date is business data.
_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?")

# O 4.1 EDIFACT: the interchange header (UNB) carries the preparation date
# and time, the message reference is derived from it, and DTM+218 repeats it.
_EDIFACT = (
    (re.compile(r"(UNB\+[^+]*\+[^+]*\+[^+]*\+)\d{6}:\d{4}"), r"\1<YYMMDD:HHMM>"),
    # The reference is X + yymmddHHMM, followed in UNH/UNT by a sequence
    # number that is kept: it is structure, not time.
    (re.compile(r"\bX\d{10}(\d*)\b"), r"X<MSGREF>\1"),
    (re.compile(r"DTM\+218:\d{12}:203"), "DTM+218:<YYYYMMDDHHMM>:203"),
)

# File names: AIFMD and the AEOI returns embed a yyyymmddHHMMSS stamp; BCL
# names end with the creation date and a sequence number.
_FILENAME = (
    (re.compile(r"\d{14}"), "<STAMP>"),
    (re.compile(r"_\d{8}_(\d{3})\.xml$"), r"_<CREATED>_\1.xml"),
)

# Keys of a JSON result that carry the day it was produced.
_VOLATILE_KEYS = {"generation_date"}


def text(value: str) -> str:
    """A generated document with its production timestamps masked."""
    value = _DATETIME.sub("<DATETIME>", value)
    for pattern, replacement in _EDIFACT:
        value = pattern.sub(replacement, value)
    return value.replace("\r\n", "\n")


def filename(value: str) -> str:
    for pattern, replacement in _FILENAME:
        value = pattern.sub(replacement, value)
    return value


def data(value: Any) -> Any:
    """A JSON-like result with its volatile fields masked and its floats
    rounded, so that 0.1 + 0.2 computed in two orders compares equal."""
    if isinstance(value, dict):
        return {k: ("<MASKED>" if k in _VOLATILE_KEYS else data(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        return text(value)
    return value


def workbook(content: bytes) -> dict[str, list[list[Any]]]:
    """An xlsx reduced to its cell values, sheet by sheet: the archive itself
    carries its own creation time and cannot be compared as bytes."""
    import io
    import warnings

    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    return {
        sheet.title: [[data(_cell(c)) for c in row] for row in sheet.iter_rows(values_only=True)]
        for sheet in book.worksheets
    }


def _cell(value: Any) -> Any:
    from datetime import datetime, time

    # Excel stores a date as a midnight datetime: that is a date (business
    # data, e.g. a filing deadline), not a production timestamp.
    if isinstance(value, datetime) and value.time() == time(0):
        return value.date().isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
