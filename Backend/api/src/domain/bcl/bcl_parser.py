"""Reading a BCL filing back into the form that produced it.

Each generator turns a captured form into XML; this turns the XML back into
that same form, so a filing produced last quarter can be re-opened, corrected
and filed again instead of being re-keyed.

The mappings below are the inverse of the generators', element for element,
and they are verified the only way that means anything: parse the
regulator's own example, generate from what came out, and compare the result
with the file we started from (see tests/test_bcl_parser.py).

Values come back as strings because that is what a form holds — the same
shape the capture screens already work with, so nothing downstream has to
know whether a draft was typed or imported.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

# The six reports, by root element and namespace.
ROOTS = {
    ("S13", "http://www.bcl.lu/2008/S1.3"): "s13",
    ("S213", "http://www.bcl.lu/2008/S2.13"): "s213",
    ("S16", "http://www.bcl.lu/2008/S1.6"): "s16",
    ("S220", "http://www.bcl.lu/2025/S2.20"): "s220",
    ("S44", "http://www.bcl.lu/2024/S4.4"): "s44",
    ("SBS", "http://www.bcl.lu/2007/SBS"): "tptobs",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(node: ET.Element | None, path: str) -> ET.Element | None:
    """Follows a slash-separated path of local names, ignoring namespaces —
    the documents declare one, and repeating it at every step would make
    these mappings unreadable."""
    if node is None:
        return None
    current: ET.Element | None = node
    for step in path.split("/"):
        if current is None:
            return None
        current = next((child for child in current if _local(child.tag) == step), None)
    return current


def _text(node: ET.Element | None, path: str) -> str:
    found = _find(node, path)
    return (found.text or "").strip() if found is not None else ""


def _each(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [child for child in node if _local(child.tag) == name]


def detect(root: ET.Element) -> str | None:
    qualified = root.tag
    namespace = qualified[1:].split("}")[0] if qualified.startswith("{") else ""
    return ROOTS.get((_local(qualified), namespace))


# =============================================================================
# The header, shared by every report but S 2.20
# =============================================================================

def _header(root: ET.Element) -> dict[str, str]:
    header = _find(root, "header")
    return {
        "end_month_date": _text(header, "endMonthDate"),
        "closing_date": _text(header, "closingDate"),
        "reporter_type": _text(header, "reporterID/type"),
        "reporter_code": _text(header, "reporterID/code"),
        "declarant_type": _text(header, "declarantID/type"),
        "declarant_code": _text(header, "declarantID/code"),
        "reporting_currency": _text(header, "reportingCurrency"),
    }


# =============================================================================
# S 1.3 / S 2.13 / S 1.6 — amounts against a chart of accounts
# =============================================================================

def _ledger_side(content: ET.Element | None, side: str) -> dict[str, list[dict[str, str]]]:
    """One row per reportedLine, grouped by item.

    An item broken down over several countries appears several times in the
    document, and the capture screen holds exactly that: a list of rows per
    item. So the grouping is the natural shape, not a convenience.
    """
    rows: dict[str, list[dict[str, str]]] = {}
    for line in _each(_find(content, side), "reportedLine"):
        item = _text(line, "id/item")
        if not item:
            continue
        rows.setdefault(item, []).append({
            "country": _text(line, "id/country"),
            "currency": _text(line, "id/currency"),
            "sector": _text(line, "id/sector"),
            "maturity": _text(line, "id/initialMaturity"),
            "amount": _text(line, "reportedAmount"),
        })
    return rows


def _parse_ledger(root: ET.Element, report_key: str) -> dict[str, Any]:
    content = _find(root, "content")
    return {
        "report_key": report_key,
        "header": _header(root),
        "assets": _ledger_side(content, "assets"),
        "liabilities": _ledger_side(content, "liabilities"),
    }


# =============================================================================
# S 4.4 — where the units are marketed
# =============================================================================

def _parse_s44(root: ET.Element) -> dict[str, Any]:
    marketing = _find(root, "content/MarketingCountry")
    return {
        "report_key": "s44",
        "s44": {
            "header": _header(root),
            "marketing_countries": [
                {"country": _text(line, "id/country"), "amount": _text(line, "reportedAmount")}
                for line in _each(marketing, "reportedLine")
            ],
        },
    }


# =============================================================================
# TPTOBS Layout 3 — security by security
# =============================================================================

#: Which branch a security sits in, and what that branch carries. A security
#: with an ISIN sits under <ISIN>, one without under <other>; the instrument
#: kind then decides between <debt>, <equity> and <typeOfShare>.
_DEBT_SUPPLEMENTS = {
    "date_of_issue": "issueDate",
    "date_of_final_maturity": "finalMaturityDate",
    "pool_factor": "poolFactor",
    "coupon_type": "couponType",
    "coupon_frequency": "couponFrequency",
    "last_coupon_payment_date": "couponLastPaymentDate",
    "coupon_rate": "couponRate",
}

_SHARE_SUPPLEMENTS = {
    "cssf_class_code": "cssfCode",
    "issue_currency": "issueCurrency",
    "distributed_amount": "distributedAmount",
    "split_date": "splitDate",
    "split_ratio": "splitRatio",
}


def _parse_security(line_item: str, branch: str, security: ET.Element) -> dict[str, str]:
    code_type = _text(security, "securityID/codeType")
    code = _text(security, "securityID/code")

    row: dict[str, str] = {
        "line_item": line_item,
        "code_type": code_type,
        "isin": code if branch == "ISIN" else "",
        "other_code": code if branch == "other" else "",
        "security_name": _text(security, "securityID/name"),
        "security_currency": _text(security, "securityID/currency"),
        "issuer_country": _text(security, "issuerID/country"),
        "issuer_sector": _text(security, "issuerID/sector"),
        "issuer_lei": _text(security, "issuerID/lei"),
        "issuer_nationalid_type": _text(security, "issuerID/nationalID/type"),
        "issuer_nationalid_code": _text(security, "issuerID/nationalID/code"),
        "hold_security_type": _text(security, "holdSecurityType"),
        "reported_amount": _text(security, "reportedAmount"),
        "quotation_type": "", "nominal_amount": "", "nominal_currency": "",
        "number_of_units": "", "esa2010_type": "",
        **{key: "" for key in _DEBT_SUPPLEMENTS},
        **{key: "" for key in _SHARE_SUPPLEMENTS},
    }

    debt = _find(security, "debt")
    equity = _find(security, "equity")
    share = _find(security, "typeOfShare")

    if debt is not None:
        row["quotation_type"] = "percent"
        row["nominal_amount"] = _text(debt, "percentageQuoted/nominalAmount")
        row["nominal_currency"] = _text(debt, "percentageQuoted/nominalCurrency")
        row["esa2010_type"] = _text(debt, "supplements/securityType")
        for key, tag in _DEBT_SUPPLEMENTS.items():
            row[key] = _text(debt, f"supplements/{tag}")
    elif equity is not None:
        row["quotation_type"] = "currency"
        row["number_of_units"] = _text(equity, "currencyQuoted/numberOfUnits")
        row["esa2010_type"] = _text(equity, "supplements/securityType")
    elif share is not None:
        row["quotation_type"] = "currency"
        row["number_of_units"] = _text(share, "currencyQuoted/numberOfUnits")
        row["esa2010_type"] = _text(share, "supplements/securityType")
        for key, tag in _SHARE_SUPPLEMENTS.items():
            row[key] = _text(share, f"supplements/{tag}")

    return row


def _parse_tptobs(root: ET.Element) -> dict[str, Any]:
    body = _find(root, "OBS")
    securities: list[dict[str, str]] = []
    for side in ("assets", "liabilities"):
        for line in _each(_find(body, side), "reportedLine"):
            item = _text(line, "id/item")
            for branch in ("ISIN", "other"):
                for holder in _each(line, branch):
                    for security in _each(holder, "security"):
                        securities.append(_parse_security(item, branch, security))
    # The line totals are derived from the securities at generation, so they
    # are deliberately not read back: doing so would let an imported total
    # disagree with the securities under it.
    return {"report_key": "tptobs",
            "tptobs": {"header": _header(root), "securities": securities}}


# =============================================================================
# S 2.20 — the fund, its share classes, its income and expenses
# =============================================================================

_S220_SCALARS = {
    "reference_month": "GeneralInformation/ReferenceMonth",
    "reporting_status": "GeneralInformation/ReportingStatus",
    "sender_cssf_code": "GeneralInformation/SenderCssfCode",
    "sender_type": "GeneralInformation/TypeOfTheSender",
    "sender_code": "GeneralInformation/CodeOfTheSender",
    "uci_cssf_code": "UCIGeneralInformation/UCISignaBasic/UCICssfCode",
    "declarant_type": "UCIGeneralInformation/UCISignaBasic/TypeOfTheDeclarant",
    "declarant_code": "UCIGeneralInformation/UCISignaBasic/CodeOfTheDeclarant",
    "uci_name": "UCIGeneralInformation/UCISignaBasic/UCIName",
    "uci_base_currency": "UCIGeneralInformation/UCISignaBasic/UCIBaseCurrency",
    "uci_lei": "UCIGeneralInformation/UCISignaBasic/LEI",
    "valuation_date": "UCIGeneralInformation/UCISignaDate/ValuationDate",
    "launch_date": "UCIGeneralInformation/UCISignaDate/LaunchDate",
    "closing_date": "UCIGeneralInformation/UCISignaDate/ClosingDate",
    "reason_for_closing": "UCIGeneralInformation/UCISignaDate/ReasonForClosing",
    "nav_freq": "UCIGeneralInformation/UCISignaDate/NavInformation/NavFreq",
    "nav_redemption_freq": "UCIGeneralInformation/UCISignaDate/NavInformation/NavRedemptionFreq",
    "open_closed_end": "UCIGeneralInformation/UCISignaDate/NavInformation/OpenClosedEnd",
    "nav_preceding_ref_month": "UCIFinancialInformation/NAVPrecedingRefMonth",
    "nav_ref_month": "UCIFinancialInformation/NAVRefMonth",
    "units_issued": "UCIFinancialInformation/TotUnitsOrSharesIssued",
    "units_redeemed": "UCIFinancialInformation/TotUnitsOrSharesRedeemed",
    "total_distributions": "UCIFinancialInformation/TotalDistributions",
}

_S220_INCOME = {
    "dividends_on_shares": "DividendsOnShares/DividendsOnShares",
    "dividends_on_shares_lu": "DividendsOnShares/DivShOfWhichFromLu",
    "dividends_on_uci_units": "DividendsOnUCI_Units_Shares/DividendsOnUCI_Units_Shares",
    "dividends_on_uci_units_lu": "DividendsOnUCI_Units_Shares/DivUCIOfWhichFromLu",
    "interest_bonds": "Interest/Interest_bonds_debt_securities",
    "interest_bonds_lu": "Interest/DivIntBondsOfWhichFromLu",
    "interest_loans_banks": "InterestLoansBanksBearingAccounts",
    "bank_interest": "BankInterest/BankInterest",
    "bank_interest_lu": "BankInterest/BankIntOfWhichFromLu",
    "other_interest": "OtherInterest/OtherInterest",
    "other_interest_lu": "OtherInterest/OtherIntOfWhichFromLu",
    "other_income": "OtherIncome",
    "rental_income": "OtherIncomeDetails/RentalIncome",
    "commission_income": "OtherIncomeDetails/CommissionIncome",
    "other_income_other": "OtherIncomeDetails/OtherOfWhichFromOtherIncome",
    "charges": "Charges",
    "advisory_management_fees": "ChargesDetails/AdvisoryManagementFees",
    "depositary_bank_fees": "ChargesDetails/DepositaryBankFees",
    "administration_fees": "ChargesDetails/AdministrationFees",
    "audit_inspection_fees": "ChargesDetails/AuditInspectionFees",
    "distribution_fees": "ChargesDetails/DistributionFees",
    "other_administrative_expenses": "ChargesDetails/OtherAdministrativeExpenses",
    "subscription_tax": "ChargesDetails/SubscriptionTax",
    "other_taxes": "ChargesDetails/OtherTaxes",
    "performance_fees": "PerformanceFees",
    "other_expenses": "OtherExpenses",
    "interest_paid": "OtherExpensesDetails/InterestPaid",
    "personnel_expenses": "OtherExpensesDetails/PersonnelExpenses",
    "rental_expenses": "OtherExpensesDetails/RentalExpenses",
    "amortisation": "OtherExpensesDetails/Amortisation",
    "other_expenses_other": "OtherExpensesDetails/OtherOfWhichFromOtherExpenses",
    "net_realised": "NetRealised",
    "net_unrealised": "NetUnrealised",
}

_S220_CLASS_GENERAL = {
    "name": "Unit_ShareClass_Name",
    "base_currency": "BaseCurrency",
    "isin": "ISINCode",
    "launch_date": "LaunchDate",
    "closing_date": "ClosingDate",
    "reason_for_closing": "ReasonForClosing",
    "spec_instr_fx": "Unit_ShareClass_SpecInstr_FX",
    "spec_instr_interest_rate": "Unit_ShareClass_SpecInstr_InterestRate",
    "spec_instr_other": "Unit_ShareClass_SpecInstr_Other",
    "investor_base": "InvestorBase",
}

_S220_CLASS_FINANCIAL = {
    "units_outstanding": "NumberUnitOrShareOutstanding",
    "nav_per_unit_fund_currency": "NetAssetValueInSubFundCurrency",
    "nav_per_unit_shareclass_currency": "NetAssetValueInShareClassCurrency",
    "net_return": "NetReturn",
    "units_issued": "UnitOrSharesIssued",
    "units_redeemed": "UnitOrSharesRedeemed",
    "distributions": "Distributions",
    "distributions_per_unit_fund_currency": "AmountDistributionsInUCICurrency",
    "distributions_per_unit_shareclass_currency": "AmountDistributionsInShareClassCurrency",
    "income_fund_currency": "IncomeInFundCurrency",
    "expenses_fund_currency": "ExpensesInFundCurrency",
}

#: The form holds a flag as "true"/"false"; the document writes 0 or 1.
_FLAGS = ("spec_instr_fx", "spec_instr_interest_rate", "spec_instr_other")


def _parse_s220(root: ET.Element) -> dict[str, Any]:
    scalars = {key: _text(root, path) for key, path in _S220_SCALARS.items()}

    income = _find(root, "UCI_Inv_Income_and_Expenses")
    scalars.update({key: _text(income, path) for key, path in _S220_INCOME.items()})
    scalars["uci_comment"] = _text(root, "UCIGeneralInformation/UCISignaBasic/Comment")

    contacts = _find(root, "GeneralInformation/SenderInformations")
    employees = [
        {"name": _text(contact, "NameOfEmployee"),
         "phone": _text(contact, "PhoneNumber"),
         "email": _text(contact, "EmailAdress")}
        for contact in _each(contacts, "SenderInformation")
    ]

    classes = []
    for entry in _each(_find(root, "Unit_Share_Informations"), "Unit_Share_Information"):
        general = _find(entry, "UnitShareClassGeneralInformation")
        financial = _find(entry, "UnitShareClassFinancialInformation")
        row = {"cssf_code": _text(entry, "CssfCode")}
        row.update({key: _text(general, tag) for key, tag in _S220_CLASS_GENERAL.items()})
        row.update({key: _text(financial, tag) for key, tag in _S220_CLASS_FINANCIAL.items()})
        for flag in _FLAGS:
            row[flag] = "true" if row[flag] in ("1", "true", "True") else "false"
        classes.append(row)

    return {"report_key": "s220",
            "s220": {"scalars": scalars, "sender_employees": employees,
                     "share_classes": classes}}


# =============================================================================

_PARSERS = {
    "s13": lambda root: _parse_ledger(root, "s13"),
    "s213": lambda root: _parse_ledger(root, "s213"),
    "s16": lambda root: _parse_ledger(root, "s16"),
    "s44": _parse_s44,
    "tptobs": _parse_tptobs,
    "s220": _parse_s220,
}


def parse(content: bytes | str) -> tuple[str | None, dict[str, Any] | None]:
    """The report a document is, and the form that would produce it.

    Returns ``(None, None)`` when the document is not one of the six: an
    unreadable or foreign file is the caller's to report, not this layer's.
    """
    try:
        root = ET.fromstring(content if isinstance(content, bytes) else content.encode())
    except ET.ParseError:
        return None, None

    report_key = detect(root)
    if report_key is None:
        return None, None
    return report_key, _PARSERS[report_key](root)
