"""Builds the expected outputs of the non-regression cases from the Streamlit MVP.

    cd Backend/api
    poetry run python tests/non_regression/oracle.py <path to PRIIPS_KID_MVP_streamlit_v20260902>

The reference files under ``reference/`` are what the Streamlit tool produced
for each case in ``cases.py``. test_non_regression.py then asks the API for
the same case and requires the same answer. Run this again only to re-anchor
the references on purpose — for instance after a deliberate change of
behaviour — and say so in the commit.

How the Streamlit side is driven
--------------------------------
The engines are imported from the MVP's own ``core`` package, never from this
API's ``domain``. What the Streamlit *views* did around them — turning a draft
into a submission, running the checks, naming the file — is reused where it
is a function (the BCL helpers), and transcribed from the view otherwise; each
transcription names the view and lines it comes from. ``streamlit`` itself is
replaced by an inert module so the views can be imported without a browser.

One deliberate substitution: the Streamlit code reads its configuration (RTS
calibration, KID templates, app settings) from this API's resources rather
than from the MVP's data/ folder. The comparison is about code, not about
two copies of a settings file drifting apart.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import types
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
API_ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import cases as case_catalogue  # noqa: E402
import normalize  # noqa: E402

warnings.filterwarnings("ignore")


# =============================================================================
# Loading the Streamlit MVP
# =============================================================================

class _Inert:
    """Stands in for any streamlit attribute: callable, subscriptable, a
    context manager, and a pass-through decorator."""

    def __getattr__(self, _name: str) -> "_Inert":
        return _Inert()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return _Inert()

    def __enter__(self) -> "_Inert":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def __iter__(self):
        return iter(())

    def __getitem__(self, _key: Any) -> "_Inert":
        return _Inert()

    def __contains__(self, _key: Any) -> bool:
        return False


def load_streamlit_mvp(root: Path) -> types.SimpleNamespace:
    streamlit = types.ModuleType("streamlit")
    streamlit.__getattr__ = lambda name: _Inert()  # type: ignore[attr-defined]
    sys.modules["streamlit"] = streamlit
    sys.path.insert(0, str(root))

    from core import aifmd_engine, aifmd_xsd, bcl_engine, bcl_s220_engine, bcl_xsd, esef_engine
    from core import fatca_pipeline, kid_generator, o41_engine, priips_engine, saq_engine, templates
    from core import urr_engine
    from core.xml_common import errors_of
    from views import bcl_generation, bcl_ingestion

    # The configuration substitution described in the module docstring.
    config = API_ROOT / "src" / "resources"
    templates.CONFIG_DIR = config / "config"
    templates.TEMPLATES_DIR = config / "templates"
    templates.RTS_PARAMETERS_JSON = templates.CONFIG_DIR / "rts_parameters.json"
    templates.APP_SETTINGS_JSON = templates.CONFIG_DIR / "app_settings.json"

    for module in (urr_engine, bcl_engine, aifmd_engine, fatca_pipeline):
        assert Path(module.__file__).resolve().is_relative_to(root.resolve()), \
            f"{module.__name__} was not loaded from the Streamlit MVP"

    return types.SimpleNamespace(**locals())


# =============================================================================
# Helpers
# =============================================================================

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def to_dates(value: Any) -> Any:
    """ISO strings back to dates: the Streamlit widgets held date objects."""
    if isinstance(value, str) and _ISO_DATE.match(value):
        return date.fromisoformat(value)
    if isinstance(value, dict):
        return {k: to_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dates(v) for v in value]
    return value


def _as_date(value: Any, fallback: date | None) -> date | None:
    """views/*_ingestion.py::_as_date, identical in the four views."""
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
    """views/urr_ingestion.py::_as_float."""
    try:
        return float(value) if value not in (None, "") else fallback
    except (TypeError, ValueError):
        return fallback


def refused(errors: list) -> dict[str, Any]:
    return {"generated": False, "errors": errors, "files": []}


def produced(files: list[dict[str, Any]]) -> dict[str, Any]:
    return {"generated": True, "errors": [], "files": files}


def text_file(filename: str, content: str, **extra: Any) -> dict[str, Any]:
    return {"filename": normalize.filename(filename), "content": normalize.text(content), **extra}


def workbook_file(filename: str, content: bytes) -> dict[str, Any]:
    return {"filename": normalize.filename(filename), "cells": normalize.workbook(content)}


def issue_list(issues) -> list[list[str]]:
    return [[issue.code, issue.message] for issue in issues]


# =============================================================================
# U 1.1 / O 4.1 / ESEF / SAQ
# =============================================================================

def ingest(mvp, regime: str, content: bytes) -> dict[str, Any] | None:
    """The upload branch of views/<regime>_ingestion.py. ``current_user`` is
    empty: the oracle has no session."""
    today = date.today()
    if regime == "urr":  # views/urr_ingestion.py, lines 118-157
        fund_info, share_classes, _errors = mvp.urr_engine.parse_urr_workbook(content)
        if not (fund_info or share_classes):
            return None
        status = str(fund_info.get("reporting_status", "final report")).strip()
        status = status if status in mvp.urr_engine.REPORTING_STATUSES else "final report"
        draft = {
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
            seeded = []
            for row in share_classes:
                r = dict(mvp.urr_engine.SHARE_CLASS_DEFAULT_ROW)
                r.update(row)
                seeded.append(r)
            draft.update({
                "nav_preceding_month": _as_float(fund_info.get("nav_preceding_month")),
                "nav_this_month": _as_float(fund_info.get("nav_this_month")),
                "proceeds_issued": _as_float(fund_info.get("proceeds_issued")),
                "payments_redeemed": _as_float(fund_info.get("payments_redeemed")),
                "total_distributions": _as_float(fund_info.get("total_distributions")),
                "share_classes": seeded,
                "income": {key: _as_float(fund_info.get(key)) for key, _ in mvp.urr_engine.INCOME_FIELDS},
            })
        return draft
    if regime == "o41":  # views/o41_ingestion.py, lines 75-92
        fund_info, values, country_breakdown, marketing_countries, _e = mvp.o41_engine.parse_o41_workbook(content)
        if not (fund_info or values):
            return None
        return {
            "uci_name": str(fund_info.get("uci_name", "")), "subfund_name": str(fund_info.get("subfund_name", "")),
            "uci_id": str(fund_info.get("uci_id", "")), "subfund_id": str(fund_info.get("subfund_id", "")),
            "year_end": _as_date(fund_info.get("year_end"), date(today.year - 1, 12, 31)),
            "currency": str(fund_info.get("currency", "EUR")),
            "employee_name": str(fund_info.get("employee_name", "")),
            "employee_phone": str(fund_info.get("employee_phone", "")),
            "values": values, "country_breakdown": country_breakdown, "marketing_countries": marketing_countries,
        }
    if regime == "esef":  # views/esef_ingestion.py, lines 77-90
        fund_info, facts, notes, _errors = mvp.esef_engine.parse_esef_workbook(content)
        if not (fund_info or facts):
            return None
        return {
            "entity_name": str(fund_info.get("entity_name", "")), "lei": str(fund_info.get("lei", "")),
            "currency": str(fund_info.get("currency", "EUR")),
            "period_start": _as_date(fund_info.get("period_start"), today.replace(month=1, day=1)),
            "period_end": _as_date(fund_info.get("period_end"), today),
            "facts": facts, "notes": notes,
        }
    if regime == "saq":  # views/saq_ingestion.py, lines 76-88
        entity_info, answers, comments, _errors = mvp.saq_engine.parse_saq_workbook(content)
        if not (entity_info or answers):
            return None
        return {
            "entity_name": str(entity_info.get("entity_name", "")),
            "uci_type": str(entity_info.get("uci_type", "UCITS")),
            "financial_year_end": _as_date(entity_info.get("financial_year_end"), today),
            "dirigeant_reviewed": bool(entity_info.get("dirigeant_reviewed", False)),
            "answers": answers, "comments": comments,
        }
    raise LookupError(regime)


def generate_filing(mvp, regime: str, draft: dict[str, Any]) -> dict[str, Any]:
    """The Generate branch of views/<regime>_generation.py."""
    if regime == "urr":  # views/urr_generation.py, lines 38-66
        share_classes = []
        for row in draft.get("share_classes", []):
            sc = dict(mvp.urr_engine.SHARE_CLASS_DEFAULT_ROW)
            sc.update(row)
            share_classes.append(sc)
        sub = mvp.urr_engine.UrrSubmission(
            reference_month=draft["reference_month"], reporting_status=draft["reporting_status"],
            sender_cssf_code=draft["sender_cssf_code"], employee_name=draft["employee_name"],
            employee_phone=draft["employee_phone"], sender_email=draft["sender_email"],
            uci_cssf_code=draft["uci_cssf_code"], uci_name=draft["uci_name"], uci_currency=draft["uci_currency"],
            lei=draft.get("lei", ""), valuation_date=draft.get("valuation_date"),
            nav_frequency=draft.get("nav_frequency", 1), launch_date=draft.get("launch_date"),
            closing_date=draft.get("closing_date"), closing_reason=draft.get("closing_reason"),
            redemption_frequency=draft.get("redemption_frequency", 1),
            open_closed_end=draft.get("open_closed_end", 1),
            nav_preceding_month=draft.get("nav_preceding_month", 0.0), nav_this_month=draft.get("nav_this_month", 0.0),
            proceeds_issued=draft.get("proceeds_issued", 0.0), payments_redeemed=draft.get("payments_redeemed", 0.0),
            total_distributions=draft.get("total_distributions", 0.0),
            share_classes=share_classes, income=draft.get("income", {}),
        )
        errors = sub.validation_errors()
        if errors:
            return refused(errors)
        filename = f"U11_{sub.uci_cssf_code}_{sub.reference_month.strftime('%Y%m')}.xml"
        return produced([text_file(filename, mvp.urr_engine.build_u11_xml(sub))])
    if regime == "o41":  # views/o41_generation.py, lines 38-56
        sub = mvp.o41_engine.O41Submission(
            uci_name=draft.get("uci_name", ""), subfund_name=draft.get("subfund_name", ""),
            uci_id=draft.get("uci_id", ""), subfund_id=draft.get("subfund_id", ""),
            year_end=draft["year_end"], currency=draft.get("currency", "EUR"),
            employee_name=draft.get("employee_name", ""), employee_phone=draft.get("employee_phone", ""),
            values=draft.get("values", {}), country_breakdown=draft.get("country_breakdown", []),
            marketing_countries=draft.get("marketing_countries", []),
        )
        errors = sub.validation_errors()
        if errors:
            return refused(errors)
        filename = f"O41_{(sub.uci_name or 'entity').replace(' ', '_')}_{sub.year_end.year}.edi"
        return produced([text_file(filename, mvp.o41_engine.build_o41_edifact(sub))])
    if regime == "esef":  # views/esef_generation.py, lines 38-56
        sub = mvp.esef_engine.EsefSubmission(
            entity_name=draft.get("entity_name", ""), lei=draft.get("lei", ""),
            currency=draft.get("currency", "EUR"), period_start=draft["period_start"],
            period_end=draft["period_end"], facts=draft.get("facts", {}), notes=draft.get("notes", {}),
        )
        errors = sub.validation_errors()
        if errors:
            return refused(errors)
        filename = f"ESEF_{(sub.entity_name or 'entity').replace(' ', '_')}_{sub.period_end.year}.xhtml"
        return produced([text_file(filename, mvp.esef_engine.build_ixbrl_document(sub))])
    if regime == "saq":  # views/saq_generation.py, lines 38-55
        sub = mvp.saq_engine.SaqSubmission(
            entity_name=draft.get("entity_name", ""), uci_type=draft.get("uci_type", "UCITS"),
            financial_year_end=draft["financial_year_end"],
            dirigeant_reviewed=draft.get("dirigeant_reviewed", False),
            answers=draft.get("answers", {}), comments=draft.get("comments", {}),
        )
        errors = sub.validation_errors()
        if errors:
            return refused(errors)
        filename = f"SAQ_{(sub.entity_name or 'entity').replace(' ', '_')}_{sub.financial_year_end.year}.xlsx"
        return produced([workbook_file(filename, mvp.saq_engine.build_saq_summary_workbook(sub))])
    raise LookupError(regime)


# =============================================================================
# BCL — the view's own helpers (views/bcl_generation.py, bcl_ingestion.py)
# =============================================================================

def generate_bcl(mvp, report: str, draft: dict[str, Any]) -> dict[str, Any]:
    be, s220e, g = mvp.bcl_engine, mvp.bcl_s220_engine, mvp.bcl_generation
    d = to_dates(draft)
    if report == "s220":
        sub = g._s220_submission_from_draft(d)
        errors = mvp.errors_of(s220e.validation_issues(sub))
        if errors:
            return refused(issue_list(errors))
        xml, filename = s220e.build_s220_xml(sub), sub.filename()
    elif report == "s44":
        header = g._header_from_draft(d, be.S44_SPEC)
        rows = d.get("marketing_countries", [])
        errors = mvp.errors_of(be.validate_s44(rows, header))
        if errors:
            return refused(issue_list(errors))
        xml, filename = be.build_s44_xml(header, rows), be.s44_filename(header)
    elif report == "tptobs":
        header = g._header_from_draft(d, be.TPTOBS_SPEC)
        securities = [dict(s) for s in d.get("securities", []) if str(s.get("line_item") or "").strip()]
        assets = mvp.bcl_ingestion._tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_ASSETS)
        liabilities = mvp.bcl_ingestion._tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_LIABILITIES)
        errors = mvp.errors_of(be.validate_tptobs(assets, liabilities, securities, header))
        if errors:
            return refused(issue_list(errors))
        xml, filename = be.build_tptobs_xml(header, assets, liabilities, securities), be.tptobs_filename(header)
    else:
        header = g._header_from_draft(d, be.LEDGER_SPECS[report])
        assets, liabilities = d.get("assets", []), d.get("liabilities", [])
        errors = mvp.errors_of(be.validate_ledger(assets, liabilities, report, header))
        if errors:
            return refused(issue_list(errors))
        xml, filename = be.build_ledger_xml(report, header, assets, liabilities), be.ledger_filename(report, header)
    schema_valid = mvp.bcl_xsd.validate(xml, report).valid
    return produced([text_file(filename, xml, schema_valid=schema_valid)])


# =============================================================================
# AIFMD — views/aifmd_generation.py::_generate
# =============================================================================

def generate_aifmd(mvp, draft: dict[str, Any]) -> dict[str, Any]:
    ae = mvp.aifmd_engine
    d = to_dates(draft)
    sub = ae.submission_from_dicts(d["aifm_info"], d["aif_info"], d["period_start"], d["period_end"])
    errors = mvp.errors_of(sub.validation_issues())
    if errors:
        return refused(issue_list(errors))
    files = []
    for key, build_xml, build_filename in (("datman", ae.build_datman_xml, ae.build_datman_filename),
                                           ("dataif", ae.build_dataif_xml, ae.build_dataif_filename)):
        xml = build_xml(sub)
        files.append(text_file(build_filename(sub), xml, schema_valid=mvp.aifmd_xsd.validate(xml, key).valid))
    return produced(files)


# =============================================================================
# PRIIPs — views/kid_generation.py (the fund comes from the registry, as JSON)
# =============================================================================

def generate_priips(mvp, fund: dict[str, Any]) -> dict[str, Any]:
    t = mvp.templates
    calc = mvp.priips_engine.run_full_calculation(fund, t.load_rts_parameters())
    kid = mvp.kid_generator.build_kid(fund, calc, t.load_kid_template(), t.load_app_settings())
    return {"generated": True, "errors": [], "files": [],
            "data": normalize.data(case_catalogue.jsonable(
                {"sri": calc.sri, "costs": calc.costs, "scenarios": calc.scenarios, "kid": kid}))}


# =============================================================================
# FATCA / CRS — views/fatca_generation.py
# =============================================================================

def generate_fatca(mvp, content: bytes, parameters: dict[str, Any], preparer: str) -> dict[str, Any]:
    fp = mvp.fatca_pipeline
    _sheets, template_tabs = fp.load_workbook_tabs(content)
    xml, filename, errors = fp.generate_xml(template_tabs, parameters, fp.load_preparers()[preparer])
    if not xml:
        return refused(errors)
    return produced([text_file(filename, xml)])


# =============================================================================

def expected(mvp, case: dict[str, Any]) -> dict[str, Any]:
    kind = case["kind"]
    if kind == "filing_draft":
        return generate_filing(mvp, case["regime"], to_dates(case["draft"]))
    if kind == "filing_workbook":
        draft = ingest(mvp, case["regime"], (case_catalogue.INPUTS / case["input"]).read_bytes())
        return generate_filing(mvp, case["regime"], draft)
    if kind == "bcl":
        return generate_bcl(mvp, case["report"], case["draft"])
    if kind == "aifmd":
        return generate_aifmd(mvp, case["draft"])
    if kind == "priips":
        return generate_priips(mvp, case["fund"])
    if kind == "fatca":
        return generate_fatca(mvp, (case_catalogue.INPUTS / case["input"]).read_bytes(),
                              case["parameters"], case["preparer"])
    raise LookupError(kind)


def _mvp_revision(root: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(argv[1]).resolve()
    mvp = load_streamlit_mvp(root)
    case_catalogue.REFERENCE.mkdir(exist_ok=True)
    manifest = {"streamlit_mvp": root.name, "streamlit_mvp_revision": _mvp_revision(root),
                "built_on": date.today().isoformat(), "cases": []}
    for case in case_catalogue.all_cases():
        result = expected(mvp, case)
        path = case_catalogue.REFERENCE / f"{case['id']}.json"
        path.write_text(json.dumps(case_catalogue.jsonable(result), indent=1, ensure_ascii=False, sort_keys=True)
                        + "\n", encoding="utf-8", newline="\n")
        manifest["cases"].append(case["id"])
        print(f"  {'generated' if result['generated'] else 'refused  '}  {case['id']}")
    (case_catalogue.REFERENCE / "_manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
