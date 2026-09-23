"""The non-regression cases: one business input, two tools, one expected output.

Each case is plain data — no import of either code base — so the Streamlit
oracle (oracle.py) and the API tests (test_non_regression.py) are fed exactly
the same thing. Dates are ISO strings here, as JSON carries them; the oracle
turns them back into ``date`` objects, which is what the Streamlit widgets
held.

Every name, code and amount is invented.

Kinds:
    filing_draft     U 1.1 / O 4.1 / ESEF / SAQ, from a captured draft
    filing_workbook  the same regimes, from a filled-in template (inputs/)
    bcl              one of the six BCL reports
    aifmd            the DATMAN and DATAIF files
    priips           the RTS calculation and the assembled KID of one fund
    fatca            an AEOI return, from a filled-in data report workbook
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "inputs"
REFERENCE = HERE / "reference"


def jsonable(value: Any) -> Any:
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


# =============================================================================
# U 1.1 / O 4.1 / ESEF / SAQ — from a draft
# =============================================================================

_SHARE_CLASS = {
    "cssf_code": "S00000101", "name": "A EUR Acc", "currency": "EUR", "isin": "LU0000000101",
    "launch_date": "2019-03-01", "closing_date": None, "closing_reason": None,
    "spec_fx": False, "spec_ir": False, "spec_other": False, "investor_base": 1,
    "units_outstanding": 800000.0, "nav_per_unit_uci_ccy": 100.25, "nav_per_unit_class_ccy": 100.25,
    "net_return_pct": 0.85, "units_issued": 15000.0, "units_redeemed": 9000.0, "distributions": 0.0,
    "distrib_per_unit_uci_ccy": 0.0, "distrib_per_unit_class_ccy": 0.0,
    "income_uci_ccy": 180000.0, "expenses_uci_ccy": 70000.0,
}

URR_FINAL = {
    "reference_month": "2025-11-01", "reporting_status": "final report",
    "sender_cssf_code": "B00000999", "employee_name": "Claire Martin", "employee_phone": "+352 000 000",
    "sender_email": "claire.martin@example.lu", "uci_cssf_code": "O00001234",
    "uci_name": "Demo Balanced Fund", "uci_currency": "EUR", "lei": "5493000DEMO0000000X1",
    "valuation_date": "2025-11-28", "nav_frequency": 1, "launch_date": "2019-03-01",
    "closing_date": None, "closing_reason": None, "redemption_frequency": 1, "open_closed_end": 1,
    "nav_preceding_month": 120000000.0, "nav_this_month": 121500000.0, "proceeds_issued": 2000000.0,
    "payments_redeemed": 1200000.0, "total_distributions": 0.0,
    "share_classes": [
        _SHARE_CLASS,
        {**_SHARE_CLASS, "cssf_code": "S00000102", "name": "I USD Hedged", "currency": "USD",
         "isin": "LU0000000102", "launch_date": "2021-06-15", "spec_fx": True, "investor_base": 2,
         "units_outstanding": 400000.0, "nav_per_unit_uci_ccy": 103.0, "nav_per_unit_class_ccy": 111.4,
         "net_return_pct": 1.1, "units_issued": 5000.0, "units_redeemed": 3000.0,
         "income_uci_ccy": 50000.0, "expenses_uci_ccy": 25000.0},
    ],
    "income": {"dividends_shares": 150000.0, "dividends_shares_lu": 20000.0, "interest_bonds": 80000.0,
               "charges": 95000.0, "advisory_mgmt_fees": 70000.0, "net_realised": 300000.0},
}

URR_NULL = {key: URR_FINAL[key] for key in (
    "reference_month", "sender_cssf_code", "employee_name", "employee_phone", "sender_email",
    "uci_cssf_code", "uci_name", "uci_currency", "lei", "valuation_date", "launch_date")}
URR_NULL["reporting_status"] = "null report"

URR_REFUSED = {**URR_FINAL, "sender_cssf_code": "", "lei": "TOO-SHORT",
               "share_classes": [{**_SHARE_CLASS, "isin": "12345"}]}

O41_REFUSED = {
    "uci_name": "Demo Umbrella SICAV", "subfund_name": "Demo Equity", "uci_id": "O00001234",
    "subfund_id": "00000001", "year_end": "2025-12-31", "currency": "EUR",
    "employee_name": "Claire Martin", "employee_phone": "+352 000 000",
    # 1000 is not the sum of its components, and the marketing split is 90 %.
    "values": {"1000": 1000.0, "1100": 400.0, "1200": 100.0},
    "marketing_countries": [{"country_iso": "LU", "pct": 90}],
}

ESEF_DRAFT = {
    "entity_name": "Demo Fund S.A.", "lei": "5493000DEMO0000000X1", "currency": "EUR",
    "period_start": "2025-01-01", "period_end": "2025-12-31",
    "facts": {"cash": 2500000.0, "investments": 118000000.0, "total_assets": 120500000.0,
              "total_equity": 120500000.0, "revenue": 3200000.0, "profit_loss": 2100000.0},
    "notes": {"general_information": "A fictitious investment company used for testing."},
}
ESEF_REFUSED = {**ESEF_DRAFT, "lei": "SHORT", "period_end": "2024-12-31", "facts": {}}

SAQ_DRAFT = {
    "entity_name": "Demo Fund S.A.", "uci_type": "SIF", "financial_year_end": "2025-12-31",
    "dirigeant_reviewed": True,
    "answers": {"formal_meetings": "Yes", "conflicts_of_interest": "No", "breach_policy": "N/A"},
    "comments": {"conflicts_of_interest": "Policy under review."},
}
SAQ_REFUSED = {**SAQ_DRAFT, "dirigeant_reviewed": False}


# =============================================================================
# BCL
# =============================================================================

BCL_HEADER = {
    "end_month_date": "2025-12-31", "closing_date": "2025-12-31",
    "reporter_type": "23", "reporter_code": "789",
    "declarant_type": "26", "declarant_code": "001220003", "reporting_currency": "EUR",
}


def _line(item: str, amount: float, **breakdown: str) -> dict[str, Any]:
    # Amounts are floats: the Streamlit data editors held float columns.
    return {"item": item, "country": breakdown.get("country", "XX"), "currency": breakdown.get("currency", "XXX"),
            "sector": breakdown.get("sector", "90000"), "maturity": breakdown.get("maturity", "I999-999"),
            "amount": float(amount)}


BCL_LEDGER = {
    "header": BCL_HEADER, "creation_date": "2026-01-05",
    "assets": [_line("1-003000", 1000), _line("1-000000", 1000)],
    "liabilities": [_line("2-004000", 1000), _line("2-000000", 1000)],
}
BCL_S16 = {"header": BCL_HEADER, "creation_date": "2026-01-05",
           "assets": [_line("1-007000", 30)], "liabilities": []}
BCL_UNBALANCED = {**BCL_LEDGER, "liabilities": [_line("2-004000", 1000), _line("2-000000", 5)]}
BCL_S44 = {"header": BCL_HEADER, "creation_date": "2026-01-05",
           "marketing_countries": [{"item": "2-004000", "country": "LU", "amount": 60},
                                   {"item": "2-004000", "country": "BE", "amount": 40}]}
BCL_TPTOBS = {"header": BCL_HEADER, "creation_date": "2026-01-05", "securities": [
    {"line_item": "1-003000", "code_type": "1", "isin": "USG9328DAH38", "hold_security_type": "01",
     "esa2010_type": "F.3", "quotation_type": "percent", "nominal_amount": 2000000,
     "nominal_currency": "USD", "reported_amount": 1840000},
]}
BCL_S220 = {
    "reference_month": "202512", "sender_type": "23", "sender_code": "341",
    "sender_employees": [{"name": "J Doe", "phone": "000", "email": "a@b.lu"}],
    "declarant_type": "42", "declarant_code": "66012345600001", "uci_name": "Fund - A",
    "valuation_date": "2025-12-31", "launch_date": "2021-01-04",
    "nav_freq": 13, "nav_redemption_freq": 4, "open_closed_end": 1,
    "nav_preceding_ref_month": 99900, "nav_ref_month": 100000,
    "units_issued": 0, "units_redeemed": 0, "total_distributions": 0,
    "share_classes": [{
        "cssf_code": "0001", "name": "CAP", "base_currency": "EUR", "launch_date": "2021-01-04",
        "investor_base": 3, "units_outstanding": 1000, "nav_per_unit_fund_currency": 100,
        "nav_per_unit_shareclass_currency": 100, "net_return": 1.5, "units_issued": 0,
        "units_redeemed": 0, "distributions": 0, "distributions_per_unit_fund_currency": 0,
        "distributions_per_unit_shareclass_currency": 0,
        "income_fund_currency": 600, "expenses_fund_currency": 500}],
    "dividends_on_shares": 600, "dividends_on_shares_lu": 100,
    "charges": 500, "advisory_management_fees": 500, "creation_date": "2025-07-01",
}


# =============================================================================
# AIFMD — the draft the capture form saves (tests/_aifmd_fixture.py)
# =============================================================================

def _aifmd_draft(**overrides: Any) -> dict[str, Any]:
    from _aifmd_fixture import draft

    d = jsonable(draft())
    for path, value in overrides.items():
        section, key = path.split(".")
        d[section][key] = value
    return d


# =============================================================================
# FATCA / CRS
# =============================================================================

_CRS_DATA = {"crs_fatca": "CRS", "report_type": "Data Report", "selection": "Initial",
             "version": "1", "filer_category": None}
_FATCA_ZERO = {"crs_fatca": "FATCA", "report_type": "Zero Report", "selection": "Initial", "version": "1",
               "filer_category": "FATCA601 - PFFI (excl. Model 2 & U.S. branch PFFI)"}
FATCA_PREPARER = "Christopher JACQUES"


# =============================================================================
# The catalogue
# =============================================================================

def _priips_funds() -> list[dict[str, Any]]:
    return json.loads((INPUTS / "priips_funds.json").read_text(encoding="utf-8"))


def all_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = [
        {"id": "urr_final_draft", "kind": "filing_draft", "regime": "urr", "draft": URR_FINAL},
        {"id": "urr_null_report_draft", "kind": "filing_draft", "regime": "urr", "draft": URR_NULL},
        {"id": "urr_refused_draft", "kind": "filing_draft", "regime": "urr", "draft": URR_REFUSED},
        {"id": "o41_refused_draft", "kind": "filing_draft", "regime": "o41", "draft": O41_REFUSED},
        {"id": "esef_draft", "kind": "filing_draft", "regime": "esef", "draft": ESEF_DRAFT},
        {"id": "esef_refused_draft", "kind": "filing_draft", "regime": "esef", "draft": ESEF_REFUSED},
        {"id": "saq_draft", "kind": "filing_draft", "regime": "saq", "draft": SAQ_DRAFT},
        {"id": "saq_refused_draft", "kind": "filing_draft", "regime": "saq", "draft": SAQ_REFUSED},

        {"id": "urr_workbook", "kind": "filing_workbook", "regime": "urr", "input": "urr_filled.xlsx"},
        {"id": "o41_workbook", "kind": "filing_workbook", "regime": "o41", "input": "o41_filled.xlsx"},
        {"id": "esef_workbook", "kind": "filing_workbook", "regime": "esef", "input": "esef_filled.xlsx"},
        {"id": "saq_workbook", "kind": "filing_workbook", "regime": "saq", "input": "saq_filled.xlsx"},

        {"id": "bcl_s13", "kind": "bcl", "report": "s13", "draft": BCL_LEDGER},
        {"id": "bcl_s213", "kind": "bcl", "report": "s213", "draft": BCL_LEDGER},
        {"id": "bcl_s16", "kind": "bcl", "report": "s16", "draft": BCL_S16},
        {"id": "bcl_s13_unbalanced", "kind": "bcl", "report": "s13", "draft": BCL_UNBALANCED},
        {"id": "bcl_s44", "kind": "bcl", "report": "s44", "draft": BCL_S44},
        {"id": "bcl_tptobs", "kind": "bcl", "report": "tptobs", "draft": BCL_TPTOBS},
        {"id": "bcl_s220", "kind": "bcl", "report": "s220", "draft": BCL_S220},

        {"id": "aifmd", "kind": "aifmd", "draft": _aifmd_draft()},
        {"id": "aifmd_refused", "kind": "aifmd", "draft": _aifmd_draft(**{"aif_info.nav_geo_focus": {"EEA": 90}})},

        {"id": "fatca_crs_data", "kind": "fatca", "input": "fatca_crs.xlsx",
         "parameters": _CRS_DATA, "preparer": FATCA_PREPARER},
        {"id": "fatca_crs_data_renamed_tabs", "kind": "fatca", "input": "fatca_crs_renamed_tabs.xlsx",
         "parameters": _CRS_DATA, "preparer": FATCA_PREPARER},
        {"id": "fatca_zero_report", "kind": "fatca", "input": "fatca_crs.xlsx",
         "parameters": _FATCA_ZERO, "preparer": FATCA_PREPARER},
    ]
    for fund in _priips_funds():
        cases.append({"id": f"priips_{fund['fund_id']}", "kind": "priips", "fund": fund})
    return cases
