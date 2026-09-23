"""What each regime's rules-engine step shows.

For U 1.1, O 4.1, ESEF and SAQ the rules engine is a mapping catalogue: every
field the platform captures, the exact regulator element it is tagged to, and
whether the current submission fills it. The catalogue is read from the same
engine constants the generators use, so the screen can never describe a
mapping the generator does not apply.

O 4.1 additionally carries real arithmetic: the 23 cross-check formulas
printed below Annexe B of Circular IML 97/136, which are evaluated here
against the submission rather than merely listed.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from domain.esef import esef_engine
from domain.o41 import o41_engine
from domain.saq import saq_engine
from domain.urr import urr_engine, urr_mapping


def _filled(value: Any) -> bool:
    """A field counts as filled when it carries a real value. Zero is not one:
    an amount left at zero is the default of every untouched numeric input, so
    counting it would overstate how much of a submission is actually done."""
    return value not in (None, "", 0)


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# =============================================================================
# U 1.1
# =============================================================================

def _urr_rules(draft: dict[str, Any]) -> dict[str, Any]:
    share_classes = draft.get("share_classes") or []
    income = draft.get("income") or {}

    fund_rows = [
        {"key": key, "label": label,
         "path": urr_mapping.FUND_INFO_XML_MAP.get(key, ""),
         "filled": _filled(draft.get(key))}
        for key, label in urr_engine.FUND_INFO_FIELDS
    ]
    class_rows = [
        {"key": key, "label": label, "path": urr_mapping.SHARE_CLASS_XML_MAP.get(key, ""),
         "filled": any(_filled((row or {}).get(key)) for row in share_classes)}
        for key, label in urr_engine.SHARE_CLASS_FIELDS
    ]
    income_rows = [
        {"key": key, "label": label.strip(), "path": urr_mapping.INCOME_XML_MAP.get(key, ""),
         "filled": _filled(income.get(key))}
        for key, label in urr_engine.INCOME_FIELDS
    ]

    return {
        "title": "U 1.1 — Rules Engine",
        "description": "Field-to-XML mapping: each Fund_Info, Share_Class and Income & Expenses field "
                       "tagged to its real U 1.1 element name (Circular CSSF 15/627).",
        "coverage": [
            {"label": "Fund info fields",
             "value": f"{sum(1 for r in fund_rows if r['filled'])} / {len(fund_rows)}",
             "hint": "filled in this submission"},
            {"label": "Share classes", "value": str(len(share_classes)), "hint": "in this submission"},
            {"label": "Income & expense fields",
             "value": f"{sum(1 for r in income_rows if r['filled'])} / {len(income_rows)}",
             "hint": "filled in this submission"},
            {"label": "Reporting status", "value": draft.get("reporting_status") or "—", "hint": ""},
        ],
        "tables": [
            {"title": "Fund_Info", "column": "Real XML path", "rows": fund_rows},
            {"title": "Share_Classes", "column": "Real XML path", "rows": class_rows,
             "note": f"{len(share_classes)} share class(es) in this submission — one "
                     f"Unit_Share_Information block per class."},
            {"title": "Income & Expenses", "column": "Real XML path", "rows": income_rows},
        ],
        "errors": [],
        "note": "Every element name and nesting above is copied from the generator itself, which was "
                "built from a real CSSF example workbook (version 5.1 - 12/2025 of the U 1.1 spec). A "
                "'null report' only tags GeneralInformation and UCISignaBasic — the fields below "
                "Section 2 are specific to a final report.",
    }


# =============================================================================
# O 4.1
# =============================================================================

def _o41_rules(draft: dict[str, Any]) -> dict[str, Any]:
    values = draft.get("values") or {}
    marketing = draft.get("marketing_countries") or []

    errors: list[str] = []
    if draft:
        submission = o41_engine.O41Submission(
            uci_name=draft.get("uci_name", ""), subfund_name=draft.get("subfund_name", ""),
            uci_id=draft.get("uci_id", ""), subfund_id=draft.get("subfund_id", ""),
            year_end=_as_date(draft.get("year_end")), currency=draft.get("currency", "EUR"),
            employee_name=draft.get("employee_name", ""), employee_phone=draft.get("employee_phone", ""),
            values=values, marketing_countries=marketing,
        )
        errors = submission.validation_errors()

    formula_errors = sum(1 for message in errors if "validation formula" in message)
    marketing_total = sum(float(row.get("pct") or 0) for row in marketing) if marketing else None

    tables = []
    for section in o41_engine.SECTIONS:
        rows = [
            {"key": code, "label": label.strip(),
             "path": f"1-{o41_engine.EDIFACT_CODE_MAP[code]}",
             "code": code, "filled": code in values}
            for code, label, item_section in o41_engine.LINE_ITEMS if item_section == section
        ]
        tables.append({"title": section, "column": "EDIFACT wire code", "rows": rows})

    if not draft:
        status = "—"
    elif formula_errors == 0:
        status = "Consistent"
    else:
        status = f"{formula_errors} mismatch(es)"

    return {
        "title": "O 4.1 — Rules Engine",
        "description": "Line-code mapping and the validation formulas of Annexe B, Circular IML 97/136, "
                       "evaluated against the submission saved at the ingestion step.",
        "coverage": [
            {"label": "Line items mapped",
             "value": f"{sum(1 for code, _, _ in o41_engine.LINE_ITEMS if code in values)} / "
                      f"{len(o41_engine.LINE_ITEMS)}",
             "hint": "filled in this submission"},
            {"label": "Validation formulas", "value": str(len(o41_engine.VALIDATION_FORMULAS) + 1),
             "hint": "from Annexe B"},
            {"label": "Cross-check status", "value": status, "hint": ""},
            {"label": "Marketing countries total",
             "value": f"{marketing_total:.1f}%" if marketing_total is not None else "—",
             "hint": "should equal 100%"},
        ],
        "tables": tables,
        "errors": errors,
        "note": "Line codes and labels come from Annexe B of Circular IML 97/136; the EDIFACT wire codes "
                "are that annex's codes renumbered per the CSSF's 'Table O 4.1' technical note (a "
                "trailing 0, except the four documented exceptions 1112/1113/1114/1115).",
    }


# =============================================================================
# ESEF
# =============================================================================

def _esef_rules(draft: dict[str, Any]) -> dict[str, Any]:
    facts = draft.get("facts") or {}
    notes = draft.get("notes") or {}

    coverage = [{"label": "Line items mapped", "value": str(len(esef_engine.MAPPING_SCHEMA)), "hint": ""}]
    tables = []
    for statement in esef_engine.STATEMENTS:
        items = [m for m in esef_engine.MAPPING_SCHEMA if m["statement"] == statement]
        coverage.append({
            "label": statement,
            "value": f"{sum(1 for m in items if m['key'] in facts)} / {len(items)}",
            "hint": "filled in this submission",
        })
        tables.append({
            "title": statement, "column": "IFRS taxonomy concept",
            "rows": [
                {"key": m["key"], "label": m["label"], "path": f"ifrs-full:{m['concept']}",
                 "period_type": m["period_type"], "balance": m["balance"] or "—",
                 "filled": m["key"] in facts}
                for m in items
            ],
        })

    coverage.append({
        "label": "Notes block-tagged",
        "value": f"{sum(1 for n in esef_engine.NOTES_CONCEPTS if n['key'] in notes)} / "
                 f"{len(esef_engine.NOTES_CONCEPTS)}",
        "hint": "filled in this submission",
    })
    tables.append({
        "title": "Notes (block-tagged)", "column": "IFRS taxonomy concept",
        "rows": [
            {"key": n["key"], "label": n["label"], "path": f"ifrs-full:{n['concept']}",
             "fact_type": "ix:nonNumeric (text block)", "filled": n["key"] in notes}
            for n in esef_engine.NOTES_CONCEPTS
        ],
    })

    return {
        "title": "ESEF — Rules Engine",
        "description": "Mapping schema: each statement line item and note tagged to its real IFRS "
                       "Accounting Taxonomy concept (Delegated Regulation (EU) 2019/815).",
        "coverage": coverage,
        "tables": tables,
        "errors": [],
        "note": "The extension schema declares no custom elements, ships no label or calculation "
                "linkbase, and none of this has been run through an XBRL processor against the official "
                "ESEF conformance suite — do that before submitting to the OAM.",
    }


# =============================================================================
# SAQ
# =============================================================================

def _saq_rules(draft: dict[str, Any]) -> dict[str, Any]:
    uci_type = draft.get("uci_type")
    year_end = _as_date(draft.get("financial_year_end"))
    answers = draft.get("answers") or {}

    label, months = saq_engine.UCI_TYPES.get(uci_type, (uci_type or "—", 0))
    deadline = saq_engine.compute_deadline(uci_type, year_end) if uci_type and year_end else None
    sections = dict(saq_engine.SAQ_SECTIONS)

    return {
        "title": "SAQ — Rules Engine",
        "description": "Applicability scope and submission deadline rule (Circular CSSF 21/790, "
                       "Section 2.1), computed from the submission saved at the ingestion step.",
        "coverage": [
            {"label": "UCI type", "value": label, "hint": ""},
            {"label": "Filing window", "value": f"{months} months" if months else "—",
             "hint": "after financial year-end"},
            {"label": "Submission deadline", "value": deadline.isoformat() if deadline else "—", "hint": ""},
            {"label": "Sub-topics self-assessed",
             "value": f"{sum(1 for q in saq_engine.SAQ_QUESTIONS if q['key'] in answers)} / "
                      f"{len(saq_engine.SAQ_QUESTIONS)}", "hint": "in this submission"},
        ],
        "tables": [
            {"title": "Applicability scope (Circular CSSF 21/790, Section 1)", "column": "Deadline",
             "rows": [
                 {"key": key, "label": type_label,
                  "path": f"{type_months} months after financial year-end",
                  "filled": key == uci_type}
                 for key, (type_label, type_months) in saq_engine.UCI_TYPES.items()
             ]},
            {"title": "Self-assessment sections and sub-topics", "column": "Section",
             "rows": [
                 {"key": question["key"], "label": question["question"],
                  "path": sections.get(question["section"], question["section"]),
                  "filled": question["key"] in answers}
                 for question in saq_engine.SAQ_QUESTIONS
             ]},
        ],
        "errors": [],
        "note": "The SAQ is filed on CSSF's eDesk portal (CISERO module); there is no public XML schema "
                "to generate against. The generation step produces an internal summary for four-eyes "
                "review and record-keeping ahead of the actual eDesk filing, not the SAQ itself.",
    }


_RULES = {"urr": _urr_rules, "o41": _o41_rules, "esef": _esef_rules, "saq": _saq_rules}


def filing_rules_service(regime_key: str, draft: dict[str, Any] | None = None) -> dict[str, Any]:
    """The rules-engine view of one regime, against an optional submission."""
    builder = _RULES.get(regime_key)
    if builder is None:
        raise LookupError(f"No rules catalogue for regime '{regime_key}'; "
                          f"expected one of {', '.join(_RULES)}.")
    return builder(draft or {})
