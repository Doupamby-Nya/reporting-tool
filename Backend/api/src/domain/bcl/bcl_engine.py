"""BCL (Banque centrale du Luxembourg) statistical reporting engine.

Covers five of the six BCL reports this module files (the sixth, S 2.20, is
built by domain.bcl.bcl_s220_engine because its schema has a completely different
shape):

  key       report        root/namespace                      layout  file code
  s13       S 1.3 L4      S13  http://www.bcl.lu/2008/S1.3        4    S0103
  s213      S 2.13 L2     S213 http://www.bcl.lu/2008/S2.13       2    S0213
  s16       S 1.6 L2      S16  http://www.bcl.lu/2008/S1.6        2    S0106
  s44       S 4.4 L0      S44  http://www.bcl.lu/2024/S4.4        0    S0404
  tptobs    TPTOBS L3     SBS  http://www.bcl.lu/2007/SBS         3    TPTOBS

Every element name, code list, cardinality and datatype below is taken from
the real BCL XSD schemas, bundled unmodified at core/bcl_schemas/<key>/ (a
copy of BCL/<report>/*_Schema_XML_*/). Generated documents are validated
against those very schemas by domain.bcl.bcl_xsd, and against the business rules of
each report's own "Compendium of verification rules" (VER) PDF by the
validate_* functions here.

Ground truth for the charts of accounts and their mandatory breakdowns is each
report's own official Excel file ("Report" sheet), bundled at
data/regulation/bcl/<report>/: a cell holding "(1)" means the amount must be
broken down over that dimension, any other value is the fixed code to report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from domain.bcl.bcl_codes import (
    BCL_MATURITY_CODES, BCL_SECTOR_CODES, BCL_SPECIAL_COUNTRY_CODES, COUPON_FREQUENCIES,
    COUPON_FREQUENCY_MAX_DAYS, COUPON_TYPES, DEBT_TYPE, DEFAULT_POOL_FACTOR, DEFAULT_SPLIT_DATE,
    DEFAULT_SPLIT_RATIO, ESA2010_SECURITY_TYPES, EQUITY_TYPES, FEDERAL_COUNTRIES, FUND_SECTORS,
    FUND_SHARE_TYPE, HOLD_SECURITY_TYPES, HOLD_TYPES_BY_ITEM, ISO_3166_ALPHA2, NO_BREAKDOWN,
    NO_BREAKDOWN_COUNTRY, NO_BREAKDOWN_CURRENCY, NO_BREAKDOWN_MATURITY, NO_BREAKDOWN_SECTOR,
    NO_LEI, NO_NATIONAL_ID_CODE, NO_NATIONAL_ID_TYPE, PERPETUAL_MATURITY_DATE, QUOTATION_TYPES,
    REAL_SECTOR_CODES, SECURITY_CODE_TYPES, SECURITY_TYPES_BY_ITEM, is_valid_country,
    is_valid_currency, is_valid_maturity, is_valid_sector, isin_checksum_ok, isin_prefix_ok,
    lei_format_ok,
)
from domain.bcl.bcl_common import (
    ERROR, WARNING, Issue, Node, as_date, blank, build_filename, creation_datetime, errors_of,
    filename_id_token, fmt_date, fmt_decimal, is_number, serialize, to_decimal, warnings_of,
)

from utils.paths import RESOURCES_DIR
BCL_DATA_DIR = RESOURCES_DIR / "regulation" / "bcl"

# Re-exported so views and other modules keep a single import site.
__all__ = [
    "BCL_MATURITY_CODES", "BCL_SECTOR_CODES", "BCL_SPECIAL_COUNTRY_CODES", "COUPON_FREQUENCIES",
    "COUPON_TYPES", "ESA2010_SECURITY_TYPES", "HOLD_SECURITY_TYPES", "QUOTATION_TYPES",
    "SECURITY_CODE_TYPES", "NO_BREAKDOWN", "BclHeader", "LEDGER_SPECS", "REPORT_LABELS",
    "S13_ASSETS", "S13_LIABILITIES", "S16_ASSETS", "S16_LIABILITIES", "S44_ITEMS",
    "TPTOBS_ASSETS", "TPTOBS_LIABILITIES", "S13_BREAKDOWN_SPECS_ASSETS",
    "S13_BREAKDOWN_SPECS_LIABILITIES", "S16_BREAKDOWN_SPECS_ASSETS", "S16_BREAKDOWN_SPECS_LIABILITIES",
    "TPTOBS_BREAKDOWN_SPECS_ASSETS", "TPTOBS_BREAKDOWN_SPECS_LIABILITIES",
    "build_ledger_xml", "build_s44_xml", "build_tptobs_xml",
    "validate_ledger", "validate_s44", "validate_tptobs", "ledger_filename", "s44_filename",
    "tptobs_filename", "load_report_bytes", "reference_file", "Issue", "ERROR", "WARNING",
    "errors_of", "warnings_of", "cross_check_ledger_vs_tptobs", "cross_check_ledger_vs_s220",
]

BREAK = "(1)"  # "must be broken down over this dimension" marker of the official Excel


# =============================================================================
# Charts of accounts — one row per line of each report's official Excel
# "Report" sheet: (item, label, country, currency, sector, maturity).
# =============================================================================

def _spec(item: str, label: str, country: str, currency: str, sector: str, maturity: str) -> dict[str, str]:
    return {"item": item, "label": label, "country": country, "currency": currency,
            "sector": sector, "maturity": maturity}


# --- S 1.3 / S 2.13 (same chart of accounts, different layout & frequency) ---
S13_BREAKDOWN_SPECS_ASSETS: list[dict[str, str]] = [
    _spec("1-S02010", "Deposits and loan claims - Leveraged loan claims", BREAK, BREAK, BREAK, BREAK),
    _spec("1-002999", "Deposits and loan claims - Deposits and other loan claims", BREAK, BREAK, BREAK, BREAK),
    _spec("1-003000", "Debt securities held", "XX", "XXX", "90000", "I999-999"),
    _spec("1-005000", "Equity and investment fund shares/units held", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006011", "Non-financial assets - Real estate - Residential", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-006012", "Non-financial assets - Real estate - Commercial", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-006013", "Non-financial assets - Real estate - Industrial", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-006014", "Non-financial assets - Real estate - Offices", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-006015", "Non-financial assets - Real estate - Others", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-006999", "Non-financial assets - Other non-financial assets", BREAK, "XXX", "90000", "I999-999"),
    _spec("1-007000", "Financial derivatives", BREAK, "XXX", BREAK, "I999-999"),
    _spec("1-090010", "Remaining assets - Accrued interest", "XX", BREAK, "90000", BREAK),
    _spec("1-099999", "Remaining assets - Other", BREAK, BREAK, "90000", BREAK),
    _spec("1-000000", "Total", "XX", "XXX", "90000", "I999-999"),
]

S13_BREAKDOWN_SPECS_LIABILITIES: list[dict[str, str]] = [
    _spec("2-002010", "Borrowings - Overnight borrowings", BREAK, BREAK, BREAK, "I999-999"),
    _spec("2-002020", "Borrowings - Borrowings with agreed maturity", BREAK, BREAK, BREAK, BREAK),
    _spec("2-002030", "Borrowings - Borrowings redeemable at notice", BREAK, BREAK, BREAK, BREAK),
    _spec("2-002040", "Borrowings - Repurchase agreements", BREAK, BREAK, BREAK, BREAK),
    _spec("2-002050", "Borrowings - Short sales of securities", "XX", "XXX", "90000", "I999-999"),
    _spec("2-RD2000", "Borrowings - Revolving loans and overdrafts", BREAK, BREAK, BREAK, BREAK),
    _spec("2-003000", "Debt securities issued", "XX", "XXX", "90000", "I999-999"),
    _spec("2-004000", "Shares/units issued", "XX", "XXX", "90000", "I999-999"),
    _spec("2-011000", "Financial derivatives", BREAK, "XXX", BREAK, "I999-999"),
    _spec("2-090010", "Remaining liabilities - Accrued interest", "XX", BREAK, "90000", BREAK),
    _spec("2-099999", "Remaining liabilities - Other", BREAK, BREAK, "90000", BREAK),
    _spec("2-000000", "Total", "XX", "XXX", "90000", "I999-999"),
]

# --- S 1.6: valuation effects, no breakdown at all (instructions §3) ---------
S16_BREAKDOWN_SPECS_ASSETS: list[dict[str, str]] = [
    _spec("1-006011", "Non-financial assets - Real estate - Residential", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006012", "Non-financial assets - Real estate - Commercial", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006013", "Non-financial assets - Real estate - Industrial", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006014", "Non-financial assets - Real estate - Offices", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006015", "Non-financial assets - Real estate - Others", "XX", "XXX", "90000", "I999-999"),
    _spec("1-006999", "Non-financial assets - Other non-financial assets", "XX", "XXX", "90000", "I999-999"),
    _spec("1-007000", "Financial derivatives", "XX", "XXX", "90000", "I999-999"),
]

S16_BREAKDOWN_SPECS_LIABILITIES: list[dict[str, str]] = [
    _spec("2-011000", "Financial derivatives", "XX", "XXX", "90000", "I999-999"),
]

# --- TPTOBS: the five security-by-security lines, always XX/XXX/90000 -------
TPTOBS_BREAKDOWN_SPECS_ASSETS: list[dict[str, str]] = [
    _spec("1-003000", "Debt securities held", "XX", "XXX", "90000", "I999-999"),
    _spec("1-005000", "Equity and investment fund shares/units held", "XX", "XXX", "90000", "I999-999"),
]

TPTOBS_BREAKDOWN_SPECS_LIABILITIES: list[dict[str, str]] = [
    _spec("2-002050", "Borrowings - Short sales of securities", "XX", "XXX", "90000", "I999-999"),
    _spec("2-003000", "Debt securities issued", "XX", "XXX", "90000", "I999-999"),
    _spec("2-004000", "Shares/units issued", "XX", "XXX", "90000", "I999-999"),
]

S44_ITEM = "2-004000"
S44_DATA_TYPE = "PCT"
S44_ITEMS: list[tuple[str, str]] = [(S44_ITEM, "Units/shares issued by marketing country")]


def _chart(specs: Iterable[dict[str, str]]) -> list[tuple[str, str]]:
    return [(s["item"], s["label"]) for s in specs]


S13_ASSETS = _chart(S13_BREAKDOWN_SPECS_ASSETS)
S13_LIABILITIES = _chart(S13_BREAKDOWN_SPECS_LIABILITIES)
S16_ASSETS = _chart(S16_BREAKDOWN_SPECS_ASSETS)
S16_LIABILITIES = _chart(S16_BREAKDOWN_SPECS_LIABILITIES)
TPTOBS_ASSETS = _chart(TPTOBS_BREAKDOWN_SPECS_ASSETS)
TPTOBS_LIABILITIES = _chart(TPTOBS_BREAKDOWN_SPECS_LIABILITIES)

TOTAL_ASSETS_ITEM = "1-000000"
TOTAL_LIABILITIES_ITEM = "2-000000"

# Lines that may legitimately carry a negative (debit) amount —
# S 1.3 / S 2.13 compendium of verification rules §2.1.1.
DEBIT_ALLOWED_ITEMS = frozenset({"1-090010", "2-090010", "2-004000"})

# Balance-sheet lines whose total must match the TPTOBS security-by-security
# report — S 1.3 / S 2.13 VER §2.1.2.
SBS_CROSS_CHECK_ITEMS = ("1-003000", "1-005000", "2-002050", "2-003000", "2-004000")


# =============================================================================
# Report specifications
# =============================================================================

@dataclass(frozen=True)
class LedgerSpec:
    key: str
    label: str
    root: str
    namespace: str
    version: str
    layout: int
    file_code: str
    assets: list[dict[str, str]]
    liabilities: list[dict[str, str]]
    has_maturity: bool = True
    sections_optional: bool = False  # S 1.6 allows an empty assets or liabilities section
    description: str = ""


LEDGER_SPECS: dict[str, LedgerSpec] = {
    "s13": LedgerSpec(
        "s13", "S 1.3 L4", "S13", "http://www.bcl.lu/2008/S1.3", "1.2", 4, "S0103",
        S13_BREAKDOWN_SPECS_ASSETS, S13_BREAKDOWN_SPECS_LIABILITIES,
        description="Monthly statistical balance sheet of money market funds and non-MMF investment funds.",
    ),
    "s213": LedgerSpec(
        "s213", "S 2.13 L2", "S213", "http://www.bcl.lu/2008/S2.13", "1.2", 2, "S0213",
        S13_BREAKDOWN_SPECS_ASSETS, S13_BREAKDOWN_SPECS_LIABILITIES,
        description="Quarterly statistical balance sheet of non-UCITS investment funds valued less frequently than monthly.",
    ),
    "s16": LedgerSpec(
        "s16", "S 1.6 L2", "S16", "http://www.bcl.lu/2008/S1.6", "1.2", 2, "S0106",
        S16_BREAKDOWN_SPECS_ASSETS, S16_BREAKDOWN_SPECS_LIABILITIES, sections_optional=True,
        description="Information on valuation effects on the balance sheet of investment funds.",
    ),
}

S44_SPEC = LedgerSpec(
    "s44", "S 4.4 L0", "S44", "http://www.bcl.lu/2024/S4.4", "1.0", 0, "S0404", [], [],
    has_maturity=False, description="Country of marketing — units/shares issued broken down by marketing country.",
)

TPTOBS_SPEC = LedgerSpec(
    "tptobs", "TPTOBS L3", "SBS", "http://www.bcl.lu/2007/SBS", "1.5", 3, "TPTOBS",
    TPTOBS_BREAKDOWN_SPECS_ASSETS, TPTOBS_BREAKDOWN_SPECS_LIABILITIES, has_maturity=False,
    sections_optional=True, description="Security-by-security report of investment funds.",
)

ALL_SPECS: dict[str, LedgerSpec] = {**LEDGER_SPECS, "s44": S44_SPEC, "tptobs": TPTOBS_SPEC}
REPORT_LABELS: dict[str, str] = {k: s.label for k, s in ALL_SPECS.items()}

# Amounts: every BCL amount datatype allows at most 5 fraction digits.
AMOUNT_DIGITS = 5
PERCENTAGE_DIGITS = 9   # SBS percentage (coupon rate, pool factor)
S44_DIGITS = 5          # S44 percentage; instructions ask for 2 decimals, the XSD allows 5


# =============================================================================
# Header
# =============================================================================

@dataclass
class BclHeader:
    """The header shared by S 1.3 / S 2.13 / S 1.6 / S 4.4 / TPTOBS."""

    end_month_date: date | None = None
    closing_date: date | None = None
    reporter_type: str = ""
    reporter_code: str = ""
    declarant_type: str = ""
    declarant_code: str = ""
    reporting_currency: str = "EUR"
    layout: int = 0

    def period(self) -> str:
        d = as_date(self.end_month_date)
        return d.strftime("%Y%m") if d else ""


def _header_node(h: BclHeader) -> Node:
    node = Node("header")
    node.add("endMonthDate", fmt_date(h.end_month_date))
    node.add("closingDate", fmt_date(h.closing_date))
    reporter = node.add("reporterID")
    reporter.add("type", str(h.reporter_type).strip())
    reporter.add("code", str(h.reporter_code).strip())
    declarant = node.add("declarantID")
    declarant.add("type", str(h.declarant_type).strip())
    declarant.add("code", str(h.declarant_code).strip())
    node.add("reportingCurrency", str(h.reporting_currency).strip().upper())
    node.add("layout", str(int(h.layout)))
    return node


def validate_header(h: BclHeader, spec: LedgerSpec) -> list[Issue]:
    issues: list[Issue] = []
    end = as_date(h.end_month_date)
    closing = as_date(h.closing_date)
    if end is None:
        issues.append(Issue(ERROR, "HDR-001", "End of period date (header/endMonthDate) is mandatory."))
    if closing is None:
        issues.append(Issue(ERROR, "HDR-002", "Date of the last NAV calculation (header/closingDate) is mandatory."))
    if end and closing and closing > end:
        issues.append(Issue(WARNING, "HDR-003",
                            f"The closing date ({closing}) is after the end of period date ({end}); the NAV calculation date is normally on or before the end of the period."))
    for label, value, code in (("Reporter", h.reporter_type, "HDR-004"), ("Declarant", h.declarant_type, "HDR-006")):
        text = str(value).strip()
        if not text:
            issues.append(Issue(ERROR, code, f"{label} institution type is mandatory (2 digits)."))
        elif not (len(text) == 2 and text.isdigit()):
            issues.append(Issue(ERROR, code, f"{label} institution type must be exactly 2 digits, got {text!r}."))
    for label, value, code in (("Reporter", h.reporter_code, "HDR-005"), ("Declarant", h.declarant_code, "HDR-007")):
        if not str(value).strip():
            issues.append(Issue(ERROR, code, f"{label} institution code is mandatory."))
    currency = str(h.reporting_currency).strip().upper()
    if not currency:
        issues.append(Issue(ERROR, "HDR-008", "Reporting currency (header/reportingCurrency) is mandatory."))
    elif not (len(currency) == 3 and currency.isalpha()):
        issues.append(Issue(ERROR, "HDR-008", f"Reporting currency must be a 3-letter ISO 4217 code, got {currency!r}."))
    elif not is_valid_currency(currency, allow_no_breakdown=False):
        issues.append(Issue(WARNING, "HDR-009", f"Reporting currency {currency!r} is not in the ISO 4217 list."))
    if int(h.layout) != spec.layout:
        issues.append(Issue(ERROR, "HDR-010",
                            f"Layout for {spec.label} must be {spec.layout}, got {h.layout}."))
    return issues


# =============================================================================
# File names
# =============================================================================

def report_filename(spec: LedgerSpec, h: BclHeader, creation: date | None = None, sequence: int = 1) -> str:
    """BCL naming convention, e.g. S0103_L4_202512_B000000789_O001220003_20260105_001.xml.
    Falls back to a clearly-marked placeholder when the header is incomplete, so
    a preparer still gets a downloadable file rather than an exception."""
    period = h.period() or "000000"
    try:
        reporter = filename_id_token(h.reporter_type, h.reporter_code, role="reporter")
    except ValueError:
        reporter = "REPORTER"
    try:
        declarant = filename_id_token(h.declarant_type, h.declarant_code, role="declarant")
    except ValueError:
        declarant = "DECLARANT"
    try:
        return build_filename(spec.file_code, spec.layout, period, reporter, declarant, creation, sequence)
    except ValueError:
        stamp = (creation or date.today()).strftime("%Y%m%d")
        return f"{spec.file_code}_L{spec.layout}_{period}_{reporter}_{declarant}_{stamp}_{int(sequence):03d}.xml"


def ledger_filename(report_key: str, h: BclHeader, creation: date | None = None, sequence: int = 1) -> str:
    return report_filename(LEDGER_SPECS[report_key], h, creation, sequence)


def s44_filename(h: BclHeader, creation: date | None = None, sequence: int = 1) -> str:
    return report_filename(S44_SPEC, h, creation, sequence)


def tptobs_filename(h: BclHeader, creation: date | None = None, sequence: int = 1) -> str:
    return report_filename(TPTOBS_SPEC, h, creation, sequence)


# =============================================================================
# Reported lines (S 1.3 / S 2.13 / S 1.6)
# =============================================================================

def _row_amount(row: dict) -> Any:
    return row.get("amount")


def has_amount(row: dict) -> bool:
    return not blank(_row_amount(row)) and is_number(_row_amount(row))


def _filled_rows(rows: Iterable[dict]) -> list[dict]:
    """Rows that carry an item and a numeric amount — the only ones written to
    the XML. A blank amount means "nothing to report on that line"."""
    return [r for r in rows if str(r.get("item") or "").strip() and has_amount(r)]


def _line_node(row: dict, with_maturity: bool) -> Node:
    line = Node("reportedLine")
    ident = line.add("id")
    ident.add("item", str(row.get("item") or "").strip())
    ident.add("country", str(row.get("country") or "").strip().upper())
    ident.add("currency", str(row.get("currency") or "").strip().upper())
    ident.add("sector", str(row.get("sector") or "").strip())
    if with_maturity:
        ident.add("initialMaturity", str(row.get("maturity") or "").strip())
    line.add("reportedAmount", fmt_decimal(_row_amount(row), AMOUNT_DIGITS))
    return line


def build_ledger_xml(
    report_key: str, header: BclHeader, asset_rows: list[dict], liability_rows: list[dict],
    creation: str | None = None,
) -> str:
    """S 1.3 / S 2.13 / S 1.6 — one document with header + content/assets +
    content/liabilities. The root element, namespace and schema version are
    derived from ``report_key`` alone, so a report can never be emitted under
    another report's namespace."""
    spec = LEDGER_SPECS[report_key]
    root = Node(spec.root)
    root.append(_header_node(header))
    content = root.add("content")
    assets = [r for r in _filled_rows(asset_rows)]
    liabilities = [r for r in _filled_rows(liability_rows)]
    if assets or not spec.sections_optional:
        node = content.add("assets")
        for row in assets:
            node.append(_line_node(row, spec.has_maturity))
    if liabilities or not spec.sections_optional:
        node = content.add("liabilities")
        for row in liabilities:
            node.append(_line_node(row, spec.has_maturity))
    return serialize(root, spec.namespace,
                     {"version": spec.version, "creationDateTime": creation or creation_datetime()})


def _validate_breakdowns(
    rows: list[dict], specs: list[dict[str, str]], section: str, spec: LedgerSpec, issues: list[Issue],
) -> None:
    by_item = {s["item"]: s for s in specs}
    seen: set[tuple] = set()
    for idx, row in enumerate(rows, start=1):
        item = str(row.get("item") or "").strip()
        where = f"{section} line {idx} ({item or 'no item'})"
        rule = by_item.get(item)
        if rule is None:
            issues.append(Issue(ERROR, "LED-001",
                                f"{where}: item {item!r} is not on the {spec.label} chart of accounts."))
            continue
        country = str(row.get("country") or "").strip().upper()
        currency = str(row.get("currency") or "").strip().upper()
        sector = str(row.get("sector") or "").strip()
        maturity = str(row.get("maturity") or "").strip() if spec.has_maturity else NO_BREAKDOWN_MATURITY

        key = (item, country, currency, sector, maturity)
        if key in seen:
            issues.append(Issue(ERROR, "LED-002",
                                f"{where}: duplicate line {item}-{country}-{currency}-{sector}"
                                f"{'-' + maturity if spec.has_maturity else ''}; the XSD requires each combination to appear once."))
        seen.add(key)

        checks = (
            ("country", country, rule["country"], is_valid_country, NO_BREAKDOWN_COUNTRY, "Country"),
            ("currency", currency, rule["currency"], is_valid_currency, NO_BREAKDOWN_CURRENCY, "Currency"),
            ("sector", sector, rule["sector"], is_valid_sector, NO_BREAKDOWN_SECTOR, "Economic sector"),
        )
        if spec.has_maturity:
            checks += (("maturity", maturity, rule["maturity"], is_valid_maturity, NO_BREAKDOWN_MATURITY, "Initial maturity"),)

        for _name, value, expected, validator, no_break, label in checks:
            if not value:
                issues.append(Issue(ERROR, "LED-003", f"{where}: {label.lower()} code is mandatory."))
                continue
            if expected == BREAK:
                if value == no_break:
                    issues.append(Issue(ERROR, "LED-004",
                                        f"{where}: {label.lower()} must be broken down for item {item}; "
                                        f"the 'no breakdown' code {no_break!r} is not accepted on that line."))
                elif not validator(value, allow_no_breakdown=False):
                    issues.append(Issue(ERROR, "LED-005", f"{where}: {label.lower()} code {value!r} is not a valid BCL code."))
            elif value != expected:
                issues.append(Issue(ERROR, "LED-006",
                                    f"{where}: {label.lower()} must be {expected!r} for item {item} "
                                    f"(no breakdown is requested on that line), got {value!r}."))

        if sector == "12100" and country not in FEDERAL_COUNTRIES and country != NO_BREAKDOWN_COUNTRY:
            issues.append(Issue(WARNING, "LED-007",
                                f"{where}: sector 12100 (State government) is only allowed for countries with a federal "
                                f"structure; check that {country!r} is on BCL's list."))

        amount = to_decimal(_row_amount(row))
        if amount is not None and amount < 0 and item not in DEBIT_ALLOWED_ITEMS:
            issues.append(Issue(ERROR, "LED-008",
                                f"{where}: amount {amount} is negative; only lines "
                                f"{', '.join(sorted(DEBIT_ALLOWED_ITEMS))} may have a debit trend."))


def _sum_item(rows: list[dict], item: str):
    total = None
    for row in rows:
        if str(row.get("item") or "").strip() == item:
            value = to_decimal(_row_amount(row))
            if value is not None:
                total = value if total is None else total + value
    return total


def validate_ledger(
    asset_rows: list[dict], liability_rows: list[dict], report_key: str = "s13",
    header: BclHeader | None = None,
) -> list[Issue]:
    """Business validation of S 1.3 / S 2.13 / S 1.6 against that report's own
    compendium of verification rules."""
    spec = LEDGER_SPECS[report_key]
    issues: list[Issue] = []
    if header is not None:
        issues += validate_header(header, spec)

    assets = _filled_rows(asset_rows)
    liabilities = _filled_rows(liability_rows)

    for rows, source in ((asset_rows, "Assets"), (liability_rows, "Liabilities")):
        for idx, row in enumerate(rows, start=1):
            if str(row.get("item") or "").strip() and not blank(_row_amount(row)) and not is_number(_row_amount(row)):
                issues.append(Issue(ERROR, "LED-009",
                                    f"{source} line {idx} ({row.get('item')}): amount {_row_amount(row)!r} is not a number."))

    if not spec.sections_optional:
        if not assets:
            issues.append(Issue(ERROR, "LED-010", "At least one asset line must carry a reported amount."))
        if not liabilities:
            issues.append(Issue(ERROR, "LED-011", "At least one liability line must carry a reported amount."))
    elif not assets and not liabilities:
        issues.append(Issue(ERROR, "LED-012", "At least one line must carry a reported amount."))

    _validate_breakdowns(assets, spec.assets, "Assets", spec, issues)
    _validate_breakdowns(liabilities, spec.liabilities, "Liabilities", spec, issues)

    # Internal rule: total assets == total liabilities (S 1.3 / S 2.13 VER §2.1.1).
    if spec.key in ("s13", "s213"):
        total_assets = _sum_item(assets, TOTAL_ASSETS_ITEM)
        total_liabilities = _sum_item(liabilities, TOTAL_LIABILITIES_ITEM)
        if total_assets is None:
            issues.append(Issue(ERROR, "LED-013", f"The total line {TOTAL_ASSETS_ITEM} must be reported."))
        if total_liabilities is None:
            issues.append(Issue(ERROR, "LED-014", f"The total line {TOTAL_LIABILITIES_ITEM} must be reported."))
        if total_assets is not None and total_liabilities is not None and total_assets != total_liabilities:
            issues.append(Issue(ERROR, "LED-015",
                                f"Total assets ({total_assets}) must equal total liabilities ({total_liabilities}) "
                                f"— lines {TOTAL_ASSETS_ITEM} and {TOTAL_LIABILITIES_ITEM}."))
        # The total line must also equal the sum of the detail lines.
        for rows, total_item, label in ((assets, TOTAL_ASSETS_ITEM, "assets"),
                                        (liabilities, TOTAL_LIABILITIES_ITEM, "liabilities")):
            reported_total = _sum_item(rows, total_item)
            detail = sum((to_decimal(_row_amount(r)) or 0) for r in rows
                         if str(r.get("item") or "").strip() != total_item)
            if reported_total is not None and detail != reported_total:
                issues.append(Issue(WARNING, "LED-016",
                                    f"The {label} total ({reported_total}) does not equal the sum of the detail "
                                    f"lines ({detail}); difference {reported_total - detail}."))
    return issues


# =============================================================================
# S 4.4 — country of marketing
# =============================================================================

def build_s44_xml(header: BclHeader, marketing_rows: list[dict], creation: str | None = None) -> str:
    """S 4.4 — percentage of units/shares placed, by marketing country."""
    root = Node(S44_SPEC.root)
    root.append(_header_node(header))
    content = root.add("content")
    countries = content.add("MarketingCountry")
    for row in _filled_rows(marketing_rows):
        line = countries.add("reportedLine")
        ident = line.add("id")
        ident.add("item", str(row.get("item") or S44_ITEM).strip())
        ident.add("country", str(row.get("country") or "").strip().upper())
        ident.add("dataType", S44_DATA_TYPE)
        line.add("reportedAmount", fmt_decimal(_row_amount(row), S44_DIGITS, fixed=False))
    return serialize(root, S44_SPEC.namespace,
                     {"version": S44_SPEC.version, "creationDateTime": creation or creation_datetime()})


def validate_s44(marketing_rows: list[dict], header: BclHeader | None = None) -> list[Issue]:
    """S 4.4 compendium of verification rules §2.1.1."""
    issues: list[Issue] = []
    if header is not None:
        issues += validate_header(header, S44_SPEC)

    rows = _filled_rows(marketing_rows)
    for idx, row in enumerate(marketing_rows, start=1):
        if str(row.get("country") or "").strip() and blank(_row_amount(row)):
            issues.append(Issue(ERROR, "S44-001",
                                f"Line {idx} ({row.get('country')}): a percentage must be reported for each marketing country."))
        if not blank(_row_amount(row)) and not is_number(_row_amount(row)):
            issues.append(Issue(ERROR, "S44-002", f"Line {idx}: percentage {_row_amount(row)!r} is not a number."))

    if not rows:
        issues.append(Issue(ERROR, "S44-003", "At least one marketing country must be reported."))

    seen: set[str] = set()
    total = 0
    for idx, row in enumerate(rows, start=1):
        item = str(row.get("item") or S44_ITEM).strip()
        country = str(row.get("country") or "").strip().upper()
        where = f"Line {idx} ({country or 'no country'})"
        if item != S44_ITEM:
            issues.append(Issue(ERROR, "S44-004", f"{where}: the only item of report S 4.4 is {S44_ITEM}, got {item!r}."))
        if not country:
            issues.append(Issue(ERROR, "S44-005", f"{where}: the marketing country code is mandatory."))
        elif country not in ISO_3166_ALPHA2:
            issues.append(Issue(ERROR, "S44-006",
                                f"{where}: {country!r} is not an ISO 3166 two-letter country code "
                                f"(no-breakdown and supranational codes are not accepted on this report)."))
        if country in seen:
            issues.append(Issue(ERROR, "S44-007", f"{where}: country {country} is reported more than once; each country must be unique."))
        seen.add(country)

        amount = to_decimal(_row_amount(row))
        if amount is not None:
            total += amount
            if amount < 0:
                issues.append(Issue(ERROR, "S44-008", f"{where}: percentage {amount} must be positive."))
            elif amount > 100:
                issues.append(Issue(ERROR, "S44-009", f"{where}: percentage {amount} must not be greater than 100."))

    if rows and total != 100:
        issues.append(Issue(ERROR, "S44-010",
                            f"The percentages must add up to exactly 100, current total is {total}."))
    return issues


# =============================================================================
# TPTOBS — security-by-security
# =============================================================================

def _code_type(sec: dict) -> str:
    """Normalises the identifier type to the XSD's "1" (ISIN) / "2" (other).
    Accepts the legacy "ISIN"/"Other" labels used by earlier drafts."""
    raw = str(sec.get("code_type") or "").strip()
    if raw in ("1", "2"):
        return raw
    if raw.upper() == "ISIN":
        return "1"
    if raw:
        return "2"
    return "1" if str(sec.get("isin") or "").strip() else "2"


def is_isin_security(sec: dict) -> bool:
    return _code_type(sec) == "1"


def security_type(sec: dict, item: str) -> str:
    """ESA 2010 security type of a security, defaulted from its balance-sheet
    line when the preparer left it blank."""
    value = str(sec.get("esa2010_type") or "").strip()
    if value:
        return value
    allowed = SECURITY_TYPES_BY_ITEM.get(item, ())
    return allowed[0] if allowed else DEBT_TYPE


def security_class(sec: dict, item: str) -> str:
    """Which of the schema's three wrapper elements carries this security:
    ``typeOfShare`` (own shares/units issued), ``debt`` or ``equity``."""
    if item == "2-004000":
        return "typeOfShare"
    return "debt" if security_type(sec, item) == DEBT_TYPE else "equity"


def _quotation(sec: dict) -> str:
    raw = str(sec.get("quotation_type") or "").strip().lower()
    if raw in ("percent", "percentage", "%"):
        return "percent"
    if raw in ("currency", "units", "number"):
        return "currency"
    return "percent" if not blank(sec.get("nominal_amount")) else "currency"


def _quote_node(sec: dict) -> Node:
    if _quotation(sec) == "percent":
        node = Node("percentageQuoted")
        node.add("nominalAmount", fmt_decimal(sec.get("nominal_amount"), AMOUNT_DIGITS))
        node.add("nominalCurrency", str(sec.get("nominal_currency") or "").strip().upper())
    else:
        node = Node("currencyQuoted")
        node.add("numberOfUnits", fmt_decimal(sec.get("number_of_units"), AMOUNT_DIGITS))
    return node


def _debt_supplements(sec: dict) -> Node:
    node = Node("supplements")
    node.add("securityType", DEBT_TYPE)
    node.add("issueDate", fmt_date(sec.get("date_of_issue")))
    node.add("finalMaturityDate", fmt_date(sec.get("date_of_final_maturity")))
    pool = sec.get("pool_factor")
    node.add("poolFactor", fmt_decimal(pool, PERCENTAGE_DIGITS) if not blank(pool) else DEFAULT_POOL_FACTOR)
    node.add("couponType", str(sec.get("coupon_type") or "").strip())
    node.add("couponFrequency", str(sec.get("coupon_frequency") or "").strip())
    node.add("couponLastPaymentDate", fmt_date(sec.get("last_coupon_payment_date")) or fmt_date(sec.get("date_of_issue")))
    node.add("couponRate", fmt_decimal(sec.get("coupon_rate"), PERCENTAGE_DIGITS) or "0")
    return node


def _type_of_share_supplements(sec: dict) -> Node:
    node = Node("supplements")
    node.add("securityType", FUND_SHARE_TYPE)
    node.add("cssfCode", str(sec.get("cssf_class_code") or "").strip())
    node.add("issueCurrency", str(sec.get("issue_currency") or "").strip().upper())
    distributed = sec.get("distributed_amount")
    node.add("distributedAmount", fmt_decimal(distributed, AMOUNT_DIGITS) if not blank(distributed) else "0")
    node.add("splitDate", fmt_date(sec.get("split_date")) or DEFAULT_SPLIT_DATE)
    ratio = sec.get("split_ratio")
    node.add("splitRatio", fmt_decimal(ratio, PERCENTAGE_DIGITS) if not blank(ratio) else DEFAULT_SPLIT_RATIO)
    return node


def _security_node(sec: dict, item: str, side: str) -> Node:
    """One <security>. Its exact shape depends on three things: whether the
    security has an ISIN, whether it sits under assets or liabilities, and its
    ESA 2010 class — see SBS.OBS.xsd, complexTypes OBS.<side>.<ISIN|other>."""
    with_isin = is_isin_security(sec)
    node = Node("security")

    ident = node.add("securityID")
    if with_isin:
        ident.add("codeType", "1")
        ident.add("code", str(sec.get("isin") or "").strip().upper())
    else:
        ident.add("codeType", "2")
        ident.add("code", str(sec.get("other_code") or "").strip())
        ident.add("name", str(sec.get("security_name") or "").strip())
        ident.add("currency", str(sec.get("security_currency") or "").strip().upper())
        issuer = node.add("issuerID")
        lei = str(sec.get("issuer_lei") or "").strip().upper()
        issuer.add("lei", lei or NO_LEI)
        national = issuer.add("nationalID")
        national.add("type", str(sec.get("issuer_nationalid_type") or "").strip() or NO_NATIONAL_ID_TYPE)
        national.add("code", str(sec.get("issuer_nationalid_code") or "").strip() or NO_NATIONAL_ID_CODE)
        issuer.add("country", str(sec.get("issuer_country") or "").strip().upper())
        issuer.add("sector", str(sec.get("issuer_sector") or "").strip())

    node.add("holdSecurityType", str(sec.get("hold_security_type") or "").strip())

    klass = security_class(sec, item)
    wrapper = node.add(klass)
    if klass == "typeOfShare":
        wrapper.append(_type_of_share_supplements(sec))
    elif not with_isin:
        if klass == "debt":
            wrapper.append(_debt_supplements(sec))
        else:
            supplements = wrapper.add("supplements")
            supplements.add("securityType", security_type(sec, item))
    wrapper.append(_quote_node(sec))

    node.add("reportedAmount", fmt_decimal(sec.get("reported_amount"), AMOUNT_DIGITS))
    return node


def securities_of(securities: Iterable[dict], item: str) -> list[dict]:
    return [s for s in securities if str(s.get("line_item") or "").strip() == item]


def line_total(securities: Iterable[dict]):
    total = None
    for sec in securities:
        value = to_decimal(sec.get("reported_amount"))
        if value is not None:
            total = value if total is None else total + value
    return total


def _tptobs_line_node(row: dict, securities: list[dict], side: str) -> Node:
    item = str(row.get("item") or "").strip()
    line = Node("reportedLine")
    ident = line.add("id")
    ident.add("item", item)
    ident.add("country", str(row.get("country") or NO_BREAKDOWN_COUNTRY).strip().upper())
    ident.add("currency", str(row.get("currency") or NO_BREAKDOWN_CURRENCY).strip().upper())
    ident.add("sector", str(row.get("sector") or NO_BREAKDOWN_SECTOR).strip())

    with_isin = [s for s in securities if is_isin_security(s)]
    without_isin = [s for s in securities if not is_isin_security(s)]
    if with_isin:
        node = line.add("ISIN")
        for sec in with_isin:
            node.append(_security_node(sec, item, side))
    if without_isin:
        node = line.add("other")
        for sec in without_isin:
            node.append(_security_node(sec, item, side))

    # The line total must be the sum of the securities it carries (TPTOBS
    # instructions §5.2.x "Information for the balance sheet line").
    total = line_total(securities)
    if total is None:
        total = to_decimal(_row_amount(row)) or 0
    line.add("totalReportedAmount", fmt_decimal(total, AMOUNT_DIGITS))
    return line


def build_tptobs_xml(
    header: BclHeader, asset_lines: list[dict], liability_lines: list[dict], securities: list[dict],
    creation: str | None = None,
) -> str:
    """TPTOBS Layout 3 — <SBS><header/><OBS><assets/><liabilities/></OBS></SBS>,
    each reportedLine nesting the individual securities held or issued under
    that balance-sheet line, split into an <ISIN> and an <other> group."""
    root = Node(TPTOBS_SPEC.root)
    root.append(_header_node(header))
    obs = root.add("OBS")

    for side, lines in (("assets", asset_lines), ("liabilities", liability_lines)):
        kept = []
        for row in lines:
            item = str(row.get("item") or "").strip()
            if not item:
                continue
            secs = securities_of(securities, item)
            if secs or has_amount(row):
                kept.append((row, secs))
        if not kept:
            continue
        node = obs.add(side)
        for row, secs in kept:
            node.append(_tptobs_line_node(row, secs, side))

    return serialize(root, TPTOBS_SPEC.namespace,
                     {"version": TPTOBS_SPEC.version, "creationDateTime": creation or creation_datetime()})


def _validate_security(sec: dict, item: str, side: str, where: str, header: BclHeader | None, issues: list[Issue]) -> None:
    with_isin = is_isin_security(sec)
    sec_type = security_type(sec, item)
    klass = security_class(sec, item)

    # --- identifier (VER rules 2, 6) ---
    if with_isin:
        isin = str(sec.get("isin") or "").strip().upper()
        if not isin:
            issues.append(Issue(ERROR, "TPT-001", f"{where}: an ISIN code is mandatory when the identifier type is ISIN."))
        elif len(isin) != 12:
            issues.append(Issue(ERROR, "TPT-002", f"{where}: ISIN {isin!r} must be 12 characters."))
        elif not isin_prefix_ok(isin):
            issues.append(Issue(ERROR, "TPT-003",
                                f"{where}: {isin!r} does not start with a valid ISIN country prefix; a provisional or "
                                f"pseudo-ISIN must be reported as a security without ISIN (identifier type 2)."))
        elif not isin_checksum_ok(isin):
            issues.append(Issue(ERROR, "TPT-004", f"{where}: ISIN {isin!r} fails the ISO 6166 check digit."))
    else:
        if not str(sec.get("other_code") or "").strip():
            issues.append(Issue(ERROR, "TPT-005", f"{where}: an internal code is mandatory for a security without ISIN."))
        elif len(str(sec.get("other_code")).strip()) > 20:
            issues.append(Issue(ERROR, "TPT-006", f"{where}: the internal code must not exceed 20 characters."))
        if not str(sec.get("security_name") or "").strip():
            issues.append(Issue(ERROR, "TPT-007", f"{where}: the name of the security is mandatory for a security without ISIN."))
        currency = str(sec.get("security_currency") or "").strip().upper()
        if not currency:
            issues.append(Issue(ERROR, "TPT-008", f"{where}: the currency of the security is mandatory for a security without ISIN."))
        elif not is_valid_currency(currency, allow_no_breakdown=False):
            issues.append(Issue(ERROR, "TPT-009", f"{where}: security currency {currency!r} is not a valid ISO 4217 code."))

        # --- issuer identification (instructions §4.3, VER rules 7, 8, 12) ---
        lei = str(sec.get("issuer_lei") or "").strip().upper()
        if lei and not lei_format_ok(lei):
            issues.append(Issue(ERROR, "TPT-010",
                                f"{where}: LEI {lei!r} must be 20 characters (18 alphanumeric + 2 check digits); "
                                f"report {NO_LEI} when the issuer has no LEI."))
        country = str(sec.get("issuer_country") or "").strip().upper()
        if not country:
            issues.append(Issue(ERROR, "TPT-011", f"{where}: the country of the issuer is mandatory."))
        elif country == NO_BREAKDOWN_COUNTRY:
            issues.append(Issue(ERROR, "TPT-012", f"{where}: the no-breakdown country code 'XX' is not allowed for the issuer."))
        elif not is_valid_country(country, allow_no_breakdown=False):
            issues.append(Issue(ERROR, "TPT-013", f"{where}: issuer country {country!r} is not a valid ISO 3166 or BCL code."))
        sector = str(sec.get("issuer_sector") or "").strip()
        if not sector:
            issues.append(Issue(ERROR, "TPT-014", f"{where}: the economic sector of the issuer is mandatory."))
        elif sector == NO_BREAKDOWN_SECTOR:
            issues.append(Issue(ERROR, "TPT-015", f"{where}: the no-breakdown sector code '90000' is not allowed for the issuer."))
        elif sector not in REAL_SECTOR_CODES:
            issues.append(Issue(ERROR, "TPT-016", f"{where}: issuer sector {sector!r} is not a BCL 2015 sector code."))
        if sector == "12100" and country and country not in FEDERAL_COUNTRIES:
            issues.append(Issue(WARNING, "TPT-017",
                                f"{where}: sector 12100 (State government) is only allowed for countries with a federal structure."))
        # VER rule 12: own securities issued, reported without ISIN.
        if side == "liabilities" and item in ("2-003000", "2-004000"):
            if country and country != "LU":
                issues.append(Issue(ERROR, "TPT-018",
                                    f"{where}: for own securities issued ({item}) the country of the issuer must be 'LU', got {country!r}."))
            if sector and sector not in FUND_SECTORS:
                issues.append(Issue(ERROR, "TPT-019",
                                    f"{where}: for own securities issued ({item}) the issuer sector must be 33000 (MMF) "
                                    f"or 41000 (non-MMF investment funds), got {sector!r}."))

    # --- type of holding (VER rule 9) ---
    hold = str(sec.get("hold_security_type") or "").strip()
    allowed_hold = HOLD_TYPES_BY_ITEM.get(item, tuple(HOLD_SECURITY_TYPES))
    if not hold:
        issues.append(Issue(ERROR, "TPT-020", f"{where}: the type of holding is mandatory."))
    elif hold not in HOLD_SECURITY_TYPES:
        issues.append(Issue(ERROR, "TPT-021", f"{where}: type of holding {hold!r} is not a BCL code."))
    elif hold not in allowed_hold:
        issues.append(Issue(ERROR, "TPT-022",
                            f"{where}: type of holding {hold!r} is not allowed on line {item}; "
                            f"expected one of {', '.join(allowed_hold)}."))

    # --- ESA 2010 security type (VER rules 11, 13, 14) ---
    allowed_types = SECURITY_TYPES_BY_ITEM.get(item, tuple(ESA2010_SECURITY_TYPES))
    if sec_type not in ESA2010_SECURITY_TYPES:
        issues.append(Issue(ERROR, "TPT-023", f"{where}: security type {sec_type!r} is not an ESA 2010 code."))
    elif sec_type not in allowed_types:
        issues.append(Issue(ERROR, "TPT-024",
                            f"{where}: security type {sec_type!r} is not allowed on line {item}; "
                            f"expected one of {', '.join(allowed_types)}."))
    if not with_isin:
        sector = str(sec.get("issuer_sector") or "").strip()
        if sec_type == FUND_SHARE_TYPE and sector and sector not in FUND_SECTORS:
            issues.append(Issue(ERROR, "TPT-025",
                                f"{where}: for security type F.52 only sectors 33000 and 41000 are allowed, got {sector!r}."))
        if sec_type in ("F.511", "F.512", "F.519") and sector in FUND_SECTORS:
            issues.append(Issue(ERROR, "TPT-026",
                                f"{where}: sectors 33000 and 41000 must not be used with security type {sec_type}."))

    # --- quantity (VER rules 4, 5, 10) ---
    amount = to_decimal(sec.get("reported_amount"))
    if amount is None:
        issues.append(Issue(ERROR, "TPT-027", f"{where}: the reported amount is mandatory."))
    elif amount < 0 and item != "2-004000":
        issues.append(Issue(ERROR, "TPT-028",
                            f"{where}: the reported amount must be greater than or equal to zero "
                            f"(only shares/units issued, line 2-004000, may be negative)."))

    if _quotation(sec) == "percent":
        nominal = to_decimal(sec.get("nominal_amount"))
        nominal_currency = str(sec.get("nominal_currency") or "").strip().upper()
        if nominal is None:
            issues.append(Issue(ERROR, "TPT-029", f"{where}: the nominal capital is mandatory for a security quoted in %."))
        elif amount is not None and amount > 0 and nominal <= 0:
            issues.append(Issue(ERROR, "TPT-030",
                                f"{where}: the nominal capital must be greater than zero when the reported amount is greater than zero."))
        if not nominal_currency:
            issues.append(Issue(ERROR, "TPT-031", f"{where}: the currency of the nominal is mandatory for a security quoted in %."))
        elif nominal_currency == NO_BREAKDOWN_CURRENCY:
            issues.append(Issue(ERROR, "TPT-032", f"{where}: the currency of the nominal must not be 'XXX'."))
        elif not is_valid_currency(nominal_currency, allow_no_breakdown=False):
            issues.append(Issue(ERROR, "TPT-033", f"{where}: nominal currency {nominal_currency!r} is not a valid ISO 4217 code."))
    else:
        units = to_decimal(sec.get("number_of_units"))
        if units is None:
            issues.append(Issue(ERROR, "TPT-034", f"{where}: the number of units is mandatory for a security quoted in currency."))
        elif amount is not None and amount > 0 and units <= 0:
            issues.append(Issue(ERROR, "TPT-035",
                                f"{where}: the number of units must be greater than zero when the reported amount is greater than zero."))

    # --- debt supplements (VER rules 15-23) ---
    if klass == "debt" and not with_isin:
        issue_date = as_date(sec.get("date_of_issue"))
        maturity_date = as_date(sec.get("date_of_final_maturity"))
        last_coupon = as_date(sec.get("last_coupon_payment_date")) or issue_date
        closing = as_date(header.closing_date) if header else None
        if issue_date is None:
            issues.append(Issue(ERROR, "TPT-036", f"{where}: the date of issue is mandatory for a debt security without ISIN."))
        if maturity_date is None:
            issues.append(Issue(ERROR, "TPT-037",
                                f"{where}: the date of final maturity is mandatory for a debt security without ISIN "
                                f"(report {PERPETUAL_MATURITY_DATE} for a perpetual bond)."))
        if issue_date and maturity_date and maturity_date < issue_date:
            issues.append(Issue(ERROR, "TPT-038", f"{where}: the date of final maturity is before the date of issue."))
        if issue_date and closing and issue_date > closing:
            issues.append(Issue(ERROR, "TPT-039",
                                f"{where}: the date of issue ({issue_date}) must be on or before the closing date ({closing})."))
        pool = sec.get("pool_factor")
        pool_value = to_decimal(pool) if not blank(pool) else to_decimal(DEFAULT_POOL_FACTOR)
        if pool_value is not None and pool_value <= 0:
            issues.append(Issue(ERROR, "TPT-040",
                                f"{where}: the pool factor must be greater than zero (report 1 when it does not apply)."))
        coupon_type = str(sec.get("coupon_type") or "").strip()
        coupon_freq = str(sec.get("coupon_frequency") or "").strip()
        if not coupon_type:
            issues.append(Issue(ERROR, "TPT-041", f"{where}: the coupon type is mandatory for a debt security without ISIN."))
        elif coupon_type not in COUPON_TYPES:
            issues.append(Issue(ERROR, "TPT-042", f"{where}: coupon type {coupon_type!r} is not a BCL code."))
        if not coupon_freq:
            issues.append(Issue(ERROR, "TPT-043", f"{where}: the coupon frequency is mandatory for a debt security without ISIN."))
        elif coupon_freq not in COUPON_FREQUENCIES:
            issues.append(Issue(ERROR, "TPT-044", f"{where}: coupon frequency {coupon_freq!r} is not a BCL code."))
        if (coupon_type == "04") != (coupon_freq == "00") and coupon_type and coupon_freq:
            issues.append(Issue(ERROR, "TPT-045",
                                f"{where}: the coupon type 'zero coupon' (04) may only be combined with the coupon "
                                f"frequency 'zero coupon' (00), and vice versa."))
        if last_coupon and issue_date and last_coupon < issue_date:
            issues.append(Issue(ERROR, "TPT-046", f"{where}: the payment date of the last coupon is before the date of issue."))
        if last_coupon and maturity_date and last_coupon > maturity_date:
            issues.append(Issue(ERROR, "TPT-047", f"{where}: the payment date of the last coupon is after the date of final maturity."))
        if last_coupon and closing:
            gap = (closing - last_coupon).days
            limit = COUPON_FREQUENCY_MAX_DAYS.get(coupon_freq)
            if gap < 0:
                issues.append(Issue(ERROR, "TPT-048",
                                    f"{where}: the payment date of the last coupon ({last_coupon}) is after the closing date ({closing})."))
            elif limit is not None and gap >= limit:
                issues.append(Issue(WARNING, "TPT-049",
                                    f"{where}: {gap} days between the closing date and the last coupon payment is not "
                                    f"consistent with a coupon frequency of {coupon_freq} ({COUPON_FREQUENCIES[coupon_freq]}, "
                                    f"limit {limit} days)."))
        if blank(sec.get("coupon_rate")):
            issues.append(Issue(WARNING, "TPT-050", f"{where}: no coupon rate reported; 0 will be sent."))

    # --- shares/units issued supplements (VER rules 25-27) ---
    if klass == "typeOfShare":
        cssf_code = str(sec.get("cssf_class_code") or "").strip()
        if not cssf_code:
            issues.append(Issue(ERROR, "TPT-051", f"{where}: the CSSF class code is mandatory for shares/units issued."))
        elif len(cssf_code) != 4:
            issues.append(Issue(ERROR, "TPT-052", f"{where}: the CSSF class code must be exactly 4 characters, got {cssf_code!r}."))
        issue_currency = str(sec.get("issue_currency") or "").strip().upper()
        if not issue_currency:
            issues.append(Issue(ERROR, "TPT-053", f"{where}: the issue currency is mandatory for shares/units issued."))
        elif not is_valid_currency(issue_currency, allow_no_breakdown=False):
            issues.append(Issue(ERROR, "TPT-054", f"{where}: issue currency {issue_currency!r} is not a valid ISO 4217 code."))
        ratio = sec.get("split_ratio")
        ratio_value = to_decimal(ratio) if not blank(ratio) else to_decimal(DEFAULT_SPLIT_RATIO)
        if ratio_value is not None and ratio_value <= 0:
            issues.append(Issue(ERROR, "TPT-055",
                                f"{where}: the split ratio must be greater than zero (report 1 when no split occurred)."))


def validate_tptobs(
    asset_lines: list[dict], liability_lines: list[dict], securities: list[dict],
    header: BclHeader | None = None,
) -> list[Issue]:
    """TPTOBS compendium of verification rules §2.1.1."""
    issues: list[Issue] = []
    if header is not None:
        issues += validate_header(header, TPTOBS_SPEC)

    allowed_items = {s["item"] for s in TPTOBS_BREAKDOWN_SPECS_ASSETS + TPTOBS_BREAKDOWN_SPECS_LIABILITIES}
    reported_items: set[str] = set()
    any_line = False

    for side, lines, specs in (("assets", asset_lines, TPTOBS_BREAKDOWN_SPECS_ASSETS),
                               ("liabilities", liability_lines, TPTOBS_BREAKDOWN_SPECS_LIABILITIES)):
        by_item = {s["item"]: s for s in specs}
        for row in lines:
            item = str(row.get("item") or "").strip()
            if not item:
                continue
            secs = securities_of(securities, item)
            if not secs and not has_amount(row):
                continue
            any_line = True
            where = f"{side.capitalize()} line {item}"
            if item in reported_items:
                issues.append(Issue(ERROR, "TPT-060", f"{where}: line {item} is reported more than once."))
            reported_items.add(item)
            if item not in by_item:
                issues.append(Issue(ERROR, "TPT-061",
                                    f"{where}: item {item!r} is not authorised on the TPTOBS {side} side; "
                                    f"expected one of {', '.join(sorted(by_item))}."))
                continue
            # VER rule 2: only the XX-XXX-90000 line is authorised for each item.
            for label, value, expected in (("country", str(row.get("country") or NO_BREAKDOWN_COUNTRY).strip().upper(), NO_BREAKDOWN_COUNTRY),
                                           ("currency", str(row.get("currency") or NO_BREAKDOWN_CURRENCY).strip().upper(), NO_BREAKDOWN_CURRENCY),
                                           ("sector", str(row.get("sector") or NO_BREAKDOWN_SECTOR).strip(), NO_BREAKDOWN_SECTOR)):
                if value != expected:
                    issues.append(Issue(ERROR, "TPT-062",
                                        f"{where}: the only authorised line is {item}-XX-XXX-90000; {label} must be "
                                        f"{expected!r}, got {value!r}."))

            if not secs:
                issues.append(Issue(ERROR, "TPT-063",
                                    f"{where}: an amount is reported but no individual security is attached to that line."))
            for idx, sec in enumerate(secs, start=1):
                _validate_security(sec, item, side, f"{where}, security {idx}", header, issues)

            total = line_total(secs)
            declared = to_decimal(_row_amount(row))
            if total is not None and declared is not None and total != declared:
                issues.append(Issue(ERROR, "TPT-064",
                                    f"{where}: the line total ({declared}) must equal the sum of the amounts of its "
                                    f"securities ({total}); difference {declared - total}."))

            # Duplicate identifiers within a line, distinguished by type of holding.
            seen: set[tuple[str, str]] = set()
            for sec in secs:
                code = (str(sec.get("isin") or "").strip().upper() if is_isin_security(sec)
                        else str(sec.get("other_code") or "").strip())
                hold = str(sec.get("hold_security_type") or "").strip()
                if code and (code, hold) in seen:
                    issues.append(Issue(WARNING, "TPT-065",
                                        f"{where}: security {code} appears more than once with the same type of holding ({hold})."))
                seen.add((code, hold))

    orphans = {str(s.get("line_item") or "").strip() for s in securities} - reported_items
    for item in sorted(o for o in orphans if o):
        issues.append(Issue(ERROR, "TPT-066",
                            f"Securities are attached to line {item!r}, which is not reported"
                            + ("." if item in allowed_items else " and is not a TPTOBS line.")))
    unattached = [s for s in securities if not str(s.get("line_item") or "").strip()]
    if unattached:
        issues.append(Issue(ERROR, "TPT-067",
                            f"{len(unattached)} security/securities are not attached to any balance-sheet line."))
    if not any_line:
        issues.append(Issue(ERROR, "TPT-068", "At least one balance-sheet line with securities must be reported."))
    return issues


# =============================================================================
# Cross-report consistency (S 1.3 / S 2.13 VER §2.1.2 and §2.1.3)
# =============================================================================

def cross_check_ledger_vs_tptobs(
    asset_rows: list[dict], liability_rows: list[dict], tptobs_assets: list[dict],
    tptobs_liabilities: list[dict], securities: list[dict],
) -> list[Issue]:
    """Each of the five security-by-security lines must carry the same total in
    the balance sheet and in TPTOBS."""
    issues: list[Issue] = []
    ledger = {**{str(r.get("item") or "").strip(): r for r in _filled_rows(asset_rows)},
              **{str(r.get("item") or "").strip(): r for r in _filled_rows(liability_rows)}}
    tpt_rows = {str(r.get("item") or "").strip(): r for r in list(tptobs_assets) + list(tptobs_liabilities)}
    for item in SBS_CROSS_CHECK_ITEMS:
        ledger_amount = to_decimal(_row_amount(ledger[item])) if item in ledger else None
        secs = securities_of(securities, item)
        tpt_amount = line_total(secs)
        if tpt_amount is None and item in tpt_rows:
            tpt_amount = to_decimal(_row_amount(tpt_rows[item]))
        if ledger_amount is None and tpt_amount is None:
            continue
        if ledger_amount is None:
            issues.append(Issue(WARNING, "XCHK-001",
                                f"Line {item} is reported in TPTOBS ({tpt_amount}) but not in the balance sheet."))
        elif tpt_amount is None:
            issues.append(Issue(WARNING, "XCHK-002",
                                f"Line {item} is reported in the balance sheet ({ledger_amount}) but not in TPTOBS."))
        elif ledger_amount != tpt_amount:
            issues.append(Issue(WARNING, "XCHK-003",
                                f"Line {item}: the balance sheet reports {ledger_amount} but TPTOBS totals "
                                f"{tpt_amount}; difference {ledger_amount - tpt_amount}."))
    return issues


def cross_check_ledger_vs_s220(liability_rows: list[dict], nav_ref_month: Any) -> list[Issue]:
    """Line 2-004000-XX-XXX-90000 must equal the S 2.20 total NAV (item 3020)."""
    issues: list[Issue] = []
    nav = to_decimal(nav_ref_month)
    shares = None
    for row in _filled_rows(liability_rows):
        if str(row.get("item") or "").strip() == "2-004000":
            shares = to_decimal(_row_amount(row))
    if nav is None or shares is None:
        return issues
    if shares != nav:
        issues.append(Issue(WARNING, "XCHK-004",
                            f"Shares/units issued in the balance sheet ({shares}) differs from the S 2.20 total net "
                            f"asset value of the reference quarter, item 3020 ({nav}); difference {shares - nav}."))
    return issues


# =============================================================================
# Official reference files
# =============================================================================

REPORT_REFERENCE_FILES: dict[str, dict[str, str]] = {
    "s13": {"dir": "s13_s213", "report": "s0103_L4_S0213_L2_report_2025_EN.xlsx",
            "instructions": "S0103_L4_S0213_L2_instructions_2025_EN.pdf", "rules": "S0103_L4_S0213_L2_VER_2025_EN.pdf"},
    "s213": {"dir": "s13_s213", "report": "s0103_L4_S0213_L2_report_2025_EN.xlsx",
             "instructions": "S0103_L4_S0213_L2_instructions_2025_EN.pdf", "rules": "S0103_L4_S0213_L2_VER_2025_EN.pdf"},
    "s16": {"dir": "s16", "report": "S0106_L2_report_2025_EN.xls",
            "instructions": "S0106_L2_instructions_2025_EN.pdf", "rules": ""},
    "s220": {"dir": "s220", "report": "S0220_L0_Report_2025_EN.xls",
             "instructions": "S0220_L0_instructions_2025_EN.pdf",
             "rules": "S-2_20-L0---Quarterly-financial-information---VER.pdf"},
    "s44": {"dir": "s44", "report": "S0404_L0_Report_2025_EN.xls",
            "instructions": "S0404_L0_instructions_2025_EN.pdf", "rules": "S0404_L0_VER_2025_EN.pdf"},
    "tptobs": {"dir": "tptobs", "report": "TPTOBS_L3_report_2025_EN.xls",
               "instructions": "TPTOBS_L3_instructions_2025_EN.pdf", "rules": "TPTOBS_L3_VER_2025_EN.pdf"},
}


def load_report_bytes(report_dir: str, filename: str) -> bytes:
    """Serves a BCL report's own official file (chart of accounts, instructions
    or verification rules) as-is from data/regulation/bcl/<report_dir>/."""
    return (BCL_DATA_DIR / report_dir / filename).read_bytes()


def reference_file(report_key: str, kind: str) -> tuple[str, bytes] | None:
    """(filename, bytes) of an official reference file, or None when that
    report has no such document bundled."""
    entry = REPORT_REFERENCE_FILES.get(report_key)
    if not entry:
        return None
    name = entry.get(kind) or ""
    if not name:
        return None
    path = BCL_DATA_DIR / entry["dir"] / name
    if not path.exists():
        return None
    return name, path.read_bytes()
