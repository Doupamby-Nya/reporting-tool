"""The capture form of each regime, described as data.

A reporting form is not free-form: every field exists because the regulator
asks for it, and the generator reads it back under an exact name. Writing
those forms by hand in the client means transcribing hundreds of field names
a second time, and a transcription drifts — a field renamed in the engine
keeps working in the form and silently stops reaching the filing.

So the form is derived here, from the same two sources the generator uses:
the submission dataclass (which names and types every field) and the
engine's own label lists (which carry the regulator's wording and item
numbers). The client renders whatever it is given.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
from typing import Any, get_args

from domain.aifmd import aifmd_engine
from domain.esef import esef_engine
from domain.o41 import o41_engine
from domain.saq import saq_engine
from domain.urr import urr_engine


# =============================================================================
# Turning a dataclass field into a form field
# =============================================================================

def _type_of(annotation: Any) -> str:
    """The input a value of this type needs.

    Optionals are unwrapped first: `date | None` is still a date field, it is
    simply one the regulator does not always require.
    """
    text = getattr(annotation, "__name__", None) or str(annotation)
    for argument in get_args(annotation):
        if argument is not type(None):
            text = getattr(argument, "__name__", None) or str(argument)
            break
    if "date" in text:
        return "date"
    if "bool" in text:
        return "boolean"
    if "int" in text:
        return "integer"
    if "float" in text:
        return "number"
    return "text"


def _labels(pairs: list[tuple[str, str]]) -> dict[str, str]:
    return {key: label for key, label in pairs}


def _humanise(key: str) -> str:
    return key.replace("_", " ").replace(" id", " ID").strip().capitalize()


def _scalar_fields(cls: Any, labels: dict[str, str], skip: set[str],
                   options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every scalar of a submission, in the order the dataclass declares it —
    which is the order the regulator's own form follows."""
    options = options or {}
    fields = []
    for field in dataclasses.fields(cls):
        if field.name in skip:
            continue
        entry: dict[str, Any] = {
            "key": field.name,
            "label": labels.get(field.name) or _humanise(field.name),
            "type": _type_of(field.type),
        }
        if field.name in options:
            entry["type"] = "select"
            entry["options"] = options[field.name]
        fields.append(entry)
    return fields


# =============================================================================
# U 1.1
# =============================================================================

def _urr_form() -> dict[str, Any]:
    fund_labels = _labels(urr_engine.FUND_INFO_FIELDS)
    class_labels = _labels(urr_engine.SHARE_CLASS_FIELDS)

    return {
        "title": "U 1.1 — Monthly financial information",
        "description": "Circular CSSF 15/627. Every field carries its own item number.",
        "sections": [
            {
                "key": "", "title": "Fund information", "kind": "fields",
                "fields": _scalar_fields(urr_engine.UrrSubmission, fund_labels,
                                         skip={"share_classes", "income"}),
            },
            {
                "key": "share_classes", "title": "Unit / share classes", "kind": "table",
                "hint": "One row per class. Each becomes its own Unit_Share_Information block.",
                "columns": [{"key": key, "label": label,
                             "type": "date" if key.endswith("_date") else
                                     "number" if key.startswith(("units_", "nav_", "net_",
                                                                 "distrib", "income", "expenses"))
                                     else "text"}
                            for key, label in urr_engine.SHARE_CLASS_FIELDS],
                "labels": class_labels,
            },
            {
                "key": "income", "title": "Income & expenses", "kind": "amounts",
                "hint": "Section 6. An empty field means not reported, which is not a zero.",
                "fields": [{"key": key, "label": label.strip()}
                           for key, label in urr_engine.INCOME_FIELDS],
            },
        ],
    }


# =============================================================================
# O 4.1
# =============================================================================

def _o41_form() -> dict[str, Any]:
    groups = []
    for section in o41_engine.SECTIONS:
        groups.append({
            "title": section,
            "fields": [{"key": code, "label": f"{code} — {label.strip()}"}
                       for code, label, item_section in o41_engine.LINE_ITEMS
                       if item_section == section],
        })

    return {
        "title": "O 4.1 — Circular IML 97/136",
        "description": "Annexe B, filed as EDIFACT. The cross-check formulas run at the rules step.",
        "sections": [
            {
                "key": "", "title": "Identification", "kind": "fields",
                "fields": _scalar_fields(o41_engine.O41Submission, {},
                                         skip={"values", "country_breakdown", "marketing_countries"}),
            },
            {
                "key": "values", "title": "Annexe B line items", "kind": "amounts",
                "groups": groups,
            },
            {
                "key": "country_breakdown", "title": "Securities portfolio by country",
                "kind": "table", "hint": "Section V — free-form rather than a fixed per-country grid.",
                "columns": [
                    {"key": "country", "label": "Country", "type": "country"},
                    {"key": "amount", "label": "Amount", "type": "number"},
                ],
            },
            {
                "key": "marketing_countries", "title": "Marketing countries", "kind": "table",
                "hint": "Section VI — the shares should total 100 %.",
                "columns": [
                    {"key": "country", "label": "Country", "type": "country"},
                    {"key": "pct", "label": "Share (%)", "type": "number"},
                ],
            },
        ],
    }


# =============================================================================
# ESEF
# =============================================================================

def _esef_form() -> dict[str, Any]:
    groups = []
    for statement in esef_engine.STATEMENTS:
        groups.append({
            "title": statement,
            "fields": [{"key": mapping["key"], "label": mapping["label"],
                        "hint": f"ifrs-full:{mapping['concept']}"}
                       for mapping in esef_engine.MAPPING_SCHEMA
                       if mapping["statement"] == statement],
        })

    return {
        "title": "ESEF — Inline XBRL annual report",
        "description": "Delegated Regulation (EU) 2019/815. Each figure is tagged to a real IFRS concept.",
        "sections": [
            {
                "key": "", "title": "Entity and period", "kind": "fields",
                "fields": _scalar_fields(esef_engine.EsefSubmission, {}, skip={"facts", "notes"}),
            },
            {
                "key": "facts", "title": "Primary statements", "kind": "amounts", "groups": groups,
            },
            {
                "key": "notes", "title": "Notes (block-tagged)", "kind": "texts",
                "hint": "Each note is tagged as one ix:nonNumeric text block.",
                "fields": [{"key": note["key"], "label": note["label"],
                            "hint": f"ifrs-full:{note['concept']}"}
                           for note in esef_engine.NOTES_CONCEPTS],
            },
        ],
    }


# =============================================================================
# SAQ
# =============================================================================

def _saq_form() -> dict[str, Any]:
    sections = dict(saq_engine.SAQ_SECTIONS)
    groups = []
    for key, title in saq_engine.SAQ_SECTIONS:
        groups.append({
            "title": title,
            "fields": [{"key": question["key"], "label": question["question"],
                        "hint": question.get("citation", "")}
                       for question in saq_engine.SAQ_QUESTIONS
                       if question["section"] == key],
        })

    return {
        "title": "SAQ — Circular CSSF 21/790",
        "description": "The self-assessment, for four-eyes review and record-keeping ahead of the "
                       "eDesk filing.",
        "sections": [
            {
                "key": "", "title": "Entity", "kind": "fields",
                "fields": _scalar_fields(
                    saq_engine.SaqSubmission, {}, skip={"answers", "comments"},
                    options={"uci_type": {key: label
                                          for key, (label, _months) in saq_engine.UCI_TYPES.items()}}),
            },
            {
                "key": "answers", "title": "Self-assessment", "kind": "questions",
                "hint": "One answer per sub-topic the CSSF describes in its feedback report.",
                "groups": groups,
                "choices": ["Yes", "Partially", "No", "Not applicable"],
                "comments_key": "comments",
            },
        ],
        "sections_index": sections,
    }



# =============================================================================
# AIFMD Annex IV
# =============================================================================
#
# The AIFM and AIF dictionaries carry 339 items between them, and unlike the
# other regimes there is no label list to read them from. What there is, and
# what matters, is the generator: `submission_from_dicts` names every key it
# reads out of each dictionary, and a key it does not read cannot reach the
# filing whatever a form does with it.
#
# So the field names are taken from that function's own source. It is an
# unusual thing to do and deliberate: the alternative is a hand-written list
# of 339 names that agrees with the generator on the day it is written and
# quietly stops agreeing afterwards. Reading the generator means a renamed
# key changes the form in the same commit.

_KEY_PATTERN = re.compile(r'\bf\(\s*(aifm_info|aif_info)\s*,\s*"([a-z0-9_]+)"')
_GET_PATTERN = re.compile(r'\b(aifm_info|aif_info)\.get\(\s*"([a-z0-9_]+)"')

# The code lists the engine enumerates, against the fields that take them.
_AIFMD_OPTIONS: dict[str, str] = {
    "sender_entity_type": "SENDER_ENTITY_TYPES",
    "aifm_filing_type": "FILING_TYPES",
    "aif_filing_type": "FILING_TYPES",
    "aifm_content_type": "AIFM_CONTENT_TYPES",
    "aif_content_type": "AIF_CONTENT_TYPES",
    "reporting_period_type": "REPORTING_PERIOD_TYPES",
    "aifm_reporting_code": "AIFM_REPORTING_CODES",
    "aif_reporting_code": "AIF_REPORTING_CODES",
    "aif_legal_form": "AIF_LEGAL_FORM_CODES",
    "aif_master_feeder_status": "MASTER_FEEDER_STATUS",
    "predominant_aif_type": "PREDOMINANT_AIF_TYPES",
    "aifm_fx_ref_rate_type": "FX_EUR_REFERENCE_RATE_TYPES",
    "aif_fx_ref_rate_type": "FX_EUR_REFERENCE_RATE_TYPES",
    "aif_redemption_frequency": "REDEMPTION_FREQUENCIES",
    "var_calc_method": "VAR_CALC_METHODS",
}

# Keys whose value is a list of records rather than a scalar. They are the
# repeating blocks of the filing, and each is a table on the form.
_AIFMD_TABLES: dict[str, list[tuple[str, str]]] = {
    "aifm_assumptions": [("question_number", "number"), ("description", "text")],
    "aif_assumptions": [("question_number", "number"), ("description", "text")],
    "aifm_principal_markets": [("ranking", "number"), ("market_code_type", "text"),
                               ("market_code", "text"), ("aggregated_value", "number")],
    "aifm_principal_instruments": [("ranking", "number"), ("sub_asset_type", "text"),
                                   ("aggregated_value", "number")],
    "aif_share_classes": [("name", "text"), ("isin", "text"), ("national_code", "text"),
                          ("cusip", "text"), ("sedol", "text"), ("bloomberg", "text"),
                          ("reuters", "text")],
    "aif_master_aifs": [("name", "text"), ("lei", "text")],
    "aif_prime_brokers": [("name", "text"), ("lei", "text"), ("bic", "text")],
    "investment_strategies": [("group", "text"), ("code", "text"), ("primary_flag", "text"),
                              ("nav_rate", "number"), ("other_description", "text")],
    "main_instruments": [("ranking", "number"), ("sub_asset_type", "text"),
                         ("instrument_name", "text"), ("isin", "text"),
                         ("position_value", "number"), ("position_type", "text")],
    "ten_principal_exposures": [("ranking", "number"), ("macro_type", "text"),
                                ("sub_asset_type", "text"), ("position_type", "text"),
                                ("aggregated_value", "number"), ("aggregated_value_pct", "number"),
                                ("counterparty_name", "text"), ("counterparty_lei", "text")],
}


def _aifmd_keys() -> tuple[list[str], list[str]]:
    """Every key the generator reads, in the order it reads them."""
    source = inspect.getsource(aifmd_engine.submission_from_dicts)
    aifm: list[str] = []
    aif: list[str] = []
    for pattern in (_KEY_PATTERN, _GET_PATTERN):
        for which, key in pattern.findall(source):
            target = aifm if which == "aifm_info" else aif
            if key not in target:
                target.append(key)
    return aifm, aif


def _aifmd_sections(prefix: str, keys: list[str], title: str) -> list[dict[str, Any]]:
    types = {field.name: field.type for field in dataclasses.fields(aifmd_engine.AifmdSubmission)}
    scalars: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []

    for key in keys:
        if key in _AIFMD_TABLES:
            tables.append({
                "key": f"{prefix}.{key}", "title": _humanise(key), "kind": "table",
                "columns": [{"key": column, "label": _humanise(column), "type": kind}
                            for column, kind in _AIFMD_TABLES[key]],
            })
            continue
        entry: dict[str, Any] = {
            "key": key, "label": _humanise(key),
            "type": _type_of(types.get(key, str)),
        }
        listed = _AIFMD_OPTIONS.get(key)
        if listed and hasattr(aifmd_engine, listed):
            codes = getattr(aifmd_engine, listed)
            entry["type"] = "select"
            entry["options"] = dict(codes) if not isinstance(codes, dict) else codes
        scalars.append(entry)

    return [{"key": prefix, "title": title, "kind": "fields", "fields": scalars}, *tables]


# ESMA's consolidated workbook holds four templates, not one, and which of
# them a filing has to fill is not a choice — the AIF content type decides
# it. A preparer looking at the workbook cannot tell which sheet applies to
# them, so the form states it.
_AIFMD_TEMPLATES = {
    "AIFM file 24(1)": "Always, for the manager.",
    "AIF file 24(1)": "Always, for each fund.",
    "AIF file 24(2)": "Content type 2 or 4.",
    "AIF file 24(4)": "Content type 4 or 5.",
}

_AIF_CONTENT_TEMPLATES = {
    "1": ["AIFM file 24(1)", "AIF file 24(1)"],
    "2": ["AIFM file 24(1)", "AIF file 24(1)", "AIF file 24(2)"],
    "3": ["AIFM file 24(1)", "AIF file 24(1)"],
    "4": ["AIFM file 24(1)", "AIF file 24(1)", "AIF file 24(2)", "AIF file 24(4)"],
    "5": ["AIFM file 24(1)", "AIF file 24(1)", "AIF file 24(4)"],
}


def _aifmd_form() -> dict[str, Any]:
    aifm_keys, aif_keys = _aifmd_keys()
    return {
        "title": "AIFMD Annex IV",
        "description": "The AIFM-level (DATMAN) and AIF-level (DATAIF) items, as the generator reads "
                       "them. Fixed-cardinality blocks are padded automatically at generation.",
        "templates": _AIFMD_TEMPLATES,
        "template_rule": {
            "field": "aif_info.aif_content_type",
            "label": "AIF content type",
            "options": dict(aifmd_engine.AIF_CONTENT_TYPES),
            "applies": _AIF_CONTENT_TEMPLATES,
        },
        "sections": [
            {"key": "", "title": "Reporting period", "kind": "fields", "fields": [
                {"key": "period_start", "label": "Period start", "type": "date"},
                {"key": "period_end", "label": "Period end", "type": "date"},
            ]},
            *_aifmd_sections("aifm_info", aifm_keys, "AIFM file (DATMAN)"),
            *_aifmd_sections("aif_info", aif_keys, "AIF file (DATAIF)"),
        ],
    }

_FORMS = {"aifmd": _aifmd_form, "urr": _urr_form, "o41": _o41_form, "esef": _esef_form, "saq": _saq_form}


def filing_form_service(regime_key: str) -> dict[str, Any]:
    """The capture form of one regime."""
    builder = _FORMS.get(regime_key)
    if builder is None:
        raise LookupError(f"No capture form for regime '{regime_key}'; "
                          f"expected one of {', '.join(_FORMS)}.")
    return builder()
