"""XML builders for the two AIFMD Annex IV reporting files.

Both documents are built against the real ESMA schemas bundled at
core/aifmd_schemas/ (AIFMD_DATMAN_V1.2.xsd, AIFMD_DATAIF_V1.2.xsd and the
AIFMD_REPORTING_DataTypes_V1.2.xsd they include), and are validated against
them by domain.aifmd.aifmd_xsd before a preparer can download anything.

Three properties of those schemas shape everything here:

1. **Fixed-cardinality blocks.** Several arrays are declared with an exact
   number of occurrences — five principal markets, five principal
   instruments, five main instruments traded, ten principal exposures, five
   portfolio concentrations, three principal markets, five counterparty
   exposures each way, five borrowing sources. They must always be sent in
   full, ranked 1..N, with the unused ranks padded by the "nothing to report"
   code of that block (NTA_NTA_NOTA for a sub-asset type, NTA_NTA for an
   asset type, NOT for a market code type, a false flag for a counterparty or
   a borrowing source). ``_ranked`` below does that padding.

2. **All-or-nothing optional blocks.** A container is optional, but once it
   is present every mandatory child must carry a value — an empty element is
   invalid, never "not reported". Optional blocks are therefore only opened
   when there is something to put in them.

3. **Conditional and forbidden fields.** The CSSF technical guidance marks
   many fields "M for <condition>, F otherwise": reporting them outside their
   condition is an error in its own right. Those rules are applied here when
   they decide whether an element is written, and reported by
   domain.aifmd.aifmd_validation when they decide whether the data is acceptable.
"""

from __future__ import annotations

from typing import Any, Iterable

from domain.shared.xml_common import (
    Node, blank, creation_datetime, fmt_bool, fmt_date, fmt_decimal, fmt_integer, serialize,
    to_decimal,
)

# ESMA datatype precision (AIFMD_REPORTING_DataTypes_V1.2.xsd).
RATE_DIGITS = 2      # SignedRate15p2Type / UnsignedPercentType
FX_DIGITS = 4        # UnsignedDecimal15p4Type
NA = "NA"            # AlternateTextType, the only non-numeric value of SignedRateNA15p2Type

# "Nothing to report at this rank" codes.
PAD_SUB_ASSET_TYPE = "NTA_NTA_NOTA"
PAD_ASSET_TYPE = "NTA_NTA"
PAD_ASSET_MACRO_TYPE = "NTA"
PAD_MARKET_CODE_TYPE = "NOT"

# Fixed cardinalities, by block.
N_AIFM_MARKETS = 5
N_AIFM_INSTRUMENTS = 5
N_MAIN_INSTRUMENTS = 5
N_PRINCIPAL_EXPOSURES = 10
N_PORTFOLIO_CONCENTRATIONS = 5
N_AIF_MARKETS = 3
N_COUNTERPARTY_EXPOSURES = 5
N_BORROWING_SOURCES = 5
MAX_CCP_EXPOSURES = 3

MONTH_TAGS = ("January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December")

# Sub-asset types whose individual exposure is reported as a single gross
# value rather than a long/short pair (CSSF controls CAF-085 to CAF-087).
GROSS_ONLY_SUB_ASSET_TYPES = ("DER_FEX_INVT", "DER_FEX_HEDG", "DER_IRD_INTR")


# =============================================================================
# Small helpers
# =============================================================================

def _text(value: Any) -> str | None:
    """A string element, or None when there is nothing to report."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _rate(value: Any) -> str | None:
    return fmt_decimal(value, RATE_DIGITS)


def _amount(value: Any) -> str | None:
    """An amount "expressed without decimal places" — every AIFMD amount is
    an xs:integer-backed type."""
    return fmt_integer(value)


def _ranked(rows: Iterable[dict], count: int) -> list[dict]:
    """Exactly ``count`` rows, in rank order. A row that carries a usable
    ``ranking`` keeps its rank; the rest fill the remaining ranks in the order
    given. Missing ranks come back as empty dicts, to be padded by the caller."""
    slots: list[dict | None] = [None] * count
    leftovers: list[dict] = []
    for row in rows or []:
        try:
            rank = int(row.get("ranking"))
        except (TypeError, ValueError):
            leftovers.append(row)
            continue
        if 1 <= rank <= count and slots[rank - 1] is None:
            slots[rank - 1] = row
        else:
            leftovers.append(row)
    for row in leftovers:
        for i in range(count):
            if slots[i] is None:
                slots[i] = row
                break
    return [row if row is not None else {} for row in slots]


def _entity(parent: Node, tag: str, name: Any, bic: Any = None, lei: Any = None) -> Node | None:
    """A ComplexEntityIdentificationType block: the name is mandatory inside
    it, so the whole block is omitted when there is no name (CSSF controls
    CAF-064, CAF-066: an identifier may not be sent without a name)."""
    entity_name = _text(name)
    if entity_name is None:
        return None
    node = parent.add(tag)
    node.add("EntityName", entity_name)
    node.add_if("EntityIdentificationBIC", _text(bic))
    node.add_if("EntityIdentificationLEI", _text(lei))
    return node


def _assumptions(parent: Node, rows: Iterable[dict]) -> None:
    kept = [r for r in (rows or [])
            if not blank(r.get("question_number")) and not blank(r.get("description"))]
    if not kept:
        return
    node = parent.add("Assumptions")
    for row in kept:
        entry = node.add("Assumption")
        entry.add("QuestionNumber", fmt_integer(row.get("question_number")))
        entry.add("AssumptionDescription", _text(row.get("description")))


def _market_identification(parent: Node, code_type: Any, code: Any, *, allow_not: bool) -> None:
    """MarketIdentification — MarketCode is mandatory for "MIC" and forbidden
    for every other code type (CSSF controls CAM-010, CAF-069, CAF-080)."""
    value = _text(code_type) or (PAD_MARKET_CODE_TYPE if allow_not else "XXX")
    node = parent.add("MarketIdentification")
    node.add("MarketCodeType", value)
    if value == "MIC":
        node.add_if("MarketCode", _text(code))


# =============================================================================
# AIFM file (DATMAN)
# =============================================================================

def build_datman_xml(sub, creation: str | None = None) -> str:
    """The AIFM-level file: one AIFMRecordInfo, or one
    CancellationAIFMRecordInfo when the submission cancels a previous report.
    CSSF control FOR-010 refuses a file carrying more than one record."""
    root = Node("AIFMReportingInfo")

    if getattr(sub, "aifm_cancellation", False):
        record = root.add("CancellationAIFMRecordInfo")
        record.add("CancelledAIFMNationalCode", _text(sub.aifm_national_code))
        record.add("CancelledReportingPeriodType", _text(sub.reporting_period_type))
        record.add("CancelledReportingPeriodYear", str(int(sub.reporting_period_year)))
        record.add("CancelledRecordFlag", "C")
    else:
        root.append(_datman_record(sub))

    return serialize(root, None, {
        "ReportingMemberState": _text(sub.reporting_member_state) or "LU",
        "Version": _text(sub.aifm_version) or "1.2",
        "CreationDateAndTime": creation or creation_datetime(),
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation": "AIFMD_DATMAN_V1.2.xsd",
    })


def _datman_record(sub) -> Node:
    record = Node("AIFMRecordInfo")
    record.add("FilingType", _text(sub.aifm_filing_type))
    record.add("AIFMContentType", _text(sub.aifm_content_type))
    record.add("ReportingPeriodStartDate", fmt_date(sub.reporting_period_start))
    record.add("ReportingPeriodEndDate", fmt_date(sub.reporting_period_end))
    record.add("ReportingPeriodType", _text(sub.reporting_period_type))
    record.add("ReportingPeriodYear", str(int(sub.reporting_period_year)))

    # The change quarter is mandatory once a frequency or contents change is
    # reported, and forbidden otherwise (CSSF control CAM-004).
    frequency = _text(sub.aifm_change_frequency_code)
    contents = _text(sub.aifm_change_contents_code)
    record.add_if("AIFMReportingObligationChangeFrequencyCode", frequency)
    record.add_if("AIFMReportingObligationChangeContentsCode", contents)
    if frequency or contents:
        record.add_if("AIFMReportingObligationChangeQuarter", _text(sub.aifm_change_quarter))

    record.add("LastReportingFlag", fmt_bool(sub.aifm_last_reporting_flag))
    _assumptions(record, sub.aifm_assumptions)

    record.add("AIFMReportingCode", str(int(sub.aifm_reporting_code)))
    record.add("AIFMJurisdiction", _text(sub.aifm_jurisdiction))
    record.add("AIFMNationalCode", _text(sub.aifm_national_code))
    record.add("AIFMName", _text(sub.aifm_name))
    record.add("AIFMEEAFlag", fmt_bool(sub.aifm_eea_flag))
    record.add("AIFMNoReportingFlag", fmt_bool(sub.aifm_no_reporting_flag))

    # An empty report carries no description at all.
    if not sub.aifm_no_reporting_flag:
        record.append(_datman_description(sub))
    return record


def _datman_description(sub) -> Node:
    node = Node("AIFMCompleteDescription")

    identifier = Node("AIFMIdentifier")
    identifier.add_if("AIFMIdentifierLEI", _text(sub.aifm_lei))
    identifier.add_if("AIFMIdentifierBIC", _text(sub.aifm_bic))
    if _text(sub.aifm_old_identifier_country) and _text(sub.aifm_old_identifier_code):
        old = identifier.add("OldAIFMIdentifierNCA")
        old.add("ReportingMemberState", _text(sub.aifm_old_identifier_country))
        old.add("AIFMNationalCode", _text(sub.aifm_old_identifier_code))
    if len(identifier):
        node.append(identifier)

    markets = node.add("AIFMPrincipalMarkets")
    for rank, row in enumerate(_ranked(sub.aifm_principal_markets, N_AIFM_MARKETS), start=1):
        entry = markets.add("AIFMFivePrincipalMarket")
        entry.add("Ranking", str(rank))
        code_type = _text(row.get("market_code_type")) or PAD_MARKET_CODE_TYPE
        _market_identification(entry, code_type, row.get("market_code"), allow_not=True)
        if code_type != PAD_MARKET_CODE_TYPE:
            entry.add_if("AggregatedValueAmount", _amount(row.get("aggregated_value")))

    instruments = node.add("AIFMPrincipalInstruments")
    for rank, row in enumerate(_ranked(sub.aifm_principal_instruments, N_AIFM_INSTRUMENTS), start=1):
        entry = instruments.add("AIFMPrincipalInstrument")
        entry.add("Ranking", str(rank))
        sub_asset = _text(row.get("sub_asset_type")) or PAD_SUB_ASSET_TYPE
        entry.add("SubAssetType", sub_asset)
        if sub_asset != PAD_SUB_ASSET_TYPE:
            entry.add_if("AggregatedValueAmount", _amount(row.get("aggregated_value")))

    node.add("AUMAmountInEuro", _amount(sub.total_aum_eur) or "0")

    currency = node.add("AIFMBaseCurrencyDescription")
    currency.add("BaseCurrency", _text(sub.aifm_base_currency) or "EUR")
    currency.add("AUMAmountInBaseCurrency", _amount(sub.total_aum_base_currency) or "0")
    # The FX block only applies when the base currency is not the euro
    # (CSSF controls CAM-017, CAM-020).
    if (_text(sub.aifm_base_currency) or "EUR").upper() != "EUR":
        rate_type = _text(sub.aifm_fx_ref_rate_type)
        currency.add_if("FXEURReferenceRateType", rate_type)
        currency.add_if("FXEURRate", fmt_decimal(sub.eur_fx_rate, FX_DIGITS))
        if rate_type == "OTH":
            currency.add_if("FXEUROtherReferenceRateDescription", _text(sub.aifm_fx_ref_rate_description))
    return node


# =============================================================================
# AIF file (DATAIF)
# =============================================================================

def content_needs_individual_info(content_type: Any) -> bool:
    """Article 24(2) content — the AIFIndividualInfo block."""
    return str(content_type).strip() in ("2", "4")


def content_needs_leverage_info(content_type: Any) -> bool:
    """Article 24(2) or 24(4) content — the AIFLeverageInfo block. CSSF
    control CSSF-045 requires the gross and commitment leverage rates for
    content types 2, 4 and 5."""
    return str(content_type).strip() in ("2", "4", "5")


def content_needs_article_24_4(content_type: Any) -> bool:
    """Article 24(4) content — the five largest sources of borrowed cash."""
    return str(content_type).strip() in ("4", "5")


def build_dataif_xml(sub, creation: str | None = None) -> str:
    """The AIF-level file: one AIFRecordInfo, or one
    CancellationAIFRecordInfo when the submission cancels a previous report."""
    root = Node("AIFReportingInfo")

    if getattr(sub, "aif_cancellation", False):
        record = root.add("CancellationAIFRecordInfo")
        # The AIF code comes first in this record, unlike everywhere else.
        record.add("CancelledAIFNationalCode", _text(sub.aif_national_code_full))
        record.add("CancelledAIFMNationalCode", _text(sub.aifm_national_code))
        record.add("CancelledReportingPeriodType", _text(sub.reporting_period_type))
        record.add("CancelledReportingPeriodYear", str(int(sub.reporting_period_year)))
        record.add("CancelledRecordFlag", "C")
    else:
        root.append(_dataif_record(sub))

    return serialize(root, None, {
        "ReportingMemberState": _text(sub.reporting_member_state) or "LU",
        "Version": _text(sub.aif_version) or "1.2",
        "CreationDateAndTime": creation or creation_datetime(),
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation": "AIFMD_DATAIF_V1.2.xsd",
    })


def _dataif_record(sub) -> Node:
    record = Node("AIFRecordInfo")
    record.add("FilingType", _text(sub.aif_filing_type))
    record.add("AIFContentType", _text(sub.aif_content_type))
    record.add("ReportingPeriodStartDate", fmt_date(sub.reporting_period_start))
    record.add("ReportingPeriodEndDate", fmt_date(sub.reporting_period_end))
    record.add("ReportingPeriodType", _text(sub.reporting_period_type))
    record.add("ReportingPeriodYear", str(int(sub.reporting_period_year)))

    frequency = _text(sub.aif_change_frequency_code)
    contents = _text(sub.aif_change_contents_code)
    record.add_if("AIFReportingObligationChangeFrequencyCode", frequency)
    record.add_if("AIFReportingObligationChangeContentsCode", contents)
    if frequency or contents:
        record.add_if("AIFReportingObligationChangeQuarter", _text(sub.aif_change_quarter))

    record.add("LastReportingFlag", fmt_bool(sub.aif_last_reporting_flag))
    _assumptions(record, sub.aif_assumptions)

    record.add("AIFMNationalCode", _text(sub.aifm_national_code))
    record.add("AIFNationalCode", _text(sub.aif_national_code_full))
    record.add("AIFName", _text(sub.aif_name))
    record.add("AIFEEAFlag", fmt_bool(sub.aif_eea_flag))
    record.add("AIFReportingCode", str(int(sub.aif_reporting_code)))
    record.add("AIFDomicile", _text(sub.aif_domicile))
    record.add("InceptionDate", fmt_date(sub.aif_inception_date))
    record.add("AIFNoReportingFlag", fmt_bool(sub.aif_no_reporting_flag))

    # CSSF control CAF-012: the description block is forbidden for an empty
    # report and mandatory otherwise (CSSF-018).
    if not sub.aif_no_reporting_flag:
        record.append(_dataif_description(sub))
    return record


def _dataif_description(sub) -> Node:
    node = Node("AIFCompleteDescription")
    node.append(_aif_principal_info(sub))
    if content_needs_individual_info(sub.aif_content_type):
        node.append(_aif_individual_info(sub))
    if content_needs_leverage_info(sub.aif_content_type):
        node.append(_aif_leverage_info(sub))
    return node


# --- AIFPrincipalInfo (Article 24(1)) ----------------------------------------

def _aif_principal_info(sub) -> Node:
    node = Node("AIFPrincipalInfo")

    identification = Node("AIFIdentification")
    identification.add_if("AIFIdentifierLEI", _text(sub.aif_lei))
    identification.add_if("AIFIdentifierISIN", _text(sub.aif_isin))
    identification.add_if("AIFIdentifierCUSIP", _text(sub.aif_cusip))
    identification.add_if("AIFIdentifierSEDOL", _text(sub.aif_sedol))
    identification.add_if("AIFIdentifierTicker", _text(sub.aif_bloomberg))
    identification.add_if("AIFIdentifierRIC", _text(sub.aif_reuters))
    identification.add_if("AIFIdentifierECB", _text(sub.aif_ecb_code))
    if _text(sub.aif_old_identifier_country) and _text(sub.aif_old_identifier_code):
        old = identification.add("OldAIFIdentifierNCA")
        old.add("ReportingMemberState", _text(sub.aif_old_identifier_country))
        old.add("AIFNationalCode", _text(sub.aif_old_identifier_code))
    if len(identification):
        node.append(identification)

    node.add("ShareClassFlag", fmt_bool(sub.aif_share_class_flag))
    # Every share-class identifier is forbidden when the flag is false
    # (CSSF controls CAF-016 to CAF-023).
    if sub.aif_share_class_flag:
        classes = [r for r in (sub.aif_share_classes or []) if _text(r.get("name"))]
        if classes:
            container = node.add("ShareClassIdentification")
            for row in classes:
                entry = container.add("ShareClassIdentifier")
                entry.add_if("ShareClassNationalCode", _text(row.get("national_code")))
                entry.add_if("ShareClassIdentifierISIN", _text(row.get("isin")))
                entry.add_if("ShareClassIdentifierCUSIP", _text(row.get("cusip")))
                entry.add_if("ShareClassIdentifierSEDOL", _text(row.get("sedol")))
                entry.add_if("ShareClassIdentifierTicker", _text(row.get("bloomberg")))
                entry.add_if("ShareClassIdentifierRIC", _text(row.get("reuters")))
                entry.add("ShareClassName", _text(row.get("name")))

    node.append(_aif_description(sub))
    node.append(_main_instruments_traded(sub))
    node.append(_nav_geographical_focus(sub))
    aum_focus = _aum_geographical_focus(sub)
    if aum_focus is not None:
        node.append(aum_focus)
    node.append(_principal_exposures(sub))
    node.append(_most_important_concentration(sub))
    return node


def _aif_description(sub) -> Node:
    node = Node("AIFDescription")
    status = _text(sub.aif_master_feeder_status) or "NONE"
    node.add("AIFMasterFeederStatus", status)

    # The master AIF identification is only allowed for a feeder (CAF-024).
    if status == "FEEDER":
        masters = [r for r in (sub.aif_master_aifs or []) if _text(r.get("name"))]
        if masters:
            container = node.add("MasterAIFsIdentification")
            for row in masters:
                entry = container.add("MasterAIFIdentification")
                entry.add("AIFName", _text(row.get("name")))
                if _text(row.get("country")) and _text(row.get("national_code")):
                    nca = entry.add("AIFIdentifierNCA")
                    nca.add("ReportingMemberState", _text(row.get("country")))
                    nca.add("AIFNationalCode", _text(row.get("national_code")))

    brokers = [r for r in (sub.aif_prime_brokers or []) if _text(r.get("name"))]
    if brokers:
        container = node.add("PrimeBrokers")
        for row in brokers:
            _entity(container, "PrimeBrokerIdentification", row.get("name"), row.get("bic"), row.get("lei"))

    currency = node.add("AIFBaseCurrencyDescription")
    base_currency = (_text(sub.aif_base_currency) or "EUR").upper()
    currency.add("BaseCurrency", base_currency)
    currency.add("AUMAmountInBaseCurrency", _amount(sub.aif_aum_base_currency) or "0")
    # The FX rate and its reference type are mandatory for a non-euro base
    # currency and forbidden otherwise (CSSF controls CAF-030, CAF-031).
    if base_currency != "EUR":
        rate_type = _text(sub.aif_fx_ref_rate_type)
        currency.add_if("FXEURReferenceRateType", rate_type)
        currency.add_if("FXEURRate", fmt_decimal(sub.aif_fx_rate, FX_DIGITS))
        if rate_type == "OTH":
            currency.add_if("FXEUROtherReferenceRateDescription", _text(sub.aif_fx_ref_rate_description))

    node.add("AIFNetAssetValue", _amount(sub.aif_nav) or "0")
    node.add_if("FirstFundingSourceCountry", _text(sub.funding_source_country_1))
    node.add_if("SecondFundingSourceCountry", _text(sub.funding_source_country_2))
    node.add_if("ThirdFundingSourceCountry", _text(sub.funding_source_country_3))
    node.add("PredominantAIFType", _text(sub.predominant_aif_type) or "NONE")

    for group, wrapper, item_tag, type_tag in (
        ("HFND", "HedgeFundInvestmentStrategies", "HedgeFundStrategy", "HedgeFundStrategyType"),
        ("PEQF", "PrivateEquityFundInvestmentStrategies", "PrivateEquityFundInvestmentStrategy", "PrivateEquityFundStrategyType"),
        ("REST", "RealEstateFundInvestmentStrategies", "RealEstateFundStrategy", "RealEstateFundStrategyType"),
        ("FOFS", "FundOfFundsInvestmentStrategies", "FundOfFundsStrategy", "FundOfFundsStrategyType"),
        ("OTHR", "OtherFundInvestmentStrategies", "OtherFundStrategy", "OtherFundStrategyType"),
    ):
        rows = [r for r in (sub.investment_strategies or [])
                if r.get("group") == group and _text(r.get("code"))]
        if not rows:
            continue
        container = node.add(wrapper)
        for row in rows:
            entry = container.add(item_tag)
            code = _text(row.get("code"))
            entry.add(type_tag, code)
            entry.add("PrimaryStrategyFlag", fmt_bool(row.get("primary_flag")))
            # A multi-strategy code carries no NAV rate (CSSF control CAF-040).
            if not code.startswith("MULT_"):
                entry.add_if("StrategyNAVRate", _rate(row.get("nav_rate")))
            # The free-text description belongs to the "other" codes only
            # (CSSF control CAF-041).
            if code.startswith("OTHR_"):
                entry.add_if("StrategyTypeOtherDescription", _text(row.get("other_description")))

    node.add_if("HFTTransactionNumber", _amount(sub.hft_transaction_number))
    node.add_if("HFTBuySellMarketValue", _amount(sub.hft_buy_sell_market_value))
    return node


def _main_instruments_traded(sub) -> Node:
    node = Node("MainInstrumentsTraded")
    for rank, row in enumerate(_ranked(sub.main_instruments, N_MAIN_INSTRUMENTS), start=1):
        entry = node.add("MainInstrumentTraded")
        entry.add("Ranking", str(rank))
        sub_asset = _text(row.get("sub_asset_type")) or PAD_SUB_ASSET_TYPE
        entry.add("SubAssetType", sub_asset)
        if sub_asset == PAD_SUB_ASSET_TYPE:
            # Nothing else may be reported at an unused rank
            # (CSSF controls CAF-042, CAF-043, CAF-053, CAF-054).
            continue

        code_type = _text(row.get("instrument_code_type")) or "NONE"
        entry.add("InstrumentCodeType", code_type)
        entry.add("InstrumentName", _text(row.get("instrument_name")) or "-")
        if code_type == "ISIN":
            entry.add_if("ISINInstrumentIdentification", _text(row.get("isin")))
        elif code_type == "AII":
            aii = entry.add("AIIInstrumentIdentification")
            aii.add("AIIExchangeCode", _text(row.get("aii_exchange_code")))
            aii.add("AIIProductCode", _text(row.get("aii_product_code")))
            derivative_type = _text(row.get("aii_derivative_type")) or "F"
            aii.add("AIIDerivativeType", derivative_type)
            # A future has no put/call sense; ESMA still requires the element,
            # with "F" standing for "not applicable" (CSSF control CAF-050).
            aii.add("AIIPutCallIdentifier", _text(row.get("aii_put_call")) or ("F" if derivative_type == "F" else "C"))
            aii.add("AIIExpiryDate", fmt_date(row.get("aii_expiry_date")))
            # The strike of a future is reported as 0 (CSSF control CAF-052).
            strike = row.get("aii_strike_price")
            aii.add("AIIStrikePrice", fmt_decimal(strike, FX_DIGITS) if not blank(strike) else "0")

        entry.add_if("PositionValue", _amount(row.get("position_value")))
        position_type = _text(row.get("position_type")) or "L"
        entry.add("PositionType", position_type)
        # The hedging rate is only allowed on a short position (CAF-056).
        if position_type == "S":
            entry.add_if("ShortPositionHedgingRate", fmt_decimal(row.get("hedging_rate"), FX_DIGITS))
    return node


def _nav_geographical_focus(sub) -> Node:
    """All eight rates are mandatory; an unreported region is 0 (CAF-057)."""
    from domain.aifmd.aifmd_engine import GEO_REGIONS
    node = Node("NAVGeographicalFocus")
    focus = sub.nav_geo_focus or {}
    for key, nav_tag, _aum_tag in GEO_REGIONS:
        node.add(nav_tag, _rate(focus.get(key)) or "0")
    return node


def _aum_geographical_focus(sub) -> Node | None:
    """Optional as a block, but all eight rates are mandatory once it is
    opened, so it is only written when something was reported (CAF-058)."""
    from domain.aifmd.aifmd_engine import GEO_REGIONS
    focus = sub.aum_geo_focus or {}
    if not any(not blank(focus.get(key)) for key, _n, _a in GEO_REGIONS):
        return None
    node = Node("AUMGeographicalFocus")
    for key, _nav_tag, aum_tag in GEO_REGIONS:
        node.add(aum_tag, _rate(focus.get(key)) or "0")
    return node


def _principal_exposures(sub) -> Node:
    node = Node("PrincipalExposures")
    for rank, row in enumerate(_ranked(sub.ten_principal_exposures, N_PRINCIPAL_EXPOSURES), start=1):
        entry = node.add("PrincipalExposure")
        entry.add("Ranking", str(rank))
        macro = _text(row.get("macro_type")) or PAD_ASSET_MACRO_TYPE
        entry.add("AssetMacroType", macro)
        if macro == PAD_ASSET_MACRO_TYPE:
            # Everything else is forbidden at an unused rank
            # (CSSF controls CAF-060 to CAF-063).
            continue
        entry.add_if("SubAssetType", _text(row.get("sub_asset_type")))
        entry.add("PositionType", _text(row.get("position_type")) or "L")
        entry.add_if("AggregatedValueAmount", _amount(row.get("aggregated_value")))
        entry.add_if("AggregatedValueRate", _rate(row.get("aggregated_value_pct")))
        _entity(entry, "CounterpartyIdentification", row.get("counterparty_name"),
                row.get("counterparty_bic"), row.get("counterparty_lei"))
    return node


def _most_important_concentration(sub) -> Node:
    node = Node("MostImportantConcentration")

    concentrations = node.add("PortfolioConcentrations")
    for rank, row in enumerate(_ranked(sub.portfolio_concentrations, N_PORTFOLIO_CONCENTRATIONS), start=1):
        entry = concentrations.add("PortfolioConcentration")
        entry.add("Ranking", str(rank))
        asset_type = _text(row.get("asset_type")) or PAD_ASSET_TYPE
        entry.add("AssetType", asset_type)
        if asset_type == PAD_ASSET_TYPE:
            continue
        entry.add("PositionType", _text(row.get("position_type")) or "L")
        code_type = _text(row.get("market_code_type")) or "XXX"
        _market_identification(entry, code_type, row.get("market_code"), allow_not=False)
        entry.add_if("AggregatedValueAmount", _amount(row.get("aggregated_value")))
        entry.add_if("AggregatedValueRate", _rate(row.get("aggregated_value_pct")))
        # The counterparty is only allowed for an OTC market (CAF-074).
        if code_type == "OTC":
            _entity(entry, "CounterpartyIdentification", row.get("counterparty_name"),
                    row.get("counterparty_bic"), row.get("counterparty_lei"))

    # The typical position size only applies to private equity (CAF-079).
    if (_text(sub.predominant_aif_type) or "") == "PEQF":
        node.add_if("TypicalPositionSize", _text(sub.typical_position_size))

    markets = node.add("AIFPrincipalMarkets")
    for rank, row in enumerate(_ranked(sub.aif_principal_markets, N_AIF_MARKETS), start=1):
        entry = markets.add("AIFPrincipalMarket")
        entry.add("Ranking", str(rank))
        code_type = _text(row.get("market_code_type")) or PAD_MARKET_CODE_TYPE
        _market_identification(entry, code_type, row.get("market_code"), allow_not=True)
        if code_type != PAD_MARKET_CODE_TYPE:
            entry.add_if("AggregatedValueAmount", _amount(row.get("aggregated_value")))

    investors = node.add("InvestorConcentration")
    investors.add("MainBeneficialOwnersRate", _rate(sub.investor_beneficial_owners_rate) or "0")
    investors.add("ProfessionalInvestorConcentrationRate", _rate(sub.investor_professional_rate) or "0")
    investors.add("RetailInvestorConcentrationRate", _rate(sub.investor_retail_rate) or "0")
    return node


# --- AIFIndividualInfo (Article 24(2)) ---------------------------------------

def _aif_individual_info(sub) -> Node:
    node = Node("AIFIndividualInfo")
    node.append(_individual_exposure(sub))
    node.append(_risk_profile(sub))
    stress = node.add("StressTests")
    stress.add("StressTestsResultArticle15", _text(sub.stress_test_article15) or "")
    stress.add("StressTestsResultArticle16", _text(sub.stress_test_article16) or "")
    return node


def _individual_exposure(sub) -> Node:
    node = Node("IndividualExposure")

    exposures = node.add("AssetTypeExposures")
    rows = [r for r in (sub.instrument_exposures or [])
            if _text(r.get("code")) and _text(r.get("code")) != PAD_SUB_ASSET_TYPE
            and any(not blank(r.get(k)) for k in ("gross_value", "long_value", "short_value"))]
    for row in rows:
        entry = exposures.add("AssetTypeExposure")
        code = _text(row.get("code"))
        entry.add("SubAssetType", code)
        # FX and interest-rate derivatives report a single gross value; every
        # other sub-asset type reports a long and a short value
        # (CSSF controls CAF-085 to CAF-087).
        if code in GROSS_ONLY_SUB_ASSET_TYPES:
            entry.add_if("GrossValue", _amount(row.get("gross_value")))
        else:
            entry.add_if("LongValue", _amount(row.get("long_value")))
            entry.add_if("ShortValue", _amount(row.get("short_value")))
    if not len(exposures):
        # The block needs at least one entry; validation reports the gap.
        entry = exposures.add("AssetTypeExposure")
        entry.add("SubAssetType", "OTH_OTH_OTHR")
        entry.add("LongValue", "0")
        entry.add("ShortValue", "0")

    turnovers = node.add("AssetTypeTurnovers")
    rows = [r for r in (sub.asset_turnovers or [])
            if _text(r.get("code"))
            and any(not blank(r.get(k)) for k in ("market_value", "notional_value"))]
    for row in rows:
        entry = turnovers.add("AssetTypeTurnover")
        entry.add("TurnoverSubAssetType", _text(row.get("code")))
        entry.add_if("MarketValue", _amount(row.get("market_value")))
        entry.add_if("NotionalValue", _amount(row.get("notional_value")))
    if not len(turnovers):
        entry = turnovers.add("AssetTypeTurnover")
        entry.add("TurnoverSubAssetType", "OTH_OTH_OTH")
        entry.add("MarketValue", "0")

    rows = [r for r in (sub.currency_exposures or []) if _text(r.get("currency"))]
    if rows:
        container = node.add("CurrencyExposures")
        for row in rows:
            entry = container.add("CurrencyExposure")
            entry.add("ExposureCurrency", _text(row.get("currency")))
            entry.add_if("LongPositionValue", _amount(row.get("long_value")))
            entry.add_if("ShortPositionValue", _amount(row.get("short_value")))

    # Dominant-influence companies are a private-equity-only table (CAF-092).
    if (_text(sub.predominant_aif_type) or "") == "PEQF":
        rows = [r for r in (sub.dominant_influence_companies or []) if _text(r.get("name"))]
        if rows:
            container = node.add("CompaniesDominantInfluence")
            for row in rows:
                entry = container.add("CompanyDominantInfluence")
                _entity(entry, "CompanyIdentification", row.get("name"), row.get("bic"), row.get("lei"))
                transaction = _text(row.get("transaction_type")) or "OTHR"
                entry.add("TransactionType", transaction)
                if transaction == "OTHR":
                    entry.add_if("OtherTransactionTypeDescription", _text(row.get("other_description")))
                entry.add("VotingRightsRate", _rate(row.get("voting_rights_pct")) or "0")
    return node


def _risk_profile(sub) -> Node:
    node = Node("RiskProfile")

    market = node.add("MarketRiskProfile")
    annual = _text(sub.annual_investment_return_rate)
    if annual is None or annual.upper() == NA:
        market.add("AnnualInvestmentReturnRate", NA)
    else:
        market.add("AnnualInvestmentReturnRate", _rate(annual) or NA)

    measures = [r for r in (sub.market_risk_measures or []) if _text(r.get("code")) and _measure_has_value(r)]
    if measures:
        container = market.add("MarketRiskMeasures")
        for row in measures:
            container.append(_market_risk_measure(row))

    counterparty = _counterparty_risk_profile(sub)
    if counterparty is not None:
        node.append(counterparty)
    liquidity = _liquidity_risk_profile(sub)
    if liquidity is not None:
        node.append(liquidity)
    operational = _operational_risk(sub)
    if operational is not None:
        node.append(operational)
    return node


def _measure_has_value(row: dict) -> bool:
    keys = ("value", "bucket_lt5", "bucket_5_15", "bucket_gt15",
            "vega_current", "vega_lower10", "vega_higher10", "var_value", "var_method")
    return any(not blank(row.get(k)) for k in keys)


def _market_risk_measure(row: dict) -> Node:
    """Each risk measure type carries exactly one of the four value shapes —
    a plain rate, a maturity-bucket triplet, a vega triplet or a VAR block
    (CSSF controls CAF-099 to CAF-107)."""
    node = Node("MarketRiskMeasure")
    code = _text(row.get("code"))
    node.add("RiskMeasureType", code)

    if code in ("NET_DV01", "NET_CS01"):
        bucket = node.add("BucketRiskMeasureValues")
        bucket.add_if("LessFiveYearsRiskMeasureValue", _rate(row.get("bucket_lt5")))
        bucket.add_if("FifthteenYearsRiskMeasureValue", _rate(row.get("bucket_5_15")))
        bucket.add_if("MoreFifthteenYearsRiskMeasureValue", _rate(row.get("bucket_gt15")))
    elif code == "VEGA_EXPO":
        vega = node.add("VegaRiskMeasureValues")
        vega.add_if("CurrentMarketRiskMeasureValue", _rate(row.get("vega_current")))
        vega.add_if("LowerMarketRiskMeasureValue", _rate(row.get("vega_lower10")))
        vega.add_if("HigherMarketRiskMeasureValue", _rate(row.get("vega_higher10")))
    elif code == "VAR":
        var = node.add("VARRiskMeasureValues")
        var.add_if("VARValue", _rate(row.get("var_value")))
        var.add_if("VARCalculationMethodCodeType", _text(row.get("var_method")))
    else:
        node.add("RiskMeasureValue", _rate(row.get("value")) or "0")

    node.add_if("RiskMeasureDescription", _text(row.get("description")))
    return node


def _counterparty_risk_profile(sub) -> Node | None:
    """Optional as a block, but ClearTransactionsThroughCCPFlag and the two
    five-row counterparty tables are mandatory once it is opened."""
    has_data = any([
        sub.trading_pct_securities_exchange is not None, sub.trading_pct_securities_otc is not None,
        sub.trading_pct_derivatives_exchange is not None, sub.trading_pct_derivatives_otc is not None,
        sub.derivatives_ccp_rate is not None, sub.derivatives_bilateral_rate is not None,
        sub.repo_ccp_rate is not None, sub.repo_bilateral_rate is not None, sub.repo_triparty_rate is not None,
        sub.collateral_cash_posted is not None, sub.collateral_securities_posted is not None,
        sub.collateral_other_posted is not None, sub.ccp_clearing_flag is not None,
        any(_text(r.get("name")) for r in (sub.counterparty_exposures_to_aif or [])),
        any(_text(r.get("name")) for r in (sub.counterparty_exposures_from_aif or [])),
    ])
    if not has_data:
        return None

    node = Node("CounterpartyRiskProfile")

    mechanism = Node("TradingClearingMechanism")
    _market_rate_pair(mechanism, "TradedSecurities",
                      sub.trading_pct_securities_exchange, sub.trading_pct_securities_otc)
    _market_rate_pair(mechanism, "TradedDerivatives",
                      sub.trading_pct_derivatives_exchange, sub.trading_pct_derivatives_otc)
    if sub.derivatives_ccp_rate is not None or sub.derivatives_bilateral_rate is not None:
        cleared = mechanism.add("ClearedDerivativesRate")
        cleared.add_if("CCPRate", _rate(sub.derivatives_ccp_rate))
        cleared.add_if("BilateralClearingRate", _rate(sub.derivatives_bilateral_rate))
    if any(v is not None for v in (sub.repo_ccp_rate, sub.repo_bilateral_rate, sub.repo_triparty_rate)):
        repos = mechanism.add("ClearedReposRate")
        repos.add_if("CCPRate", _rate(sub.repo_ccp_rate))
        repos.add_if("BilateralClearingRate", _rate(sub.repo_bilateral_rate))
        repos.add_if("TriPartyRepoClearingRate", _rate(sub.repo_triparty_rate))
    if len(mechanism):
        node.append(mechanism)

    if any(v is not None for v in (sub.collateral_cash_posted, sub.collateral_securities_posted,
                                   sub.collateral_other_posted)):
        collateral = node.add("AllCounterpartyCollateral")
        collateral.add_if("AllCounterpartyCollateralCash", _amount(sub.collateral_cash_posted))
        collateral.add_if("AllCounterpartyCollateralSecurities", _amount(sub.collateral_securities_posted))
        collateral.add_if("AllCounterpartyOtherCollateralPosted", _amount(sub.collateral_other_posted))

    _counterparty_exposures(node, "FundToCounterpartyExposures", "FundToCounterpartyExposure",
                            sub.counterparty_exposures_to_aif)
    _counterparty_exposures(node, "CounterpartyToFundExposures", "CounterpartyToFundExposure",
                            sub.counterparty_exposures_from_aif)

    node.add("ClearTransactionsThroughCCPFlag", fmt_bool(sub.ccp_clearing_flag))
    if sub.ccp_clearing_flag:
        rows = [r for r in (sub.ccp_exposures or []) if _text(r.get("name"))][:MAX_CCP_EXPOSURES]
        if rows:
            container = node.add("CCPExposures")
            for rank, row in enumerate(rows, start=1):
                entry = container.add("CCPExposure")
                entry.add("Ranking", str(rank))
                _entity(entry, "CCPIdentification", row.get("name"), row.get("bic"), row.get("lei"))
                entry.add("CCPExposureValue", _amount(row.get("exposure_value")) or "0")
    return node


def _market_rate_pair(parent: Node, tag: str, regulated: Any, otc: Any) -> None:
    if regulated is None and otc is None:
        return
    node = parent.add(tag)
    node.add_if("RegulatedMarketRate", _rate(regulated))
    node.add_if("OTCRate", _rate(otc))


def _counterparty_exposures(parent: Node, wrapper: str, item_tag: str, rows: Iterable[dict]) -> None:
    """Exactly five ranked entries. An unused rank carries only the ranking and
    a false flag; the identification and the rate are forbidden there
    (CSSF controls CAF-113 to CAF-124)."""
    container = parent.add(wrapper)
    for rank, row in enumerate(_ranked(rows, N_COUNTERPARTY_EXPOSURES), start=1):
        entry = container.add(item_tag)
        entry.add("Ranking", str(rank))
        has_counterparty = bool(_text(row.get("name")))
        entry.add("CounterpartyExposureFlag", fmt_bool(has_counterparty))
        if not has_counterparty:
            continue
        _entity(entry, "CounterpartyIdentification", row.get("name"), row.get("bic"), row.get("lei"))
        entry.add_if("CounterpartyTotalExposureRate", fmt_decimal(row.get("nav_pct"), FX_DIGITS))


def _liquidity_risk_profile(sub) -> Node | None:
    portfolio = _liquidity_bucket_block(sub, "PortfolioLiquidityProfile", "PortfolioLiquidityInDays{}Rate",
                                        sub.portfolio_liquidity, extra=("UnencumberedCash", sub.unencumbered_cash))
    investor = _liquidity_bucket_block(sub, "InvestorLiquidityProfile", "InvestorLiquidityInDays{}Rate",
                                       sub.investor_liquidity)
    redemption = _investor_redemption(sub)
    arrangement = _investor_arrangement(sub)
    groups = [r for r in (sub.investor_groups or []) if _text(r.get("code")) and not blank(r.get("rate"))]
    financing = _financing_liquidity(sub)

    if not any([portfolio, investor, redemption, arrangement, groups, financing]):
        return None

    node = Node("LiquidityRiskProfile")
    if portfolio is not None:
        node.append(portfolio)
    if investor is not None:
        node.append(investor)
    if redemption is not None:
        node.append(redemption)
    if arrangement is not None:
        node.append(arrangement)

    # InvestorGroups is mandatory inside the block; validation reports an
    # empty table rather than the schema rejecting the whole file.
    container = node.add("InvestorGroups")
    for row in groups:
        entry = container.add("InvestorGroup")
        entry.add("InvestorGroupType", _text(row.get("code")))
        entry.add("InvestorGroupRate", _rate(row.get("rate")) or "0")
    if not groups:
        entry = container.add("InvestorGroup")
        entry.add("InvestorGroupType", "OTHR")
        entry.add("InvestorGroupRate", "100")

    if financing is not None:
        node.append(financing)
    return node


_BUCKET_TAGS = ("0to1", "2to7", "8to30", "31to90", "91to180", "181to365", "365More")


def _liquidity_bucket_block(sub, tag: str, pattern: str, values: dict | None,
                            extra: tuple[str, Any] | None = None) -> Node | None:
    """A liquidity profile: optional as a block, all seven buckets mandatory
    once opened (CSSF controls CAF-128, CAF-129)."""
    from domain.aifmd.aifmd_engine import LIQUIDITY_BUCKETS
    values = values or {}
    has_any = any(not blank(values.get(key)) for key, _label in LIQUIDITY_BUCKETS)
    if extra is not None and not blank(extra[1]):
        has_any = True
    if not has_any:
        return None
    node = Node(tag)
    for (key, _label), suffix in zip(LIQUIDITY_BUCKETS, _BUCKET_TAGS):
        node.add(pattern.format(suffix), fmt_decimal(values.get(key), FX_DIGITS) or "0")
    if extra is not None:
        node.add(extra[0], _amount(extra[1]) or "0")
    return node


def _investor_redemption(sub) -> Node | None:
    if sub.provide_withdrawal_rights is None:
        return None
    node = Node("InvestorRedemption")
    node.add("ProvideWithdrawalRightsFlag", fmt_bool(sub.provide_withdrawal_rights))
    # The three redemption terms only apply when withdrawal rights exist
    # (CSSF controls CAF-130 to CAF-132).
    if sub.provide_withdrawal_rights:
        node.add_if("InvestorRedemptionFrequency", _text(sub.redemption_frequency))
        node.add_if("InvestorRedemptionNoticePeriod", fmt_integer(sub.redemption_notice_period_days))
        node.add_if("InvestorRedemptionLockUpPeriod", fmt_integer(sub.redemption_lockup_period_days))
    return node


def _investor_arrangement(sub) -> Node | None:
    illiquid_values = (sub.side_pocket_rate, sub.gates_rate, sub.dealing_suspension_rate,
                       sub.total_arrangement_rate, sub.other_arrangement_rate)
    has_illiquid = any(v is not None for v in illiquid_values) or bool(_text(sub.other_arrangement_type))
    has_preferential = sub.investor_preferential_treatment_flag is not None
    if not has_illiquid and not has_preferential:
        return None

    node = Node("InvestorArrangement")
    if has_illiquid:
        illiquid = node.add("InvestorIlliquidAssetArrangement")
        illiquid.add_if("SidePocketRate", _rate(sub.side_pocket_rate))
        illiquid.add_if("GatesRate", _rate(sub.gates_rate))
        illiquid.add_if("DealingSuspensionRate", _rate(sub.dealing_suspension_rate))
        if _text(sub.other_arrangement_type) and sub.other_arrangement_rate is not None:
            other = illiquid.add("OtherArrangement")
            other.add("OtherArrangementType", _text(sub.other_arrangement_type))
            other.add("OtherArrangementRate", _rate(sub.other_arrangement_rate) or "0")
        illiquid.add_if("TotalArrangementRate", _rate(sub.total_arrangement_rate))
    if has_preferential:
        preferential = node.add("InvestorPreferentialTreatment")
        preferential.add("InvestorPreferentialTreatmentFlag", fmt_bool(sub.investor_preferential_treatment_flag))
        # The four detail flags only apply when preferential treatment exists.
        if sub.investor_preferential_treatment_flag:
            for tag, value in (("DisclosureTermsPreferentialTreatmentFlag", sub.pref_disclosure_flag),
                               ("LiquidityTermsPreferentialTreatmentFlag", sub.pref_liquidity_flag),
                               ("FeeTermsPreferentialTreatmentFlag", sub.pref_fee_flag),
                               ("OtherTermsPreferentialTreatmentFlag", sub.pref_other_flag)):
                if value is not None:
                    preferential.add(tag, fmt_bool(value))
    return node


def _financing_liquidity(sub) -> Node | None:
    from domain.aifmd.aifmd_engine import LIQUIDITY_BUCKETS
    buckets = sub.financing_buckets or {}
    if sub.total_financing_amount is None and not any(
        not blank(buckets.get(key)) for key, _label in LIQUIDITY_BUCKETS
    ):
        return None
    node = Node("FinancingLiquidityProfile")
    node.add("TotalFinancingAmount", _amount(sub.total_financing_amount) or "0")
    for (key, _label), suffix in zip(LIQUIDITY_BUCKETS, _BUCKET_TAGS):
        node.add(f"TotalFinancingInDays{suffix}Rate", fmt_decimal(buckets.get(key), FX_DIGITS) or "0")
    return node


def _operational_risk(sub) -> Node | None:
    history = _historical_risk_profile(sub)
    if sub.total_open_positions is None and history is None:
        return None
    node = Node("OperationalRisk")
    node.add_if("TotalOpenPositions", _amount(sub.total_open_positions))
    if history is not None:
        node.append(history)
    return node


def _historical_risk_profile(sub) -> Node | None:
    """The four month-by-month series. Each is optional, and a month with
    nothing to report is simply omitted (CSSF controls CAF-134 to CAF-138)."""
    rows = {str(r.get("month")): r for r in (sub.historical_performance or []) if r.get("month")}
    if not rows:
        return None

    series = (
        ("GrossInvestmentReturnsRate", "gross_return", "Rate{}", _rate),
        ("NetInvestmentReturnsRate", "net_return", "Rate{}", _rate),
        ("NAVChangeRate", "nav_change", "Rate{}", _rate),
        ("Subscription", "subscriptions", "Quantity{}", _amount),
        ("Redemption", "redemptions", "Quantity{}", _amount),
    )
    node = Node("HistoricalRiskProfile")
    for tag, key, pattern, formatter in series:
        values = [(month, rows.get(month, {}).get(key)) for month in MONTH_TAGS]
        if not any(not blank(v) for _m, v in values):
            continue
        block = node.add(tag)
        for month, value in values:
            block.add_if(pattern.format(month), formatter(value))
    return node if len(node) else None


# --- AIFLeverageInfo (Articles 24(2) and 24(4)) ------------------------------

def _aif_leverage_info(sub) -> Node:
    node = Node("AIFLeverageInfo")

    article_24_2 = node.add("AIFLeverageArticle24-2")
    article_24_2.add("AllCounterpartyCollateralRehypothecationFlag", fmt_bool(sub.rehypothecation_flag))
    # The rehypothecated share is forbidden when the flag is false (CAF-139).
    if sub.rehypothecation_flag:
        article_24_2.add_if("AllCounterpartyCollateralRehypothecatedRate", _rate(sub.rehypothecation_rate))

    borrowing_values = (sub.unsecured_borrowing_amount, sub.secured_borrowing_prime_brokerage_amount,
                        sub.secured_borrowing_reverse_repo_amount, sub.secured_borrowing_other_amount)
    if any(v is not None for v in borrowing_values):
        borrowing = article_24_2.add("SecuritiesCashBorrowing")
        borrowing.add_if("UnsecuredBorrowingAmount", _amount(sub.unsecured_borrowing_amount))
        borrowing.add_if("SecuredBorrowingPrimeBrokerageAmount", _amount(sub.secured_borrowing_prime_brokerage_amount))
        borrowing.add_if("SecuredBorrowingReverseRepoAmount", _amount(sub.secured_borrowing_reverse_repo_amount))
        borrowing.add_if("SecuredBorrowingOtherAmount", _amount(sub.secured_borrowing_other_amount))

    if sub.exchange_traded_derivatives_exposure is not None or sub.otc_derivatives_amount is not None:
        instruments = article_24_2.add("FinancialInstrumentBorrowing")
        instruments.add_if("ExchangedTradedDerivativesExposureValue", _amount(sub.exchange_traded_derivatives_exposure))
        instruments.add_if("OTCDerivativesAmount", _amount(sub.otc_derivatives_amount))

    article_24_2.add_if("ShortPositionBorrowedSecuritiesValue", _amount(sub.short_position_borrowed_securities_value))

    structures = [r for r in (sub.controlled_structures or []) if _text(r.get("name"))]
    if structures:
        container = article_24_2.add("ControlledStructures")
        for row in structures:
            entry = container.add("ControlledStructure")
            _entity(entry, "ControlledStructureIdentification", row.get("name"), row.get("bic"), row.get("lei"))
            entry.add("ControlledStructureExposureValue", _amount(row.get("exposure_value")) or "0")

    leverage = article_24_2.add("LeverageAIF")
    leverage.add("GrossMethodRate", _rate(sub.gross_method_rate) or "0")
    leverage.add("CommitmentMethodRate", _rate(sub.commitment_method_rate) or "0")

    if content_needs_article_24_4(sub.aif_content_type):
        article_24_4 = node.add("AIFLeverageArticle24-4")
        for rank, row in enumerate(_ranked(sub.borrowing_sources, N_BORROWING_SOURCES), start=1):
            entry = article_24_4.add("BorrowingSource")
            entry.add("Ranking", str(rank))
            has_source = bool(_text(row.get("name")))
            entry.add("BorrowingSourceFlag", fmt_bool(has_source))
            if not has_source:
                continue
            _entity(entry, "SourceIdentification", row.get("name"), row.get("bic"), row.get("lei"))
            entry.add_if("LeverageAmount", _amount(row.get("leverage_amount")))
    return node
