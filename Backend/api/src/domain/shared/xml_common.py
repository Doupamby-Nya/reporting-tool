"""Shared XML-building primitives for the regulatory reporting engines.

Used by the BCL engines (domain.bcl.bcl_common re-exports everything here) and by
the AIFMD Annex IV engine. What lives here is deliberately regime-agnostic:

- a tiny element tree and serializer (correct escaping, deterministic
  indentation, no global namespace registration so it is thread-safe, and
  support for both namespaced documents — BCL — and no-namespace documents
  carrying xsi:noNamespaceSchemaLocation — ESMA/AIFMD);
- exact decimal formatting: no binary-float noise, never exponent notation,
  and a bounded number of fraction digits as the XSD datatypes require;
- the ``Issue`` type every validator returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from xml.sax.saxutils import escape, quoteattr

# =============================================================================
# Validation issues
# =============================================================================

ERROR = "error"      # blocks generation: the file would be rejected, or is invalid against the XSD
WARNING = "warning"  # shown to the preparer, does not block


@dataclass(frozen=True)
class Issue:
    level: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


def errors_of(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == ERROR]


def warnings_of(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == WARNING]


# =============================================================================
# XML tree + serializer
# =============================================================================

_ILLEGAL_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def clean_text(value: str) -> str:
    """Strips characters that are illegal in XML 1.0 (they would make the whole
    document non well-formed) and surrounding whitespace."""
    return _ILLEGAL_XML.sub("", value).strip()


class Node:
    """Minimal element: a tag, optional text, ordered children."""

    __slots__ = ("tag", "text", "children")

    def __init__(self, tag: str, text: str | None = None) -> None:
        self.tag = tag
        self.text = text
        self.children: list[Node] = []

    def add(self, tag: str, text: Any = None) -> "Node":
        """Appends and returns a child. ``text`` must already be a string (use
        the fmt_* helpers) or None for a container element."""
        child = Node(tag, None if text is None else str(text))
        self.children.append(child)
        return child

    def add_if(self, tag: str, text: Any) -> "Node | None":
        """Appends a leaf only when it carries a value — the usual shape for an
        optional element, which must be omitted rather than sent empty."""
        if text is None or (isinstance(text, str) and text == ""):
            return None
        return self.add(tag, text)

    def append(self, node: "Node") -> "Node":
        self.children.append(node)
        return node

    def __len__(self) -> int:
        return len(self.children)


def _render(node: Node, depth: int, out: list[str]) -> None:
    pad = "\t" * depth
    if node.children:
        out.append(f"{pad}<{node.tag}>")
        for c in node.children:
            _render(c, depth + 1, out)
        out.append(f"{pad}</{node.tag}>")
    else:
        text = escape(clean_text(node.text)) if node.text is not None else ""
        out.append(f"{pad}<{node.tag}>{text}</{node.tag}>")


def serialize(root: Node, namespace: str | None, attributes: dict[str, str]) -> str:
    """UTF-8 XML document string.

    ``namespace`` becomes the document's default namespace (every BCL schema is
    elementFormDefault="qualified" with a target namespace). Passing None emits
    a no-namespace document, which is what the ESMA AIFMD schemas define; the
    caller then usually adds xsi:noNamespaceSchemaLocation through
    ``attributes``."""
    parts = []
    if namespace is not None:
        parts.append(f" xmlns={quoteattr(namespace)}")
    parts.extend(f" {k}={quoteattr(v)}" for k, v in attributes.items())
    attrs = "".join(parts)
    out: list[str] = []
    if root.children:
        out.append(f"<{root.tag}{attrs}>")
        for c in root.children:
            _render(c, 1, out)
        out.append(f"</{root.tag}>")
    else:
        out.append(f"<{root.tag}{attrs}/>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(out) + "\n"


def creation_datetime(now: datetime | None = None) -> str:
    """xs:dateTime for a mandatory creation-timestamp attribute."""
    return (now or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")


# =============================================================================
# Scalar formatting (XSD lexical forms)
# =============================================================================

def to_decimal(value: Any) -> Decimal | None:
    """Blank -> None. Raises ValueError on anything that is not a finite
    number. Floats go through str() so the later quantize, not the binary
    expansion, decides the digits that are kept."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"not a number: {value!r}")
    if isinstance(value, Decimal):
        d = value
    else:
        text = str(value).strip()
        if text == "":
            return None
        try:
            d = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"not a number: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return d


def fmt_decimal(value: Any, fraction_digits: int, *, fixed: bool = False) -> str | None:
    """xs:decimal with at most ``fraction_digits`` digits (ROUND_HALF_UP), in
    plain notation. ``fixed=True`` keeps exactly that many digits; otherwise
    trailing zeros are dropped. Returns None for a blank value."""
    d = to_decimal(value)
    if d is None:
        return None
    q = d.quantize(Decimal(1).scaleb(-fraction_digits), rounding=ROUND_HALF_UP)
    text = format(q, "f")
    if not fixed and "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", "-0.0", ""):
        text = "0"
    if fixed and set(text.replace("-", "").replace(".", "")) == {"0"}:
        text = text.lstrip("-")
    return text


def fmt_integer(value: Any) -> str | None:
    """An amount reported "without decimal places" — the AIFMD wording for the
    xs:integer-backed amount types. Rounds half-up rather than truncating."""
    d = to_decimal(value)
    if d is None:
        return None
    return str(int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def fmt_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"not an ISO date (YYYY-MM-DD): {value!r}") from exc


def fmt_bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def fmt_int(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(int(value))


def as_date(value: Any) -> date | None:
    """Best-effort conversion used by validators (never raises)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def is_number(value: Any) -> bool:
    try:
        return to_decimal(value) is not None
    except ValueError:
        return False


def blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")
