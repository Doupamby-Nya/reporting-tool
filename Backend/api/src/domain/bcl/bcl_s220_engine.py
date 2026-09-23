"""BCL S 2.20 — "Quarterly financial information" reporting engine.

Unlike the S 1.3 / S 2.13 / S 1.6 / S 4.4 / TPTOBS family (see
domain.bcl.bcl_engine), S 2.20 is a structured fund- and share-class-level
NAV-movement and P&L report. Every element name, item number (1010-6100),
cardinality, datatype and enumeration below comes from the real BCL
S220.xsd / datatypes.xsd, bundled at core/bcl_schemas/s220/ — the schema's
own <xs:documentation> carries the official item number of every field.

Two things about the schema drive the whole design of this module:

1. Four of the six sections are optional as a *whole* (minOccurs="0"), but
   every child inside them is mandatory, and every amount datatype carries
   the pattern ".+", so an empty element is invalid. A section is therefore
   written all-or-nothing: either it is omitted, or every field in it is
   written, blanks becoming 0. Verification rule R1020D requires the
   financial sections for a "final report" or a "provisional report", so
   they are omitted only for a "null report".

2. The report is cross-checked by BCL against itself (the NAV roll-forward
   of rule R3020A), against TPTOBS and against S 1.3 / S 2.13. Those checks
   are implemented in validation_issues() so a preparer sees them here
   rather than in a BCL rejection notice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from domain.bcl.bcl_codes import is_valid_currency, is_valid_isin, lei_format_ok
from domain.bcl.bcl_common import (
    ERROR, WARNING, ID_TYPE_TO_FILENAME_PREFIX, Issue, Node, as_date, blank, build_filename,
    creation_datetime, errors_of, filename_id_token, fmt_bool, fmt_date, fmt_decimal, is_number,
    serialize, to_decimal, warnings_of,
)

TARGET_NAMESPACE = "http://www.bcl.lu/2025/S2.20"
ROOT = "S220"
VERSION = "1.0"
LAYOUT = 0
FILE_CODE = "S0220"
REPORT_LABEL = "S 2.20 L0"

# Datatype precision (S220 datatypes.xsd).
AMOUNT_DIGITS = 5        # amount / positiveAmount
LARGE_DIGITS = 10        # largeAmount / positiveLargeAmount
PERCENT_DIGITS = 10      # percent

# The BCL institution type of a NAF is fixed (item 2011, rule RNOM20).
NAF_DECLARANT_TYPE = "42"

# Earliest reference period accepted by BCL (rule R1010B).
MIN_REFERENCE_MONTH = "202512"

STATUS_NULL = "null report"
STATUS_PROVISIONAL = "provisional report"
STATUS_FINAL = "final report"
REPORTING_STATUSES = [STATUS_NULL, STATUS_PROVISIONAL, STATUS_FINAL]

NAV_FREQUENCIES: dict[int, str] = {
    1: "Daily", 2: "Daily and month-end", 3: "Semi-weekly", 4: "Semi-weekly and month-end", 5: "Weekly",
    6: "Weekly and month-end", 7: "Weekly and first day of the month",
    8: "Weekly and for each subscription or redemption", 9: "Semi-monthly", 10: "Semi-monthly and month-end",
    11: "Semi-monthly and quarter-end", 12: "Semi-monthly and for each subscription or redemption",
    13: "Monthly", 14: "Monthly and for each subscription or redemption", 15: "Quarterly",
    16: "Quarterly and for each subscription or redemption", 17: "Semi-annually",
    18: "Semi-annually and for each subscription or redemption", 19: "Annually",
    20: "Annually and for each subscription or redemption",
}

NAV_REDEMPTION_FREQUENCIES: dict[int, str] = {
    1: "Daily", 2: "Weekly", 3: "Semi-monthly", 4: "Monthly", 5: "Quarterly",
    6: "Biannual", 7: "Yearly", 8: "Only at the end of maturity", 9: "Other / Irregular",
}

OPEN_CLOSED_END: dict[int, str] = {1: "Open-end investment funds", 2: "Closed-end investment funds"}

REASON_FOR_CLOSING_UCI: dict[int, str] = {
    1: "Put into liquidation",
    2: "Merger into another UCI (wherever it is domiciled)",
    3: "The NAF status has been abandoned and the UCI has adopted a different legal status from the NAF",
    4: "The NAF is temporarily closed",
    5: "The NAF is definitively closed",
}

REASON_FOR_CLOSING_SC: dict[int, str] = {
    1: "Put into liquidation",
    2: "Merger into another unit/share class (wherever it is domiciled)",
    3: "The NAF status is relinquished and the UCI has adopted a legal status other than that of a NAF",
    4: "The unit/share class is temporarily closed",
}

INVESTOR_BASE: dict[int, str] = {
    1: "Professional investor", 2: "Well-informed investor", 3: "Retail investor", 4: "Mixed",
}

# Section 6 chart of accounts, in reporting order (item, label).
S220_SECTION_6: list[tuple[str, str]] = [
    ("6010", "Dividends on shares"),
    ("6011", "...of which from Luxembourg"),
    ("6020", "Dividends on UCI units/shares"),
    ("6021", "...of which from Luxembourg"),
    ("6030", "Interest on bonds and other debt securities"),
    ("6031", "...of which from Luxembourg"),
    ("6040", "Interest on loans, bank and other interest-bearing accounts"),
    ("6041", "Bank interest"),
    ("6042", "...of which from Luxembourg (bank interest)"),
    ("6043", "Other interest"),
    ("6044", "...of which from Luxembourg (other interest)"),
    ("6050", "Other income"),
    ("6051", "Rental income"),
    ("6052", "Commission income"),
    ("6053", "Other (of which, other income)"),
    ("6060", "Charges"),
    ("6061", "Advisory and/or management commissions and/or fees"),
    ("6062", "Depository bank commissions and/or fees"),
    ("6063", "NAF administration fees"),
    ("6064", "Audit and inspection fees"),
    ("6065", "Distribution fees"),
    ("6066", "Other administrative expenses"),
    ("6067", "Subscription tax"),
    ("6068", "Other taxes"),
    ("6070", "Performance fees"),
    ("6080", "Other expenses"),
    ("6081", "Interest paid"),
    ("6082", "Personnel expenses"),
    ("6083", "Rental expenses"),
    ("6084", "Amortisation"),
    ("6085", "Other (of which, other expenses)"),
    ("6090", "Net realised profit or loss on investments and FX positions"),
    ("6100", "Net unrealised profit or loss on investments and FX positions"),
]

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
_CSSF_UCI_RE = re.compile(r"V[0-9]{8}_[0-9]{8}")
_SENDER_CSSF_RE = re.compile(r"[A-Z0-9][0-9]{8}")
MAX_SENDER_CONTACTS = 20


# =============================================================================
# Data model
# =============================================================================

@dataclass
class ShareClass:
    cssf_code: str = ""                                          # 4010
    name: str = ""                                               # 4020
    base_currency: str = "EUR"                                   # 4030
    isin: str = ""                                               # 4040
    launch_date: date | None = None                              # 4050
    closing_date: date | None = None                             # 4060
    reason_for_closing: int | None = None                        # 4070
    spec_instr_fx: bool = False                                  # 4080
    spec_instr_interest_rate: bool = False                       # 4090
    spec_instr_other: bool = False                               # 4100
    investor_base: int | None = None                             # 4110
    units_outstanding: float | None = None                       # 5010
    nav_per_unit_fund_currency: float | None = None              # 5020
    nav_per_unit_shareclass_currency: float | None = None        # 5030
    net_return: float | None = None                              # 5040
    units_issued: float | None = None                            # 5050
    units_redeemed: float | None = None                          # 5060
    distributions: float | None = None                           # 5070
    distributions_per_unit_fund_currency: float | None = None    # 5080
    distributions_per_unit_shareclass_currency: float | None = None  # 5090
    income_fund_currency: float | None = None                    # 5100
    expenses_fund_currency: float | None = None                  # 5110


@dataclass
class S220Submission:
    # 1. General information on the report and the sender
    reference_month: str = ""                    # 1010 (YYYYMM)
    reporting_status: str = STATUS_FINAL         # 1020
    sender_cssf_code: str = ""                   # 1030 (not used by S 2.20, mirrors U 1.1)
    sender_type: str = ""                        # 1031
    sender_code: str = ""                        # 1032
    sender_employees: list[dict] = field(default_factory=list)   # 1040 / 1050

    # 2. General information on the NAF
    uci_cssf_code: str = ""                      # 2010
    declarant_type: str = NAF_DECLARANT_TYPE     # 2011
    declarant_code: str = ""                     # 2012
    uci_name: str = ""                           # 2020
    uci_base_currency: str = "EUR"               # 2030
    uci_lei: str = ""                            # 2040
    valuation_date: date | None = None           # 2050
    nav_freq: int | None = None                  # 2060
    launch_date: date | None = None              # 2070
    closing_date: date | None = None             # 2080
    reason_for_closing: int | None = None        # 2090
    nav_redemption_freq: int | None = None       # 2100
    open_closed_end: int | None = None           # 2110
    uci_comment: str = ""                        # free text

    # 3. Financial information on the NAF
    nav_preceding_ref_month: float | None = None   # 3010
    nav_ref_month: float | None = None             # 3020
    units_issued: float | None = None              # 3030
    units_redeemed: float | None = None            # 3040
    total_distributions: float | None = None       # 3050

    # 4-5. Unit / share class information
    share_classes: list[ShareClass] = field(default_factory=list)

    # 6. Investment income and expenses
    dividends_on_shares: float | None = None             # 6010
    dividends_on_shares_lu: float | None = None          # 6011
    dividends_on_uci_units: float | None = None          # 6020
    dividends_on_uci_units_lu: float | None = None       # 6021
    interest_bonds: float | None = None                  # 6030
    interest_bonds_lu: float | None = None               # 6031
    interest_loans_banks: float | None = None            # 6040
    bank_interest: float | None = None                   # 6041
    bank_interest_lu: float | None = None                # 6042
    other_interest: float | None = None                  # 6043
    other_interest_lu: float | None = None               # 6044
    other_income: float | None = None                    # 6050
    rental_income: float | None = None                   # 6051
    commission_income: float | None = None               # 6052
    other_income_other: float | None = None              # 6053
    charges: float | None = None                         # 6060
    advisory_management_fees: float | None = None        # 6061
    depositary_bank_fees: float | None = None            # 6062
    administration_fees: float | None = None             # 6063
    audit_inspection_fees: float | None = None           # 6064
    distribution_fees: float | None = None               # 6065
    other_administrative_expenses: float | None = None   # 6066
    subscription_tax: float | None = None                # 6067
    other_taxes: float | None = None                     # 6068
    performance_fees: float | None = None                # 6070
    other_expenses: float | None = None                  # 6080
    interest_paid: float | None = None                   # 6081
    personnel_expenses: float | None = None              # 6082
    rental_expenses: float | None = None                 # 6083
    amortisation: float | None = None                    # 6084
    other_expenses_other: float | None = None            # 6085
    net_realised: float | None = None                    # 6090
    net_unrealised: float | None = None                  # 6100

    # ---------------------------------------------------------------- helpers
    @property
    def is_null_report(self) -> bool:
        return self.reporting_status == STATUS_NULL

    def contacts(self) -> list[dict]:
        """Sender contacts that carry at least one filled field."""
        return [e for e in self.sender_employees
                if any(not blank(e.get(k)) for k in ("name", "phone", "email"))]

    def classes(self) -> list[ShareClass]:
        """Share classes that carry at least a code or a name."""
        return [sc for sc in self.share_classes if not blank(sc.cssf_code) or not blank(sc.name)]

    def filename(self, creation: date | None = None, sequence: int = 1) -> str:
        period = self.reference_month.strip() or "000000"
        try:
            sender = filename_id_token(self.sender_type, self.sender_code, role="reporter")
        except ValueError:
            sender = "SENDER"
        try:
            declarant = filename_id_token(self.declarant_type, self.declarant_code, role="declarant")
        except ValueError:
            declarant = "DECLARANT"
        try:
            return build_filename(FILE_CODE, LAYOUT, period, sender, declarant, creation, sequence)
        except ValueError:
            stamp = (creation or date.today()).strftime("%Y%m%d")
            return f"{FILE_CODE}_L{LAYOUT}_{period}_{sender}_{declarant}_{stamp}_{int(sequence):03d}.xml"

    # Kept for backward compatibility with earlier callers.
    def validation_errors(self) -> list[str]:
        return [str(i) for i in errors_of(validation_issues(self))]


# =============================================================================
# Amount helpers
# =============================================================================

def _amount(value: Any, digits: int = AMOUNT_DIGITS) -> str:
    """Every amount inside a section that is written must carry a value: the
    XSD's ".+" pattern rejects an empty element. A blank field means zero."""
    if blank(value):
        return "0"
    text = fmt_decimal(value, digits)
    return text if text is not None else "0"


def _positive(value: Any, digits: int = AMOUNT_DIGITS) -> str:
    """positiveAmount: same, clamped at zero so a stray minus sign cannot make
    the whole document invalid (the value is flagged by validation_issues)."""
    text = _amount(value, digits)
    return "0" if text.startswith("-") else text


def _d(value: Any) -> Decimal:
    return to_decimal(value) or Decimal(0)


def _sum(*values: Any) -> Decimal:
    total = Decimal(0)
    for v in values:
        total += _d(v)
    return total


# =============================================================================
# XML
# =============================================================================

def _general_information(sub: S220Submission) -> Node:
    node = Node("GeneralInformation")
    node.add("ReferenceMonth", sub.reference_month.strip())
    node.add("ReportingStatus", sub.reporting_status.strip())
    cssf = sub.sender_cssf_code.strip().upper()
    if cssf:
        node.add("SenderCssfCode", cssf)
    node.add("TypeOfTheSender", sub.sender_type.strip())
    node.add("CodeOfTheSender", sub.sender_code.strip())
    contacts = node.add("SenderInformations")
    for employee in sub.contacts()[:MAX_SENDER_CONTACTS]:
        entry = contacts.add("SenderInformation")
        entry.add("NameOfEmployee", str(employee.get("name") or "").strip())
        entry.add("PhoneNumber", str(employee.get("phone") or "").strip())
        entry.add("EmailAdress", str(employee.get("email") or "").strip())
    return node


def _uci_general_information(sub: S220Submission) -> Node:
    node = Node("UCIGeneralInformation")
    basic = node.add("UCISignaBasic")
    uci_code = sub.uci_cssf_code.strip().upper()
    if uci_code:
        basic.add("UCICssfCode", uci_code)
    basic.add("TypeOfTheDeclarant", sub.declarant_type.strip())
    basic.add("CodeOfTheDeclarant", sub.declarant_code.strip())
    basic.add("UCIName", sub.uci_name.strip())
    basic.add("UCIBaseCurrency", sub.uci_base_currency.strip().upper())
    lei = sub.uci_lei.strip().upper()
    if lei:
        basic.add("LEI", lei)

    # UCISignaDate is optional as a block, but ValuationDate, NavInformation
    # and LaunchDate are all mandatory inside it.
    if as_date(sub.valuation_date) and as_date(sub.launch_date):
        dates = node.add("UCISignaDate")
        dates.add("ValuationDate", fmt_date(sub.valuation_date))
        nav = dates.add("NavInformation")
        nav.add("NavFreq", str(sub.nav_freq) if sub.nav_freq else None)
        nav.add("NavRedemptionFreq", str(sub.nav_redemption_freq) if sub.nav_redemption_freq else None)
        nav.add("OpenClosedEnd", str(sub.open_closed_end) if sub.open_closed_end else None)
        if sub.uci_comment.strip():
            nav.add("Comment", sub.uci_comment.strip()[:1024])
        dates.add("LaunchDate", fmt_date(sub.launch_date))
        if as_date(sub.closing_date) and sub.reason_for_closing:
            closing = dates.add("ClosingInformation")
            closing.add("ClosingDate", fmt_date(sub.closing_date))
            closing.add("ReasonForClosing", str(sub.reason_for_closing))
    return node


def _uci_financial_information(sub: S220Submission) -> Node:
    node = Node("UCIFinancialInformation")
    node.add("NAVPrecedingRefMonth", _amount(sub.nav_preceding_ref_month))
    node.add("NAVRefMonth", _amount(sub.nav_ref_month))
    node.add("TotUnitsOrSharesIssued", _positive(sub.units_issued))
    node.add("TotUnitsOrSharesRedeemed", _positive(sub.units_redeemed))
    node.add("TotalDistributions", _positive(sub.total_distributions))
    return node


def _share_class_node(sc: ShareClass) -> Node:
    node = Node("Unit_Share_Information")
    node.add("CssfCode", sc.cssf_code.strip())

    general = node.add("UnitShareClassGeneralInformation")
    general.add("Unit_ShareClass_Name", sc.name.strip())
    general.add("BaseCurrency", sc.base_currency.strip().upper())
    isin = sc.isin.strip().upper()
    if isin:
        general.add("ISINCode", isin)
    general.add("LaunchDate", fmt_date(sc.launch_date))
    if as_date(sc.closing_date) and sc.reason_for_closing:
        closing = general.add("ClosingInformation")
        closing.add("ClosingDate", fmt_date(sc.closing_date))
        closing.add("ReasonForClosing", str(sc.reason_for_closing))
    general.add("Unit_ShareClass_SpecInstr_FX", fmt_bool(sc.spec_instr_fx))
    general.add("Unit_ShareClass_SpecInstr_InterestRate", fmt_bool(sc.spec_instr_interest_rate))
    general.add("Unit_ShareClass_SpecInstr_Other", fmt_bool(sc.spec_instr_other))
    general.add("InvestorBase", str(sc.investor_base) if sc.investor_base else None)

    financial = node.add("UnitShareClassFinancialInformation")
    financial.add("NumberUnitOrShareOutstanding", _positive(sc.units_outstanding))
    financial.add("NetAssetValueInSubFundCurrency", _amount(sc.nav_per_unit_fund_currency, LARGE_DIGITS))
    financial.add("NetAssetValueInShareClassCurrency", _amount(sc.nav_per_unit_shareclass_currency, LARGE_DIGITS))
    financial.add("NetReturn", _amount(sc.net_return, PERCENT_DIGITS))
    financial.add("UnitOrSharesIssued", _positive(sc.units_issued))
    financial.add("UnitOrSharesRedeemed", _positive(sc.units_redeemed))
    financial.add("Distributions", _positive(sc.distributions))
    financial.add("AmountDistributionsInUCICurrency", _positive(sc.distributions_per_unit_fund_currency))
    financial.add("AmountDistributionsInShareClassCurrency", _positive(sc.distributions_per_unit_shareclass_currency))
    financial.add("IncomeInFundCurrency", _amount(sc.income_fund_currency))
    financial.add("ExpensesInFundCurrency", _amount(sc.expenses_fund_currency))
    return node


def _income_and_expenses(sub: S220Submission) -> Node:
    node = Node("UCI_Inv_Income_and_Expenses")

    dividends = node.add("DividendsOnShares")
    dividends.add("DividendsOnShares", _positive(sub.dividends_on_shares))
    dividends.add("DivShOfWhichFromLu", _positive(sub.dividends_on_shares_lu))

    uci_dividends = node.add("DividendsOnUCI_Units_Shares")
    uci_dividends.add("DividendsOnUCI_Units_Shares", _positive(sub.dividends_on_uci_units))
    uci_dividends.add("DivUCIOfWhichFromLu", _positive(sub.dividends_on_uci_units_lu))

    interest = node.add("Interest")
    interest.add("Interest_bonds_debt_securities", _positive(sub.interest_bonds))
    interest.add("DivIntBondsOfWhichFromLu", _positive(sub.interest_bonds_lu))

    node.add("InterestLoansBanksBearingAccounts", _positive(sub.interest_loans_banks))

    bank = node.add("BankInterest")
    bank.add("BankInterest", _positive(sub.bank_interest))
    bank.add("BankIntOfWhichFromLu", _positive(sub.bank_interest_lu))

    other_interest = node.add("OtherInterest")
    other_interest.add("OtherInterest", _positive(sub.other_interest))
    other_interest.add("OtherIntOfWhichFromLu", _positive(sub.other_interest_lu))

    node.add("OtherIncome", _positive(sub.other_income))
    income_details = node.add("OtherIncomeDetails")
    income_details.add("RentalIncome", _positive(sub.rental_income))
    income_details.add("CommissionIncome", _positive(sub.commission_income))
    income_details.add("OtherOfWhichFromOtherIncome", _positive(sub.other_income_other))

    node.add("Charges", _positive(sub.charges))
    charges_details = node.add("ChargesDetails")
    charges_details.add("AdvisoryManagementFees", _positive(sub.advisory_management_fees))
    charges_details.add("DepositaryBankFees", _positive(sub.depositary_bank_fees))
    charges_details.add("AdministrationFees", _positive(sub.administration_fees))
    charges_details.add("AuditInspectionFees", _positive(sub.audit_inspection_fees))
    charges_details.add("DistributionFees", _positive(sub.distribution_fees))
    charges_details.add("OtherAdministrativeExpenses", _positive(sub.other_administrative_expenses))
    charges_details.add("SubscriptionTax", _positive(sub.subscription_tax))
    charges_details.add("OtherTaxes", _positive(sub.other_taxes))

    node.add("PerformanceFees", _amount(sub.performance_fees))
    node.add("OtherExpenses", _positive(sub.other_expenses))
    expenses_details = node.add("OtherExpensesDetails")
    expenses_details.add("InterestPaid", _positive(sub.interest_paid))
    expenses_details.add("PersonnelExpenses", _positive(sub.personnel_expenses))
    expenses_details.add("RentalExpenses", _positive(sub.rental_expenses))
    expenses_details.add("Amortisation", _positive(sub.amortisation))
    expenses_details.add("OtherOfWhichFromOtherExpenses", _positive(sub.other_expenses_other))

    node.add("NetRealised", _amount(sub.net_realised))
    node.add("NetUnrealised", _amount(sub.net_unrealised))
    return node


def build_s220_xml(sub: S220Submission, creation: str | None = None) -> str:
    """S 2.20 XML document. The three financial sections are written in full for
    a final or provisional report (rule R1020D) and omitted for a null report."""
    root = Node(ROOT)
    root.append(_general_information(sub))
    root.append(_uci_general_information(sub))
    if not sub.is_null_report:
        root.append(_uci_financial_information(sub))
        classes = sub.classes()
        if classes:
            container = root.add("Unit_Share_Informations")
            for sc in classes:
                container.append(_share_class_node(sc))
        root.append(_income_and_expenses(sub))
    return serialize(root, TARGET_NAMESPACE,
                     {"version": VERSION, "creationDateTime": creation or creation_datetime()})


# =============================================================================
# Validation — S 2.20 compendium of verification rules
# =============================================================================

def _check_total(issues: list[Issue], level: str, code: str, label: str, total: Any, parts: Decimal, part_label: str) -> None:
    if blank(total):
        return
    value = _d(total)
    if value != parts:
        issues.append(Issue(level, code,
                            f"{label} ({value}) must equal {part_label} ({parts}); difference {value - parts}."))


def _check_of_which(issues: list[Issue], code: str, child_label: str, child: Any, parent_label: str, parent: Any) -> None:
    if blank(child) or blank(parent):
        return
    if _d(child) > _d(parent):
        issues.append(Issue(WARNING, code,
                            f"{child_label} ({_d(child)}) must be less than or equal to {parent_label} ({_d(parent)})."))


def validation_issues(sub: S220Submission) -> list[Issue]:
    issues: list[Issue] = []

    # --- 1. Report and sender -------------------------------------------------
    month = sub.reference_month.strip()
    if not month:
        issues.append(Issue(ERROR, "R1010", "Reference month (item 1010) is mandatory."))
    elif not re.fullmatch(r"[0-9]{4}(0[1-9]|1[0-2])", month):
        issues.append(Issue(ERROR, "R1010", f"Reference month (item 1010) must be YYYYMM, got {month!r}."))
    elif month < MIN_REFERENCE_MONTH:
        issues.append(Issue(ERROR, "R1010B",
                            f"Reference month (item 1010) must be greater than or equal to {MIN_REFERENCE_MONTH}, got {month}."))
    elif month[4:] not in ("03", "06", "09", "12"):
        issues.append(Issue(WARNING, "R1010C",
                            f"S 2.20 is a quarterly report; reference month {month} is not a quarter end (March, June, September or December)."))

    if sub.reporting_status not in REPORTING_STATUSES:
        issues.append(Issue(ERROR, "R1020", f"Reporting status (item 1020) must be one of {', '.join(REPORTING_STATUSES)}."))

    cssf = sub.sender_cssf_code.strip().upper()
    if cssf and not _SENDER_CSSF_RE.fullmatch(cssf):
        issues.append(Issue(ERROR, "R1030", f"CSSF code of the sender (item 1030) must be 9 characters, got {cssf!r}."))

    sender_type = sub.sender_type.strip()
    if not sender_type:
        issues.append(Issue(ERROR, "R1031", "Institution type of the sender (item 1031) is mandatory."))
    elif not re.fullmatch(r"[0-9]{2}", sender_type):
        issues.append(Issue(ERROR, "R1031", f"Institution type of the sender (item 1031) must be 2 digits, got {sender_type!r}."))
    elif sender_type not in ID_TYPE_TO_FILENAME_PREFIX:
        issues.append(Issue(WARNING, "R1031A", f"Institution type of the sender {sender_type!r} is not a BCL institution type."))

    sender_code = sub.sender_code.strip()
    if not sender_code:
        issues.append(Issue(ERROR, "R1032", "Institution code of the sender (item 1032) is mandatory."))
    elif not sender_code.isdigit():
        issues.append(Issue(ERROR, "R1032", f"Institution code of the sender (item 1032) must be numeric, got {sender_code!r}."))

    contacts = sub.contacts()
    if not contacts:
        issues.append(Issue(ERROR, "R1040", "At least one contact person (items 1040/1050) is mandatory."))
    if len(contacts) > MAX_SENDER_CONTACTS:
        issues.append(Issue(ERROR, "R1040B",
                            f"At most {MAX_SENDER_CONTACTS} contact persons may be reported, got {len(contacts)}."))
    for idx, employee in enumerate(contacts[:MAX_SENDER_CONTACTS], start=1):
        for key, label, item in (("name", "Name of the employee", "1040"),
                                 ("phone", "Phone number", "1040"),
                                 ("email", "Email address", "1050")):
            if blank(employee.get(key)):
                issues.append(Issue(ERROR, f"R{item}", f"Contact {idx}: {label} (item {item}) is mandatory."))
        email = str(employee.get("email") or "").strip()
        if email and not _EMAIL_RE.fullmatch(email):
            issues.append(Issue(WARNING, "R1050A", f"Contact {idx}: the email address {email!r} does not have a valid format."))

    # --- 2. The NAF -----------------------------------------------------------
    uci_code = sub.uci_cssf_code.strip().upper()
    if uci_code and not _CSSF_UCI_RE.fullmatch(uci_code):
        issues.append(Issue(ERROR, "R2010",
                            f"CSSF code of the NAF (item 2010) must look like V00000001_00000000, got {uci_code!r}."))

    declarant_type = sub.declarant_type.strip()
    if not declarant_type:
        issues.append(Issue(ERROR, "R2011", "BCL institution type of the NAF (item 2011) is mandatory."))
    elif declarant_type != NAF_DECLARANT_TYPE:
        issues.append(Issue(ERROR, "RNOM20",
                            f"BCL institution type of the NAF (item 2011) must be {NAF_DECLARANT_TYPE}, got {declarant_type!r}."))

    declarant_code = sub.declarant_code.strip()
    if not declarant_code:
        issues.append(Issue(ERROR, "R2012", "BCL code of the NAF (item 2012) is mandatory."))
    elif not re.fullmatch(r"[0-9]{14}", declarant_code):
        issues.append(Issue(ERROR, "R2012",
                            f"BCL code of the NAF (item 2012) must be exactly 14 digits "
                            f"(2 for the RCS letter, 7 for the fund, 5 for the compartment), got {declarant_code!r}."))

    if not sub.uci_name.strip():
        issues.append(Issue(ERROR, "R2020", "Name of the NAF (item 2020) is mandatory."))

    currency = sub.uci_base_currency.strip().upper()
    if not currency:
        issues.append(Issue(ERROR, "R2030", "Base currency of the NAF (item 2030) is mandatory."))
    elif not (len(currency) == 3 and currency.isalpha()):
        issues.append(Issue(ERROR, "R2030", f"Base currency of the NAF (item 2030) must be a 3-letter ISO 4217 code, got {currency!r}."))
    elif not is_valid_currency(currency, allow_no_breakdown=False):
        issues.append(Issue(WARNING, "R2030A", f"Base currency {currency!r} is not in the ISO 4217 list."))

    lei = sub.uci_lei.strip().upper()
    if lei and not lei_format_ok(lei):
        issues.append(Issue(WARNING, "R2040A",
                            f"The LEI (item 2040) must be 20 characters (18 alphanumeric + 2 check digits), got {lei!r}."))

    valuation = as_date(sub.valuation_date)
    launch = as_date(sub.launch_date)
    closing = as_date(sub.closing_date)
    if valuation is None:
        issues.append(Issue(ERROR, "R2050", "Valuation date (item 2050) is mandatory."))
    if launch is None:
        issues.append(Issue(ERROR, "R2070", "Launch date (item 2070) is mandatory."))
    if valuation and launch and launch > valuation:
        issues.append(Issue(ERROR, "R2070A",
                            f"The launch date ({launch}) must be before or equal to the valuation date ({valuation})."))
    if valuation and month and re.fullmatch(r"[0-9]{6}", month):
        year, quarter_month = int(month[:4]), int(month[4:])
        end_of_quarter = date(year + (quarter_month == 12), quarter_month % 12 + 1, 1)
        if (valuation - end_of_quarter).days > 20:
            issues.append(Issue(WARNING, "R2050A",
                                f"The valuation date ({valuation}) is more than 20 days after the end of the reference "
                                f"period {month}."))
    if sub.nav_freq is None:
        issues.append(Issue(ERROR, "R2060", "Net asset value calculation frequency (item 2060) is mandatory."))
    elif int(sub.nav_freq) not in NAV_FREQUENCIES:
        issues.append(Issue(ERROR, "R2060", f"Net asset value calculation frequency (item 2060) {sub.nav_freq!r} is not a BCL code."))
    if sub.nav_redemption_freq is None:
        issues.append(Issue(ERROR, "R2100", "Redemption frequency (item 2100) is mandatory."))
    elif int(sub.nav_redemption_freq) not in NAV_REDEMPTION_FREQUENCIES:
        issues.append(Issue(ERROR, "R2100", f"Redemption frequency (item 2100) {sub.nav_redemption_freq!r} is not a BCL code."))
    if sub.open_closed_end is None:
        issues.append(Issue(ERROR, "R2110", "Open / closed-end (item 2110) is mandatory."))
    elif int(sub.open_closed_end) not in OPEN_CLOSED_END:
        issues.append(Issue(ERROR, "R2110", f"Open / closed-end (item 2110) {sub.open_closed_end!r} is not a BCL code."))

    if closing:
        if sub.reason_for_closing is None:
            issues.append(Issue(ERROR, "R2090",
                                "Reason for closing (item 2090) is mandatory when the NAF closed during the reference quarter."))
        elif int(sub.reason_for_closing) not in REASON_FOR_CLOSING_UCI:
            issues.append(Issue(ERROR, "R2090", f"Reason for closing (item 2090) {sub.reason_for_closing!r} is not a BCL code."))
        if valuation and closing > valuation:
            issues.append(Issue(WARNING, "R2080A",
                                f"The closing date ({closing}) must be before or equal to the valuation date ({valuation})."))
        if launch and closing < launch:
            issues.append(Issue(WARNING, "R2080C",
                                f"The closing date ({closing}) must be greater than or equal to the launch date ({launch})."))
    elif sub.reason_for_closing is not None:
        issues.append(Issue(WARNING, "R2080",
                            "A reason for closing (item 2090) is reported without a closing date (item 2080); "
                            "neither will be sent."))

    if sub.is_null_report:
        # A null report carries no financial information at all.
        if sub.classes() or not blank(sub.nav_ref_month):
            issues.append(Issue(WARNING, "R1020N",
                                "The reporting status is 'null report', so the financial sections will not be included in the XML."))
        return issues

    # --- 3. Financial information on the NAF ---------------------------------
    for value, item, label in ((sub.nav_preceding_ref_month, "3010", "Total net asset value of the preceding reference quarter"),
                               (sub.nav_ref_month, "3020", "Total net asset value of the reference quarter"),
                               (sub.units_issued, "3030", "Proceeds from all units/shares issued"),
                               (sub.units_redeemed, "3040", "Payments made for all units/shares redeemed"),
                               (sub.total_distributions, "3050", "Total distributions made")):
        if blank(value):
            issues.append(Issue(ERROR, f"R{item}", f"{label} (item {item}) is mandatory for a {sub.reporting_status}."))
        elif not is_number(value):
            issues.append(Issue(ERROR, f"R{item}", f"{label} (item {item}) is not a number: {value!r}."))
    for value, item, label in ((sub.units_issued, "3030", "Proceeds from all units/shares issued"),
                               (sub.units_redeemed, "3040", "Payments made for all units/shares redeemed"),
                               (sub.total_distributions, "3050", "Total distributions made")):
        if not blank(value) and is_number(value) and _d(value) < 0:
            issues.append(Issue(ERROR, f"R{item}P", f"{label} (item {item}) must not be negative, got {_d(value)}."))

    # Rule R3020A: the NAV roll-forward.
    roll_forward = (
        _d(sub.nav_preceding_ref_month) + _d(sub.units_issued) - _d(sub.units_redeemed) - _d(sub.total_distributions)
        + _sum(sub.dividends_on_shares, sub.dividends_on_uci_units, sub.interest_bonds,
               sub.interest_loans_banks, sub.other_income)
        - _d(sub.charges) - _d(sub.performance_fees) - _d(sub.other_expenses)
        + _d(sub.net_realised) + _d(sub.net_unrealised)
    )
    if not blank(sub.nav_ref_month) and _d(sub.nav_ref_month) != roll_forward:
        issues.append(Issue(WARNING, "R3020A",
                            f"The total net asset value of the reference quarter (item 3020 = {_d(sub.nav_ref_month)}) does not "
                            f"match the NAV roll-forward 3010 + 3030 - 3040 - 3050 + 6010 + 6020 + 6030 + 6040 + 6050 "
                            f"- 6060 - 6070 - 6080 + 6090 + 6100 = {roll_forward}; difference "
                            f"{_d(sub.nav_ref_month) - roll_forward}."))

    # --- 4-5. Share classes ---------------------------------------------------
    classes = sub.classes()
    if not classes:
        issues.append(Issue(ERROR, "R1020D",
                            f"At least one unit/share class must be reported for a {sub.reporting_status} (rule R1020D)."))
    seen_codes: set[str] = set()
    for idx, sc in enumerate(classes, start=1):
        where = f"Unit/share class {idx} ({sc.cssf_code or sc.name or 'unnamed'})"
        code = sc.cssf_code.strip()
        if not code:
            issues.append(Issue(ERROR, "R4010", f"{where}: the code of the unit/share class (item 4010) is mandatory."))
        elif not re.fullmatch(r"[0-9]{4}", code):
            issues.append(Issue(ERROR, "R4010",
                                f"{where}: the code of the unit/share class (item 4010) must be exactly 4 digits, got {code!r}."))
        if code in seen_codes:
            issues.append(Issue(ERROR, "R4010U", f"{where}: the code {code} is used by more than one unit/share class."))
        seen_codes.add(code)

        if not sc.name.strip():
            issues.append(Issue(ERROR, "R4020", f"{where}: the name of the unit/share class (item 4020) is mandatory."))
        sc_currency = sc.base_currency.strip().upper()
        if not sc_currency:
            issues.append(Issue(ERROR, "R4030", f"{where}: the base currency (item 4030) is mandatory."))
        elif not (len(sc_currency) == 3 and sc_currency.isalpha()):
            issues.append(Issue(ERROR, "R4030", f"{where}: the base currency (item 4030) must be a 3-letter ISO 4217 code, got {sc_currency!r}."))
        isin = sc.isin.strip().upper()
        if isin:
            if len(isin) != 12:
                issues.append(Issue(ERROR, "R4040", f"{where}: the ISIN (item 4040) must be 12 characters, got {isin!r}."))
            elif not is_valid_isin(isin):
                issues.append(Issue(WARNING, "R4040A", f"{where}: the ISIN {isin!r} does not follow the ISO 6166 rules."))

        sc_launch = as_date(sc.launch_date)
        sc_closing = as_date(sc.closing_date)
        if sc_launch is None:
            issues.append(Issue(ERROR, "R4050", f"{where}: the launch date (item 4050) is mandatory."))
        else:
            if valuation and sc_launch > valuation:
                issues.append(Issue(WARNING, "R4050A",
                                    f"{where}: the launch date ({sc_launch}) must be before or equal to the NAF valuation date ({valuation})."))
            if launch and sc_launch < launch:
                issues.append(Issue(WARNING, "R4050B",
                                    f"{where}: the launch date ({sc_launch}) must be later than or equal to the NAF launch date ({launch})."))
        if sc_closing:
            if sc.reason_for_closing is None:
                issues.append(Issue(WARNING, "R4070",
                                    f"{where}: a closing date is reported without a reason for closing (item 4070); neither will be sent."))
            elif int(sc.reason_for_closing) not in REASON_FOR_CLOSING_SC:
                issues.append(Issue(ERROR, "R4070", f"{where}: reason for closing (item 4070) {sc.reason_for_closing!r} is not a BCL code."))
            if valuation and sc_closing > valuation:
                issues.append(Issue(WARNING, "R4060A",
                                    f"{where}: the closing date ({sc_closing}) must be before or equal to the valuation date ({valuation})."))
            if sc_launch and sc_closing < sc_launch:
                issues.append(Issue(WARNING, "R4060B",
                                    f"{where}: the closing date ({sc_closing}) must be later than or equal to the launch date ({sc_launch})."))
        if sc.investor_base is None:
            issues.append(Issue(ERROR, "R4110", f"{where}: the investor base (item 4110) is mandatory."))
        elif int(sc.investor_base) not in INVESTOR_BASE:
            issues.append(Issue(ERROR, "R4110", f"{where}: investor base (item 4110) {sc.investor_base!r} is not a BCL code."))

        for value, item, label in ((sc.units_outstanding, "5010", "Number of units/shares outstanding"),
                                   (sc.nav_per_unit_fund_currency, "5020", "Net asset value per unit/share in the base currency of the NAF"),
                                   (sc.nav_per_unit_shareclass_currency, "5030", "Net asset value per unit/share in the base currency of the unit/share class"),
                                   (sc.net_return, "5040", "Net return per unit/share"),
                                   (sc.units_issued, "5050", "Proceeds from units/shares issued"),
                                   (sc.units_redeemed, "5060", "Payments made for units/shares redeemed"),
                                   (sc.distributions, "5070", "Total distributions made"),
                                   (sc.income_fund_currency, "5100", "Income in the base currency of the NAF"),
                                   (sc.expenses_fund_currency, "5110", "Expenses in the base currency of the NAF")):
            if blank(value):
                issues.append(Issue(ERROR, f"R{item}", f"{where}: {label} (item {item}) is mandatory."))
            elif not is_number(value):
                issues.append(Issue(ERROR, f"R{item}", f"{where}: {label} (item {item}) is not a number: {value!r}."))
        for value, item, label in ((sc.units_outstanding, "5010", "Number of units/shares outstanding"),
                                   (sc.units_issued, "5050", "Proceeds from units/shares issued"),
                                   (sc.units_redeemed, "5060", "Payments made for units/shares redeemed"),
                                   (sc.distributions, "5070", "Total distributions made")):
            if not blank(value) and is_number(value) and _d(value) < 0:
                issues.append(Issue(ERROR, f"R{item}P", f"{where}: {label} (item {item}) must not be negative, got {_d(value)}."))
        if not blank(sc.distributions) and _d(sc.distributions) > 0 and blank(sc.distributions_per_unit_fund_currency):
            issues.append(Issue(WARNING, "R5080A",
                                f"{where}: total distributions (item 5070) are positive, so the amount of distributions per "
                                f"unit/share in the base currency of the NAF (item 5080) must be positive too."))
        if (not blank(sc.distributions) and _d(sc.distributions) > 0 and sc_currency != currency
                and blank(sc.distributions_per_unit_shareclass_currency)):
            issues.append(Issue(WARNING, "R5090A",
                                f"{where}: the base currency differs from the NAF base currency and distributions are positive, "
                                f"so the amount of distributions per unit/share in the class currency (item 5090) must be positive too."))

    # Rules R3020B / R3030A / R3040A / R3050A: fund totals vs the share classes.
    if classes:
        nav_from_classes = sum((_d(sc.units_outstanding) * _d(sc.nav_per_unit_fund_currency) for sc in classes), Decimal(0))
        if not blank(sub.nav_ref_month) and abs(_d(sub.nav_ref_month) - nav_from_classes) > Decimal("0.01"):
            issues.append(Issue(WARNING, "R3020B",
                                f"The total net asset value (item 3020 = {_d(sub.nav_ref_month)}) must equal the sum over the "
                                f"unit/share classes of 5010 x 5020 ({nav_from_classes}); difference "
                                f"{_d(sub.nav_ref_month) - nav_from_classes}."))
        _check_total(issues, WARNING, "R3030A", "Proceeds from all units/shares issued (item 3030)", sub.units_issued,
                     sum((_d(sc.units_issued) for sc in classes), Decimal(0)), "the sum of the items 5050")
        _check_total(issues, WARNING, "R3040A", "Payments made for all units/shares redeemed (item 3040)", sub.units_redeemed,
                     sum((_d(sc.units_redeemed) for sc in classes), Decimal(0)), "the sum of the items 5060")
        _check_total(issues, WARNING, "R3050A", "Total distributions made (item 3050)", sub.total_distributions,
                     sum((_d(sc.distributions) for sc in classes), Decimal(0)), "the sum of the items 5070")
        _check_total(issues, WARNING, "R5100A", "The sum of the income per unit/share class (items 5100)",
                     sum((_d(sc.income_fund_currency) for sc in classes), Decimal(0)),
                     _sum(sub.dividends_on_shares, sub.dividends_on_uci_units, sub.interest_bonds,
                          sub.interest_loans_banks, sub.other_income, sub.net_realised, sub.net_unrealised),
                     "6010 + 6020 + 6030 + 6040 + 6050 + 6090 + 6100")
        _check_total(issues, WARNING, "R5110A", "The sum of the expenses per unit/share class (items 5110)",
                     sum((_d(sc.expenses_fund_currency) for sc in classes), Decimal(0)),
                     _sum(sub.charges, sub.performance_fees, sub.other_expenses), "6060 + 6070 + 6080")

    # --- 6. Investment income and expenses -----------------------------------
    section6 = [
        (sub.dividends_on_shares, "6010"), (sub.dividends_on_shares_lu, "6011"),
        (sub.dividends_on_uci_units, "6020"), (sub.dividends_on_uci_units_lu, "6021"),
        (sub.interest_bonds, "6030"), (sub.interest_bonds_lu, "6031"),
        (sub.interest_loans_banks, "6040"), (sub.bank_interest, "6041"), (sub.bank_interest_lu, "6042"),
        (sub.other_interest, "6043"), (sub.other_interest_lu, "6044"),
        (sub.other_income, "6050"), (sub.rental_income, "6051"), (sub.commission_income, "6052"),
        (sub.other_income_other, "6053"), (sub.charges, "6060"), (sub.advisory_management_fees, "6061"),
        (sub.depositary_bank_fees, "6062"), (sub.administration_fees, "6063"),
        (sub.audit_inspection_fees, "6064"), (sub.distribution_fees, "6065"),
        (sub.other_administrative_expenses, "6066"), (sub.subscription_tax, "6067"),
        (sub.other_taxes, "6068"), (sub.other_expenses, "6080"), (sub.interest_paid, "6081"),
        (sub.personnel_expenses, "6082"), (sub.rental_expenses, "6083"), (sub.amortisation, "6084"),
        (sub.other_expenses_other, "6085"),
    ]
    labels = dict(S220_SECTION_6)
    for value, item in section6:
        if not blank(value) and is_number(value) and _d(value) < 0:
            issues.append(Issue(ERROR, f"R{item}P",
                                f"{labels.get(item, item)} (item {item}) must not be negative, got {_d(value)}; "
                                f"only the performance fees (6070) and the results (6090/6100) may be negative."))

    _check_total(issues, WARNING, "R6040A", "Interest on loans, bank and other interest-bearing accounts (item 6040)",
                 sub.interest_loans_banks, _sum(sub.bank_interest, sub.other_interest), "6041 + 6043")
    _check_total(issues, WARNING, "R6050A", "Other income (item 6050)", sub.other_income,
                 _sum(sub.rental_income, sub.commission_income, sub.other_income_other), "6051 + 6052 + 6053")
    _check_total(issues, WARNING, "R6060A", "Charges (item 6060)", sub.charges,
                 _sum(sub.advisory_management_fees, sub.depositary_bank_fees, sub.administration_fees,
                      sub.audit_inspection_fees, sub.distribution_fees, sub.other_administrative_expenses,
                      sub.subscription_tax, sub.other_taxes), "the sum of the items 6061 to 6068")
    _check_total(issues, WARNING, "R6080A", "Other expenses (item 6080)", sub.other_expenses,
                 _sum(sub.interest_paid, sub.personnel_expenses, sub.rental_expenses, sub.amortisation,
                      sub.other_expenses_other), "the sum of the items 6081 to 6085")

    _check_of_which(issues, "R6011A", "Dividends on shares of which from Luxembourg (item 6011)", sub.dividends_on_shares_lu,
                    "the dividends on shares (item 6010)", sub.dividends_on_shares)
    _check_of_which(issues, "R6021A", "Dividends on UCI units/shares of which from Luxembourg (item 6021)", sub.dividends_on_uci_units_lu,
                    "the dividends on UCI units/shares (item 6020)", sub.dividends_on_uci_units)
    _check_of_which(issues, "R6031A", "Interest on bonds of which from Luxembourg (item 6031)", sub.interest_bonds_lu,
                    "the interest on bonds and other debt securities (item 6030)", sub.interest_bonds)
    _check_of_which(issues, "R6041A", "Bank interest (item 6041)", sub.bank_interest,
                    "the interest on loans, bank and other interest-bearing accounts (item 6040)", sub.interest_loans_banks)
    _check_of_which(issues, "R6042A", "Bank interest of which from Luxembourg (item 6042)", sub.bank_interest_lu,
                    "the bank interest (item 6041)", sub.bank_interest)
    _check_of_which(issues, "R6043A", "Other interest (item 6043)", sub.other_interest,
                    "the interest on loans, bank and other interest-bearing accounts (item 6040)", sub.interest_loans_banks)
    _check_of_which(issues, "R6044A", "Other interest of which from Luxembourg (item 6044)", sub.other_interest_lu,
                    "the other interest (item 6043)", sub.other_interest)
    for value, item, label in ((sub.rental_income, "6051", "Rental income"),
                               (sub.commission_income, "6052", "Commission income"),
                               (sub.other_income_other, "6053", "Other income - other")):
        _check_of_which(issues, f"R{item}A", f"{label} (item {item})", value, "the other income (item 6050)", sub.other_income)
    for value, item, label in ((sub.advisory_management_fees, "6061", "Advisory and/or management fees"),
                               (sub.depositary_bank_fees, "6062", "Depository bank fees"),
                               (sub.administration_fees, "6063", "NAF administration fees"),
                               (sub.audit_inspection_fees, "6064", "Audit and inspection fees"),
                               (sub.distribution_fees, "6065", "Distribution fees"),
                               (sub.other_administrative_expenses, "6066", "Other administrative expenses"),
                               (sub.subscription_tax, "6067", "Subscription tax"),
                               (sub.other_taxes, "6068", "Other taxes")):
        _check_of_which(issues, f"R{item}A", f"{label} (item {item})", value, "the charges (item 6060)", sub.charges)
    for value, item, label in ((sub.interest_paid, "6081", "Interest paid"),
                               (sub.personnel_expenses, "6082", "Personnel expenses"),
                               (sub.rental_expenses, "6083", "Rental expenses"),
                               (sub.amortisation, "6084", "Amortisation"),
                               (sub.other_expenses_other, "6085", "Other expenses - other")):
        _check_of_which(issues, f"R{item}A", f"{label} (item {item})", value, "the other expenses (item 6080)", sub.other_expenses)

    return issues


def cross_check_s220_vs_tptobs(sub: S220Submission, securities: list[dict]) -> list[Issue]:
    """S 2.20 VER §2.1.2 — the share-class level agreement between S 2.20 and
    the TPTOBS securities reported on line 2-004000."""
    issues: list[Issue] = []
    shares = [s for s in securities if str(s.get("line_item") or "").strip() == "2-004000"]
    if not shares:
        return issues

    total = sum((to_decimal(s.get("reported_amount")) or Decimal(0)) for s in shares)
    if not blank(sub.nav_ref_month) and _d(sub.nav_ref_month) != total:
        issues.append(Issue(WARNING, "XS220-001",
                            f"The total net asset value (item 3020 = {_d(sub.nav_ref_month)}) must equal the total reported "
                            f"on the TPTOBS line 2-004000 ({total}); difference {_d(sub.nav_ref_month) - total}."))

    by_code = {str(s.get("cssf_class_code") or "").strip(): s for s in shares}
    for sc in sub.classes():
        sec = by_code.get(sc.cssf_code.strip())
        if sec is None:
            issues.append(Issue(WARNING, "XS220-002",
                                f"Unit/share class {sc.cssf_code} is not reported on the TPTOBS line 2-004000."))
            continue
        issue_currency = str(sec.get("issue_currency") or "").strip().upper()
        if issue_currency and issue_currency != sc.base_currency.strip().upper():
            issues.append(Issue(WARNING, "XS220-003",
                                f"Unit/share class {sc.cssf_code}: the base currency (item 4030 = {sc.base_currency}) differs "
                                f"from the TPTOBS issue currency ({issue_currency})."))
        tpt_isin = str(sec.get("isin") or "").strip().upper()
        if sc.isin.strip() and tpt_isin and tpt_isin != sc.isin.strip().upper():
            issues.append(Issue(WARNING, "XS220-004",
                                f"Unit/share class {sc.cssf_code}: the ISIN (item 4040 = {sc.isin}) differs from the TPTOBS "
                                f"ISIN ({tpt_isin})."))
        units = to_decimal(sec.get("number_of_units"))
        if units is not None and not blank(sc.units_outstanding) and _d(sc.units_outstanding) != units:
            issues.append(Issue(WARNING, "XS220-005",
                                f"Unit/share class {sc.cssf_code}: the number of units outstanding (item 5010 = "
                                f"{_d(sc.units_outstanding)}) differs from the TPTOBS number of units ({units})."))
        amount = to_decimal(sec.get("reported_amount"))
        if amount is not None and units and not blank(sc.nav_per_unit_fund_currency):
            implied = amount / units
            if abs(implied - _d(sc.nav_per_unit_fund_currency)) > Decimal("0.01"):
                issues.append(Issue(WARNING, "XS220-006",
                                    f"Unit/share class {sc.cssf_code}: the NAV per unit (item 5020 = "
                                    f"{_d(sc.nav_per_unit_fund_currency)}) differs from the TPTOBS reported amount divided by "
                                    f"the number of units ({implied})."))
        distributed = to_decimal(sec.get("distributed_amount"))
        if distributed is not None and not blank(sc.distributions) and _d(sc.distributions) != distributed:
            issues.append(Issue(WARNING, "XS220-007",
                                f"Unit/share class {sc.cssf_code}: the total distributions (item 5070 = {_d(sc.distributions)}) "
                                f"differ from the TPTOBS distributed amount ({distributed})."))
    return issues
