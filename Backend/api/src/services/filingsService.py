"""The regimes whose engines share one shape: a workbook in, a filing out.

U 1.1, O 4.1, ESEF, SAQ and FATCA/CRS each expose the same three operations —
hand out a blank template, read a filled-in one back, and build the filing —
so they are described once as data here rather than as five near-identical
modules. Each entry names the engine functions that do the work; the engines
themselves are untouched in domain/.
"""

from __future__ import annotations

import base64
import dataclasses
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, get_args

from domain.esef import esef_engine
from domain.o41 import o41_engine
from domain.saq import saq_engine
from domain.urr import urr_engine

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class FilingRegime:
    key: str
    label: str
    authority: str
    output_label: str
    output_media_type: str
    template_filename: str
    build_template: Callable[[], bytes]
    parse_workbook: Callable[[bytes], tuple]
    parse_keys: tuple[str, ...]


REGIMES: dict[str, FilingRegime] = {
    "urr": FilingRegime(
        key="urr", label="U 1.1", authority="CSSF",
        output_label="U 1.1 XML filing", output_media_type="application/xml",
        template_filename="U11_template.xlsx",
        build_template=urr_engine.build_urr_template_workbook,
        parse_workbook=urr_engine.parse_urr_workbook,
        parse_keys=("header", "share_classes", "errors"),
    ),
    "o41": FilingRegime(
        key="o41", label="O 4.1", authority="CSSF / BCL",
        output_label="O 4.1 EDIFACT filing", output_media_type="text/plain",
        template_filename="O41_template.xlsx",
        build_template=o41_engine.build_o41_template_workbook,
        parse_workbook=o41_engine.parse_o41_workbook,
        parse_keys=("header", "totals", "assets", "liabilities", "errors"),
    ),
    "esef": FilingRegime(
        key="esef", label="ESEF", authority="ESMA",
        output_label="Inline XBRL report", output_media_type="application/xhtml+xml",
        template_filename="ESEF_template.xlsx",
        build_template=esef_engine.build_esef_template_workbook,
        parse_workbook=esef_engine.parse_esef_workbook,
        parse_keys=("entity", "figures", "narratives", "errors"),
    ),
    "saq": FilingRegime(
        key="saq", label="SAQ", authority="CSSF",
        output_label="SAQ summary workbook", output_media_type=XLSX_MEDIA_TYPE,
        template_filename="SAQ_template.xlsx",
        build_template=saq_engine.build_saq_template_workbook,
        parse_workbook=saq_engine.parse_saq_workbook,
        parse_keys=("entity", "answers", "metadata", "errors"),
    ),
}


def _regime(regime_key: str) -> FilingRegime:
    regime = REGIMES.get(regime_key)
    if regime is None:
        raise LookupError(f"Unknown regime '{regime_key}'; expected one of {', '.join(REGIMES)}.")
    return regime


def filing_regimes_service() -> list[dict[str, Any]]:
    return [
        {"key": r.key, "label": r.label, "authority": r.authority,
         "output": r.output_label, "template_filename": r.template_filename}
        for r in REGIMES.values()
    ]


def filing_template_service(regime_key: str) -> tuple[str, bytes, str]:
    """A blank workbook for a regime. Returns (filename, bytes, media type)."""
    regime = _regime(regime_key)
    return regime.template_filename, regime.build_template(), XLSX_MEDIA_TYPE


def filing_parse_service(regime_key: str, content: bytes) -> dict[str, Any]:
    """Reads a filled-in workbook back into the dictionaries the engine uses,
    naming each part the way that regime does."""
    regime = _regime(regime_key)
    parts = regime.parse_workbook(content)
    return dict(zip(regime.parse_keys, parts))


# =============================================================================
# Building a filing
# =============================================================================


# =============================================================================
# The wire format and the domain
# =============================================================================

def _as_date(value: Any) -> Any:
    """An ISO string turned into the date the engine declared."""
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return value
    return value


def _typed(cls: Any, payload: dict[str, Any]) -> Any:
    """Builds a submission from the loosely-typed dictionary a client sends.

    JSON has no date type, so every date arrives as a string while the
    engines declare real ``date`` fields and call ``strftime`` on them. The
    conversion therefore has to happen at this boundary — the same defect
    the AIFMD service had, and for the same reason.

    Only the fields the dataclass declares are passed through: a client that
    sends an extra key gets it ignored rather than a TypeError naming an
    argument it has never heard of.
    """
    fields = {f.name: f for f in dataclasses.fields(cls)}
    converted: dict[str, Any] = {}
    for name, value in payload.items():
        field = fields.get(name)
        if field is None:
            continue
        annotation = field.type
        text = getattr(annotation, "__name__", None) or str(annotation)
        optional = [getattr(a, "__name__", str(a)) for a in get_args(annotation)]
        if "date" in text or any("date" in a for a in optional):
            value = _as_date(value)
        converted[name] = value
    return cls(**converted)


def urr_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """U 1.1 — one XML filing per UCI."""
    submission = _typed(urr_engine.UrrSubmission, payload)
    xml = urr_engine.build_u11_xml(submission)
    return {"filename": _filename(submission, "U11", "xml"), "content": xml,
            "media_type": "application/xml", "label": REGIMES["urr"].output_label}


def o41_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """O 4.1 — an EDIFACT message, not XML."""
    submission = _typed(o41_engine.O41Submission, payload)
    message = o41_engine.build_o41_edifact(submission)
    return {"filename": _filename(submission, "O41", "txt"), "content": message,
            "media_type": "text/plain", "label": REGIMES["o41"].output_label}


def esef_generate_service(payload: dict[str, Any], as_package: bool = False) -> dict[str, Any]:
    """ESEF — the Inline XBRL document, or the whole report package as a ZIP."""
    submission = _typed(esef_engine.EsefSubmission, payload)
    ixbrl = esef_engine.build_ixbrl_document(submission)
    if not as_package:
        return {"filename": _filename(submission, "ESEF", "xhtml"), "content": ixbrl,
                "media_type": "application/xhtml+xml", "label": REGIMES["esef"].output_label}
    archive, filename = esef_engine.build_report_package(submission, ixbrl)
    return {"filename": filename, "content_base64": base64.b64encode(archive).decode("ascii"),
            "media_type": "application/zip", "label": "ESEF report package"}


def saq_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """SAQ — the summary workbook a UCI files with the CSSF."""
    submission = _typed(saq_engine.SaqSubmission, payload)
    workbook = saq_engine.build_saq_summary_workbook(submission)
    return {"filename": _filename(submission, "SAQ", "xlsx"),
            "content_base64": base64.b64encode(workbook).decode("ascii"),
            "media_type": XLSX_MEDIA_TYPE, "label": REGIMES["saq"].output_label}


_GENERATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "urr": urr_generate_service,
    "o41": o41_generate_service,
    "esef": esef_generate_service,
    "saq": saq_generate_service,
}


def filing_generate_service(regime_key: str, payload: dict[str, Any], **options: Any) -> dict[str, Any]:
    _regime(regime_key)
    return _GENERATORS[regime_key](payload, **options)


def _filename(submission: Any, prefix: str, extension: str) -> str:
    """A predictable name built from whichever identifier the submission
    carries, so two filings of the same entity never collide."""
    for attribute in ("entity_name", "uci_name", "fund_name", "name", "entity_code", "uci_code"):
        value = getattr(submission, attribute, None)
        if value:
            safe = "".join(c for c in str(value) if c.isalnum() or c in (" ", "-", "_")).strip()
            safe = safe.replace(" ", "_") or prefix
            return f"{prefix}_{safe}.{extension}"
    return f"{prefix}_filing.{extension}"
