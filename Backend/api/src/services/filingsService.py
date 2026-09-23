"""The regimes whose engines share one shape: a workbook in, a filing out.

U 1.1, O 4.1, ESEF and SAQ each expose the same three operations —
hand out a blank template, read a filled-in one back, and build the filing —
so they are described once as data here rather than as five near-identical
modules. Each entry names the engine functions that do the work; the engines
themselves are untouched in domain/.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

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


REGIMES: dict[str, FilingRegime] = {
    "urr": FilingRegime(
        key="urr", label="U 1.1", authority="CSSF",
        output_label="U 1.1 XML filing", output_media_type="application/xml",
        template_filename="U11_template.xlsx",
        build_template=urr_engine.build_urr_template_workbook,
        parse_workbook=urr_engine.parse_urr_workbook,
    ),
    "o41": FilingRegime(
        key="o41", label="O 4.1", authority="CSSF / BCL",
        output_label="O 4.1 EDIFACT filing", output_media_type="text/plain",
        template_filename="O41_template.xlsx",
        build_template=o41_engine.build_o41_template_workbook,
        parse_workbook=o41_engine.parse_o41_workbook,
    ),
    "esef": FilingRegime(
        key="esef", label="ESEF", authority="ESMA",
        output_label="Inline XBRL report", output_media_type="application/xhtml+xml",
        template_filename="ESEF_template.xlsx",
        build_template=esef_engine.build_esef_template_workbook,
        parse_workbook=esef_engine.parse_esef_workbook,
    ),
    "saq": FilingRegime(
        key="saq", label="SAQ", authority="CSSF",
        output_label="SAQ summary workbook", output_media_type=XLSX_MEDIA_TYPE,
        template_filename="SAQ_template.xlsx",
        build_template=saq_engine.build_saq_template_workbook,
        parse_workbook=saq_engine.parse_saq_workbook,
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
    """Reads a filled-in workbook back into a draft the generator accepts.

    The engine's parser returns the workbook's parts (the fund block, the
    share classes, the line items...). The Streamlit ingestion views then
    folded those parts into the flat draft the generation step builds from,
    with their own defaults; that folding is ported here so that what the
    client receives can be posted to ``/generate`` as it is. The parser's
    problems travel alongside under ``errors``.
    """
    regime = _regime(regime_key)
    *data, errors = regime.parse_workbook(content)
    draft = _DRAFT_BUILDERS[regime_key](*data)
    return {**(draft or {}), "errors": list(errors)}


# =============================================================================
# The workbook's parts, folded into a draft
#
# Ported from the "Upload the Excel template completed file" branch of each
# Streamlit ingestion view (views/<regime>_ingestion.py). A part the workbook
# did not fill gets the same default the Streamlit view gave it.
# =============================================================================

def _as_date(value: Any, fallback: date | None = None) -> date | None:
    """A date from whatever a workbook or a JSON client hands over."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip()[:10]).date()
        except ValueError:
            return fallback
    return fallback


def _as_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else fallback
    except (TypeError, ValueError):
        return fallback


def _urr_draft(fund_info: dict[str, Any], share_classes: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not (fund_info or share_classes):
        return None
    today = date.today()
    status = str(fund_info.get("reporting_status", "final report")).strip()
    status = status if status in urr_engine.REPORTING_STATUSES else "final report"
    draft: dict[str, Any] = {
        "reference_month": _as_date(fund_info.get("reference_month"), today.replace(day=1)),
        "reporting_status": status,
        "sender_cssf_code": str(fund_info.get("sender_cssf_code", "")),
        "employee_name": str(fund_info.get("employee_name", "")),
        "employee_phone": str(fund_info.get("employee_phone", "")),
        "sender_email": str(fund_info.get("sender_email", "")),
        "uci_cssf_code": str(fund_info.get("uci_cssf_code", "")),
        "uci_name": str(fund_info.get("uci_name", "")),
        "uci_currency": str(fund_info.get("uci_currency", "EUR")),
        "lei": str(fund_info.get("lei", "")),
        "valuation_date": _as_date(fund_info.get("valuation_date"), today),
        "launch_date": _as_date(fund_info.get("launch_date"), date(2015, 1, 1)),
        "closing_date": _as_date(fund_info.get("closing_date"), None),
        "closing_reason": int(_as_float(fund_info.get("closing_reason"), 0)) or None,
        "nav_frequency": int(_as_float(fund_info.get("nav_frequency"), 1)),
        "redemption_frequency": int(_as_float(fund_info.get("redemption_frequency"), 1)),
        "open_closed_end": int(_as_float(fund_info.get("open_closed_end"), 1)),
    }
    if status == "final report":
        draft.update({
            "nav_preceding_month": _as_float(fund_info.get("nav_preceding_month")),
            "nav_this_month": _as_float(fund_info.get("nav_this_month")),
            "proceeds_issued": _as_float(fund_info.get("proceeds_issued")),
            "payments_redeemed": _as_float(fund_info.get("payments_redeemed")),
            "total_distributions": _as_float(fund_info.get("total_distributions")),
            "share_classes": [_share_class(row) for row in share_classes],
            "income": {key: _as_float(fund_info.get(key)) for key, _ in urr_engine.INCOME_FIELDS},
        })
    return draft


def _share_class(row: dict[str, Any]) -> dict[str, Any]:
    """A share class over its defaults. A cell left empty keeps its default:
    the Streamlit original let the blank overwrite it, and the engine then
    failed on float("") — any partially filled share-class row crashed the
    generation."""
    filled = {key: value for key, value in row.items() if value not in (None, "")}
    return {**urr_engine.SHARE_CLASS_DEFAULT_ROW, **filled}


def _o41_draft(fund_info: dict[str, Any], values: dict[str, float], country_breakdown: list[dict],
               marketing_countries: list[dict]) -> dict[str, Any] | None:
    if not (fund_info or values):
        return None
    today = date.today()
    return {
        "uci_name": str(fund_info.get("uci_name", "")),
        "subfund_name": str(fund_info.get("subfund_name", "")),
        "uci_id": str(fund_info.get("uci_id", "")),
        "subfund_id": str(fund_info.get("subfund_id", "")),
        "year_end": _as_date(fund_info.get("year_end"), date(today.year - 1, 12, 31)),
        "currency": str(fund_info.get("currency", "EUR")),
        "employee_name": str(fund_info.get("employee_name", "")),
        "employee_phone": str(fund_info.get("employee_phone", "")),
        "values": values,
        "country_breakdown": country_breakdown,
        "marketing_countries": marketing_countries,
    }


def _esef_draft(fund_info: dict[str, Any], facts: dict[str, float], notes: dict[str, str]) -> dict[str, Any] | None:
    if not (fund_info or facts):
        return None
    today = date.today()
    return {
        "entity_name": str(fund_info.get("entity_name", "")),
        "lei": str(fund_info.get("lei", "")),
        "currency": str(fund_info.get("currency", "EUR")),
        "period_start": _as_date(fund_info.get("period_start"), today.replace(month=1, day=1)),
        "period_end": _as_date(fund_info.get("period_end"), today),
        "facts": facts,
        "notes": notes,
    }


def _saq_draft(entity_info: dict[str, Any], answers: dict[str, str],
               comments: dict[str, str]) -> dict[str, Any] | None:
    if not (entity_info or answers):
        return None
    return {
        "entity_name": str(entity_info.get("entity_name", "")),
        "uci_type": str(entity_info.get("uci_type", "UCITS")),
        "financial_year_end": _as_date(entity_info.get("financial_year_end"), date.today()),
        "dirigeant_reviewed": bool(entity_info.get("dirigeant_reviewed", False)),
        "answers": answers,
        "comments": comments,
    }


_DRAFT_BUILDERS: dict[str, Callable[..., dict[str, Any] | None]] = {
    "urr": _urr_draft, "o41": _o41_draft, "esef": _esef_draft, "saq": _saq_draft,
}


# =============================================================================
# Building a filing
#
# Ported from the "Generate" branch of each Streamlit generation view
# (views/<regime>_generation.py): the submission is built from the draft with
# the same defaults, the engine's own validation_errors() is run, and a
# submission that fails it is refused rather than turned into a filing. The
# file names are the ones the Streamlit views gave.
#
# A refusal is an answer, not an HTTP error: ``generated`` is False and
# ``errors`` says why, as for BCL and AIFMD.
# =============================================================================

def _refused(errors: list[str]) -> dict[str, Any]:
    return {"generated": False, "errors": errors}


def _produced(regime_key: str, filename: str, media_type: str, *, content: str | None = None,
              content_base64: str | None = None, label: str | None = None) -> dict[str, Any]:
    return {"generated": True, "errors": [], "filename": filename, "media_type": media_type,
            "content": content, "content_base64": content_base64,
            "label": label or REGIMES[regime_key].output_label}


def _required_date(draft: dict[str, Any], key: str) -> date:
    """A date the filing cannot be built without. Missing or unreadable, it
    is the submission that is wrong, hence a ValueError (answered as 400)."""
    value = _as_date(draft.get(key))
    if value is None:
        raise ValueError(f"'{key}' is required and must be a date (YYYY-MM-DD).")
    return value


def _urr_submission(draft: dict[str, Any]) -> urr_engine.UrrSubmission:
    share_classes = []
    for row in draft.get("share_classes") or []:
        share_class = _share_class(row)
        # JSON carries dates as text; the engine calls isoformat() on them.
        for key in ("launch_date", "closing_date"):
            share_class[key] = _as_date(share_class.get(key))
        share_classes.append(share_class)
    return urr_engine.UrrSubmission(
        reference_month=_required_date(draft, "reference_month"),
        reporting_status=draft["reporting_status"],
        sender_cssf_code=draft["sender_cssf_code"], employee_name=draft["employee_name"],
        employee_phone=draft["employee_phone"], sender_email=draft["sender_email"],
        uci_cssf_code=draft["uci_cssf_code"], uci_name=draft["uci_name"], uci_currency=draft["uci_currency"],
        lei=draft.get("lei", ""), valuation_date=_as_date(draft.get("valuation_date")),
        nav_frequency=draft.get("nav_frequency", 1), launch_date=_as_date(draft.get("launch_date")),
        closing_date=_as_date(draft.get("closing_date")), closing_reason=draft.get("closing_reason"),
        redemption_frequency=draft.get("redemption_frequency", 1),
        open_closed_end=draft.get("open_closed_end", 1),
        nav_preceding_month=draft.get("nav_preceding_month", 0.0),
        nav_this_month=draft.get("nav_this_month", 0.0),
        proceeds_issued=draft.get("proceeds_issued", 0.0), payments_redeemed=draft.get("payments_redeemed", 0.0),
        total_distributions=draft.get("total_distributions", 0.0),
        share_classes=share_classes, income=draft.get("income", {}),
    )


def urr_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """U 1.1 — one XML filing per UCI."""
    submission = _urr_submission(payload)
    errors = submission.validation_errors()
    if errors:
        return _refused(errors)
    xml = urr_engine.build_u11_xml(submission)
    filename = f"U11_{submission.uci_cssf_code}_{submission.reference_month.strftime('%Y%m')}.xml"
    return _produced("urr", filename, "application/xml", content=xml)


def o41_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """O 4.1 — an EDIFACT message, not XML."""
    draft = payload
    submission = o41_engine.O41Submission(
        uci_name=draft.get("uci_name", ""), subfund_name=draft.get("subfund_name", ""),
        uci_id=draft.get("uci_id", ""), subfund_id=draft.get("subfund_id", ""),
        year_end=_required_date(draft, "year_end"), currency=draft.get("currency", "EUR"),
        employee_name=draft.get("employee_name", ""), employee_phone=draft.get("employee_phone", ""),
        values=draft.get("values", {}), country_breakdown=draft.get("country_breakdown", []),
        marketing_countries=draft.get("marketing_countries", []),
    )
    errors = submission.validation_errors()
    if errors:
        return _refused(errors)
    message = o41_engine.build_o41_edifact(submission)
    filename = f"O41_{(submission.uci_name or 'entity').replace(' ', '_')}_{submission.year_end.year}.edi"
    return _produced("o41", filename, "text/plain", content=message)


def esef_generate_service(payload: dict[str, Any], as_package: bool = False) -> dict[str, Any]:
    """ESEF — the Inline XBRL document, or the whole report package as a ZIP."""
    draft = payload
    submission = esef_engine.EsefSubmission(
        entity_name=draft.get("entity_name", ""), lei=draft.get("lei", ""),
        currency=draft.get("currency", "EUR"), period_start=_required_date(draft, "period_start"),
        period_end=_required_date(draft, "period_end"), facts=draft.get("facts", {}),
        notes=draft.get("notes", {}),
    )
    errors = submission.validation_errors()
    if errors:
        return _refused(errors)
    ixbrl = esef_engine.build_ixbrl_document(submission)
    if not as_package:
        filename = f"ESEF_{(submission.entity_name or 'entity').replace(' ', '_')}_{submission.period_end.year}.xhtml"
        return _produced("esef", filename, "application/xhtml+xml", content=ixbrl)
    archive, filename = esef_engine.build_report_package(submission, ixbrl)
    return _produced("esef", filename, "application/zip", label="ESEF report package",
                     content_base64=base64.b64encode(archive).decode("ascii"))


def saq_generate_service(payload: dict[str, Any]) -> dict[str, Any]:
    """SAQ — the summary workbook a UCI files with the CSSF."""
    draft = payload
    submission = saq_engine.SaqSubmission(
        entity_name=draft.get("entity_name", ""), uci_type=draft.get("uci_type", "UCITS"),
        financial_year_end=_required_date(draft, "financial_year_end"),
        dirigeant_reviewed=draft.get("dirigeant_reviewed", False),
        answers=draft.get("answers", {}), comments=draft.get("comments", {}),
    )
    errors = submission.validation_errors()
    if errors:
        return _refused(errors)
    workbook = saq_engine.build_saq_summary_workbook(submission)
    filename = (f"SAQ_{(submission.entity_name or 'entity').replace(' ', '_')}_"
                f"{submission.financial_year_end.year}.xlsx")
    return _produced("saq", filename, XLSX_MEDIA_TYPE,
                     content_base64=base64.b64encode(workbook).decode("ascii"))


_GENERATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "urr": urr_generate_service,
    "o41": o41_generate_service,
    "esef": esef_generate_service,
    "saq": saq_generate_service,
}


def filing_generate_service(regime_key: str, payload: dict[str, Any], **options: Any) -> dict[str, Any]:
    _regime(regime_key)
    try:
        return _GENERATORS[regime_key](payload, **options)
    except KeyError as exc:
        # A field the Streamlit view read unconditionally is missing: the
        # submission is incomplete, which is the client's to fix.
        raise ValueError(f"'{exc.args[0]}' is required.") from exc
