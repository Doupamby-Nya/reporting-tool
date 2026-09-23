"""Request shapes for the BCL statistical reports.

The six reports share one header and, for the four balance-sheet-shaped ones,
one reported-line shape; S 4.4 and S 2.20 have their own. Every field name
matches the element it becomes in the XML, so a reader can follow a value
from the client through to the filing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class BclHeaderModel(BaseModel):
    """The header of every BCL report (endMonthDate ... layout)."""

    end_month_date: date | None = Field(default=None, description="header/endMonthDate — last day of the period")
    closing_date: date | None = Field(default=None, description="header/closingDate — date of the last NAV calculation")
    reporter_type: str = Field(default="", description="header/reporterID/type — 2-digit BCL institution type")
    reporter_code: str = Field(default="", description="header/reporterID/code")
    declarant_type: str = Field(default="", description="header/declarantID/type")
    declarant_code: str = Field(default="", description="header/declarantID/code")
    reporting_currency: str = Field(default="EUR", description="header/reportingCurrency — ISO 4217")

    def to_domain(self, layout: int):
        from domain.bcl.bcl_engine import BclHeader
        return BclHeader(
            end_month_date=self.end_month_date, closing_date=self.closing_date,
            reporter_type=self.reporter_type.strip(), reporter_code=self.reporter_code.strip(),
            declarant_type=self.declarant_type.strip(), declarant_code=self.declarant_code.strip(),
            reporting_currency=self.reporting_currency.strip().upper(), layout=layout,
        )


class ReportedLineModel(BaseModel):
    """One <reportedLine> of a balance-sheet report."""

    item: str = Field(description="Account item, e.g. 1-003000")
    country: str = Field(default="XX")
    currency: str = Field(default="XXX")
    sector: str = Field(default="90000")
    maturity: str = Field(default="I999-999", description="Initial maturity; ignored by TPTOBS")
    amount: float | None = None

    def to_row(self) -> dict[str, Any]:
        return self.model_dump()


class LedgerRequest(BaseModel):
    """S 1.3, S 2.13 and S 1.6 — a header plus two sides of reported lines."""

    header: BclHeaderModel = BclHeaderModel()
    assets: list[ReportedLineModel] = []
    liabilities: list[ReportedLineModel] = []
    creation_date: date | None = Field(default=None, description="Overrides the file-name timestamp; for tests")
    sequence: int = Field(default=1, ge=0, le=999, description="The nnn counter of the file name")


class MarketingCountryModel(BaseModel):
    """One line of S 4.4 — the share of units placed in a country."""

    item: str = Field(default="2-004000")
    country: str = Field(description="ISO 3166 alpha-2")
    amount: float | None = Field(default=None, description="Percentage, two decimals, all lines totalling 100")

    def to_row(self) -> dict[str, Any]:
        return self.model_dump()


class S44Request(BaseModel):
    header: BclHeaderModel = BclHeaderModel()
    marketing_countries: list[MarketingCountryModel] = []
    creation_date: date | None = None
    sequence: int = Field(default=1, ge=0, le=999)


class SecurityModel(BaseModel):
    """One security of the TPTOBS look-through report. Which fields apply
    depends on the identifier type, the balance-sheet line and the ESA 2010
    class — see the BCL instructions, §5.2."""

    line_item: str = Field(description="The reportedLine this security belongs to")
    code_type: str = Field(default="1", description="1 = with an ISIN, 2 = without")
    isin: str = ""
    other_code: str = ""
    security_name: str = ""
    security_currency: str = ""
    issuer_lei: str = ""
    issuer_nationalid_type: str = ""
    issuer_nationalid_code: str = ""
    issuer_country: str = ""
    issuer_sector: str = ""
    hold_security_type: str = ""
    esa2010_type: str = ""
    quotation_type: str = Field(default="percent", description="'percent' or 'currency'")
    nominal_amount: float | None = None
    nominal_currency: str = ""
    number_of_units: float | None = None
    reported_amount: float | None = None
    date_of_issue: date | None = None
    date_of_final_maturity: date | None = None
    pool_factor: float | None = None
    coupon_type: str = ""
    coupon_frequency: str = ""
    last_coupon_payment_date: date | None = None
    coupon_rate: float | None = None
    cssf_class_code: str = ""
    issue_currency: str = ""
    distributed_amount: float | None = None
    split_date: date | None = None
    split_ratio: float | None = None

    def to_row(self) -> dict[str, Any]:
        return self.model_dump()


class TptobsRequest(BaseModel):
    """TPTOBS — the line totals are derived from the securities, so a caller
    only has to send the securities themselves."""

    header: BclHeaderModel = BclHeaderModel()
    securities: list[SecurityModel] = []
    creation_date: date | None = None
    sequence: int = Field(default=1, ge=0, le=999)


class ShareClassModel(BaseModel):
    """One unit/share class of S 2.20 — items 4010 to 5110."""

    cssf_code: str = Field(default="", description="Item 4010 — 4 digits")
    name: str = ""
    base_currency: str = "EUR"
    isin: str = ""
    launch_date: date | None = None
    closing_date: date | None = None
    reason_for_closing: int | None = None
    spec_instr_fx: bool = False
    spec_instr_interest_rate: bool = False
    spec_instr_other: bool = False
    investor_base: int | None = None
    units_outstanding: float | None = None
    nav_per_unit_fund_currency: float | None = None
    nav_per_unit_shareclass_currency: float | None = None
    net_return: float | None = None
    units_issued: float | None = None
    units_redeemed: float | None = None
    distributions: float | None = None
    distributions_per_unit_fund_currency: float | None = None
    distributions_per_unit_shareclass_currency: float | None = None
    income_fund_currency: float | None = None
    expenses_fund_currency: float | None = None


class SenderContactModel(BaseModel):
    """Items 1040 and 1050 — at least one contact is mandatory."""

    name: str = ""
    phone: str = ""
    email: str = ""


class S220Request(BaseModel):
    """S 2.20 — quarterly financial information, items 1010 to 6100."""

    reference_month: str = Field(default="", description="Item 1010 — YYYYMM")
    reporting_status: str = Field(default="final report", description="Item 1020")
    sender_cssf_code: str = ""
    sender_type: str = Field(default="", description="Item 1031")
    sender_code: str = Field(default="", description="Item 1032")
    sender_employees: list[SenderContactModel] = []

    uci_cssf_code: str = Field(default="", description="Item 2010")
    declarant_type: str = Field(default="42", description="Item 2011 — always 42 for a NAF")
    declarant_code: str = Field(default="", description="Item 2012 — 14 digits")
    uci_name: str = Field(default="", description="Item 2020")
    uci_base_currency: str = Field(default="EUR", description="Item 2030")
    uci_lei: str = Field(default="", description="Item 2040")
    valuation_date: date | None = Field(default=None, description="Item 2050")
    nav_freq: int | None = Field(default=None, description="Item 2060")
    launch_date: date | None = Field(default=None, description="Item 2070")
    closing_date: date | None = Field(default=None, description="Item 2080")
    reason_for_closing: int | None = Field(default=None, description="Item 2090")
    nav_redemption_freq: int | None = Field(default=None, description="Item 2100")
    open_closed_end: int | None = Field(default=None, description="Item 2110")
    uci_comment: str = ""

    nav_preceding_ref_month: float | None = Field(default=None, description="Item 3010")
    nav_ref_month: float | None = Field(default=None, description="Item 3020")
    units_issued: float | None = Field(default=None, description="Item 3030")
    units_redeemed: float | None = Field(default=None, description="Item 3040")
    total_distributions: float | None = Field(default=None, description="Item 3050")

    share_classes: list[ShareClassModel] = []

    # Section 6 — investment income and expenses, items 6010 to 6100.
    dividends_on_shares: float | None = None
    dividends_on_shares_lu: float | None = None
    dividends_on_uci_units: float | None = None
    dividends_on_uci_units_lu: float | None = None
    interest_bonds: float | None = None
    interest_bonds_lu: float | None = None
    interest_loans_banks: float | None = None
    bank_interest: float | None = None
    bank_interest_lu: float | None = None
    other_interest: float | None = None
    other_interest_lu: float | None = None
    other_income: float | None = None
    rental_income: float | None = None
    commission_income: float | None = None
    other_income_other: float | None = None
    charges: float | None = None
    advisory_management_fees: float | None = None
    depositary_bank_fees: float | None = None
    administration_fees: float | None = None
    audit_inspection_fees: float | None = None
    distribution_fees: float | None = None
    other_administrative_expenses: float | None = None
    subscription_tax: float | None = None
    other_taxes: float | None = None
    performance_fees: float | None = None
    other_expenses: float | None = None
    interest_paid: float | None = None
    personnel_expenses: float | None = None
    rental_expenses: float | None = None
    amortisation: float | None = None
    other_expenses_other: float | None = None
    net_realised: float | None = None
    net_unrealised: float | None = None

    creation_date: date | None = None
    sequence: int = Field(default=1, ge=0, le=999)


class BclSubmissionRequest(BaseModel):
    """A whole BCL submission — used by the cross-report consistency checks,
    which compare the balance sheet against TPTOBS and S 2.20."""

    s13: LedgerRequest | None = None
    s213: LedgerRequest | None = None
    s16: LedgerRequest | None = None
    s44: S44Request | None = None
    tptobs: TptobsRequest | None = None
    s220: S220Request | None = None
