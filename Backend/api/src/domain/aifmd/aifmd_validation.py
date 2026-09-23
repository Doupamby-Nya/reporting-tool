"""Business validation of an AIFMD Annex IV submission.

Every rule below is one of the controls the CSSF publishes in the "AIFM
Reporting — Technical Guidance" (bundled at
data/regulation/aifmd/CSSF_AIFM_Reporting_Technical_Guidance.pdf), and each
issue carries that control's own code so a preparer can look it up:

- ERR-xxx / FOR-xxx — the file itself (naming convention, one record per file,
  the XML corresponds to the file type in its name);
- FIL-009, CSSF-xxx — identification and content of the file;
- CAM-xxx — consistency controls on the AIFM file (Annex 1);
- CAF-xxx — consistency controls on the AIF file (Annex 2).

Controls the CSSF runs against its own register (does the AIFM exist, is the
sender linked to it, has this exact file already been sent) cannot be checked
here and are deliberately absent. Controls the schema already enforces are
also absent: those are caught by domain.aifmd.aifmd_xsd, against the real ESMA XSD,
rather than duplicated as Python.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from domain.shared.iso_codes import (
    EEA_COUNTRIES, ISO_3166_ALPHA2, ISO_4217, bic_format_ok, isin_checksum_ok, lei_checksum_ok,
    lei_format_ok,
)
from domain.shared.xml_common import ERROR, WARNING, Issue, as_date, blank, to_decimal

# Tolerance on a "should sum to 100%" control: the rates carry two decimals.
PCT_TOLERANCE = Decimal("0.01")
# CSSF controls CSSF-042 / CAF-204 accept 99-101% on the financing breakdown.
FINANCING_TOLERANCE = Decimal("1")


def _d(value: Any) -> Decimal | None:
    try:
        return to_decimal(value)
    except ValueError:
        return None


def _sum(values: Iterable[Any]) -> Decimal:
    total = Decimal(0)
    for v in values:
        d = _d(v)
        if d is not None:
            total += d
    return total


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


# =============================================================================
# Reporting period
# =============================================================================

# Allowed start and end dates for each reporting period type — CSSF controls
# CAM-002 / CAM-003 for the AIFM file and CAF-003 / CAF-004 for the AIF file.
PERIOD_BOUNDS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "Q1": ((1, 1), (3, 31)), "Q2": ((4, 1), (6, 30)), "Q3": ((7, 1), (9, 30)), "Q4": ((10, 1), (12, 31)),
    "H1": ((1, 1), (6, 30)), "H2": ((7, 1), (12, 31)),
    "X1": ((1, 1), (9, 30)), "X2": ((4, 1), (12, 31)),
    "Y1": ((1, 1), (12, 31)),
}

# Non-overlapping combinations a single AIFM may file in one year (CSSF-005).
VALID_PERIOD_COMBINATIONS = (
    ("Q1", "Q2", "Q3", "Q4"), ("Q1", "Q2", "H2"), ("Q1", "X2"),
    ("H1", "H2"), ("H1", "Q3", "Q4"), ("Y1",), ("X1", "Q4"),
)


def _check_period(issues: list[Issue], sub, prefix: str, last_flag: bool) -> None:
    period = _text(sub.reporting_period_type)
    start = as_date(sub.reporting_period_start)
    end = as_date(sub.reporting_period_end)
    year = int(sub.reporting_period_year)

    bounds = PERIOD_BOUNDS.get(period)
    if bounds is None:
        issues.append(Issue(ERROR, f"{prefix}-PERIOD",
                            f"Reporting period type {period!r} is not one of {', '.join(PERIOD_BOUNDS)}."))
        return
    (start_month, start_day), (end_month, end_day) = bounds

    if start is None:
        issues.append(Issue(ERROR, f"{prefix}-002" if prefix == "CAM" else "CAF-003",
                            "The reporting period start date is mandatory."))
    else:
        expected = date(start.year, start_month, start_day)
        if (start.month, start.day) != (start_month, start_day):
            issues.append(Issue(ERROR, "CAM-002" if prefix == "CAM" else "CAF-003",
                                f"For a {period} reporting period the start date must be {expected.isoformat()}, "
                                f"got {start.isoformat()}."))
    if end is None:
        issues.append(Issue(ERROR, "CAM-003" if prefix == "CAM" else "CAF-004",
                            "The reporting period end date is mandatory."))
    elif start is not None:
        limit = date(end.year, end_month, end_day)
        if last_flag:
            # A final report may stop early, but never after the period end.
            if end > limit:
                issues.append(Issue(ERROR, "CAM-003" if prefix == "CAM" else "CAF-004",
                                    f"For a {period} reporting period the end date must be on or before "
                                    f"{limit.isoformat()}, got {end.isoformat()}."))
        elif (end.month, end.day) != (end_month, end_day):
            issues.append(Issue(ERROR, "CAM-003" if prefix == "CAM" else "CAF-004",
                                f"For a {period} reporting period the end date must be {limit.isoformat()}, "
                                f"got {end.isoformat()}. A shorter period is only accepted on a last report."))
        if end < start:
            issues.append(Issue(ERROR, f"{prefix}-PERIOD", "The reporting period end date is before its start date."))

    if start is not None and end is not None and not (start.year == end.year == year):
        issues.append(Issue(ERROR, "CSSF-006",
                            f"The reporting period year ({year}) must match the year of the start date "
                            f"({start.year}) and of the end date ({end.year})."))


def _check_change_quarter(issues: list[Issue], frequency: Any, contents: Any, quarter: Any, code: str) -> None:
    """The change quarter is mandatory once a frequency or a contents change is
    reported, and forbidden otherwise (CSSF controls CAM-004 / CAF-006)."""
    has_change = bool(_text(frequency) or _text(contents))
    value = _text(quarter)
    if has_change and not value:
        issues.append(Issue(ERROR, code,
                            "The reporting-obligation change quarter is mandatory once a change of frequency or "
                            "of contents is reported."))
    elif not has_change and value:
        issues.append(Issue(WARNING, code,
                            "A reporting-obligation change quarter is reported without any change of frequency or "
                            "contents; it will not be included in the file."))
    if value and value not in ("Q1", "Q2", "Q3", "Q4"):
        issues.append(Issue(ERROR, code, f"The change quarter must be Q1, Q2, Q3 or Q4, got {value!r}."))


# =============================================================================
# Identifiers
# =============================================================================

def _check_identifier(issues: list[Issue], value: Any, label: str, code: str, *,
                      checker, level: str = ERROR, mandatory: bool = False) -> None:
    text = _text(value)
    if not text:
        if mandatory:
            issues.append(Issue(ERROR, code, f"{label} is mandatory."))
        return
    if not checker(text):
        issues.append(Issue(level, code, f"{label} {text!r} is not valid."))


def _check_lei(issues: list[Issue], value: Any, label: str, code: str) -> None:
    text = _text(value).upper()
    if not text:
        return
    if not lei_format_ok(text):
        issues.append(Issue(ERROR, code,
                            f"{label} must be 20 characters (18 alphanumeric + 2 check digits), got {text!r}."))
    elif not lei_checksum_ok(text):
        issues.append(Issue(ERROR, code, f"{label} {text!r} fails the ISO 17442 check digits."))


def _check_isin(issues: list[Issue], value: Any, label: str, code: str) -> None:
    text = _text(value).upper()
    if not text:
        return
    if len(text) != 12:
        issues.append(Issue(ERROR, code, f"{label} must be 12 characters, got {text!r}."))
    elif not isin_checksum_ok(text):
        issues.append(Issue(ERROR, code, f"{label} {text!r} fails the ISO 6166 check digit."))


def _check_bic(issues: list[Issue], value: Any, label: str, code: str) -> None:
    text = _text(value).upper()
    if text and not bic_format_ok(text):
        issues.append(Issue(ERROR, code,
                            f"{label} {text!r} is not a valid 11-character BIC (ISO 9362)."))


def _check_country(issues: list[Issue], value: Any, label: str, code: str, *, mandatory: bool = False) -> None:
    text = _text(value).upper()
    if not text:
        if mandatory:
            issues.append(Issue(ERROR, code, f"{label} is mandatory."))
        return
    if text not in ISO_3166_ALPHA2:
        issues.append(Issue(ERROR, code, f"{label} {text!r} is not an ISO 3166-1 alpha-2 country code."))


def _check_currency(issues: list[Issue], value: Any, label: str, code: str, *, mandatory: bool = False) -> None:
    text = _text(value).upper()
    if not text:
        if mandatory:
            issues.append(Issue(ERROR, code, f"{label} is mandatory."))
        return
    if text not in ISO_4217:
        issues.append(Issue(ERROR, code, f"{label} {text!r} is not an ISO 4217 currency code."))


# =============================================================================
# Ranked tables
# =============================================================================

def _check_ranking(issues: list[Issue], rows: Iterable[dict], label: str, count: int) -> None:
    """Ranks must be unique within a block (CSSF control CSSF-020)."""
    seen: set[int] = set()
    for row in rows or []:
        try:
            rank = int(row.get("ranking"))
        except (TypeError, ValueError):
            continue
        if rank in seen:
            issues.append(Issue(ERROR, "CSSF-020", f"{label}: rank {rank} is used more than once."))
        if not 1 <= rank <= count:
            issues.append(Issue(ERROR, "CSSF-020", f"{label}: rank {rank} is outside the range 1-{count}."))
        seen.add(rank)


def _check_rank_order(issues: list[Issue], rows: Iterable[dict], value_key: str, label: str, code: str) -> None:
    """A ranked table must be sorted by decreasing value — the first rank is the
    largest (CSSF controls CAM-012, CAM-014, CAF-055, CAF-062, CAF-072,
    CAF-083, CAF-118, CAF-124, CAF-127, CAF-146)."""
    ordered = []
    for row in rows or []:
        try:
            rank = int(row.get("ranking"))
        except (TypeError, ValueError):
            continue
        value = _d(row.get(value_key))
        if value is not None:
            ordered.append((rank, value))
    ordered.sort()
    for (rank_a, value_a), (rank_b, value_b) in zip(ordered, ordered[1:]):
        if value_b > value_a:
            issues.append(Issue(ERROR, code,
                                f"{label}: rank {rank_b} ({value_b}) is larger than rank {rank_a} ({value_a}); "
                                f"the ranks must be ordered from the largest value down."))
            break


# =============================================================================
# AIFM file (DATMAN)
# =============================================================================

def validate_aifm_file(sub) -> list[Issue]:
    """Controls on the AIFM-level file — Annex 1 of the CSSF guidance."""
    issues: list[Issue] = []

    if _text(sub.reporting_member_state).upper() != "LU":
        issues.append(Issue(ERROR, "FIL-009",
                            f"The reporting member state must be 'LU', got "
                            f"{_text(sub.reporting_member_state)!r}."))

    if not re.fullmatch(r"A\d{8}", _text(sub.aifm_national_code)):
        issues.append(Issue(ERROR, "CSSF-001",
                            f"The AIFM national code must be 'A' followed by 8 digits (e.g. A00000001), got "
                            f"{_text(sub.aifm_national_code)!r}. It must also match the AIFM code in the file name."))
    if not _text(sub.aifm_name):
        issues.append(Issue(ERROR, "CAM-NAME", "The AIFM name is mandatory."))

    content = _text(sub.aifm_content_type)
    reporting_code = int(sub.aifm_reporting_code)
    if content not in ("1", "2", "3"):
        issues.append(Issue(ERROR, "CSSF-003", f"The AIFM content type must be 1, 2 or 3, got {content!r}."))
    # CSSF-032: registered -> 1, authorised -> 2-5, Article 42 -> 6-9.
    expected = {"2": (1, 1), "1": (2, 5), "3": (6, 9)}.get(content)
    if expected and not expected[0] <= reporting_code <= expected[1]:
        issues.append(Issue(ERROR, "CSSF-032",
                            f"An AIFM reporting code of {reporting_code} is not consistent with the AIFM content "
                            f"type {content}: a registered AIFM reports code 1, an authorised AIFM codes 2 to 5, "
                            f"and an Article 42 AIFM codes 6 to 9."))

    _check_country(issues, sub.aifm_jurisdiction, "The AIFM jurisdiction", "CAM-005", mandatory=True)
    _check_lei(issues, sub.aifm_lei, "The AIFM LEI", "CAM-007")
    _check_bic(issues, sub.aifm_bic, "The AIFM BIC", "CAM-BIC")

    if _text(sub.aifm_old_identifier_country) or _text(sub.aifm_old_identifier_code):
        _check_country(issues, sub.aifm_old_identifier_country,
                       "The country of the former AIFM national code", "CAM-008", mandatory=True)
        if not _text(sub.aifm_old_identifier_code):
            issues.append(Issue(ERROR, "CAM-009",
                                "The former AIFM national code is mandatory once its reporting member state is filled in."))

    _check_period(issues, sub, "CAM", bool(sub.aifm_last_reporting_flag))
    _check_change_quarter(issues, sub.aifm_change_frequency_code, sub.aifm_change_contents_code,
                          sub.aifm_change_quarter, "CAM-004")

    if sub.aifm_no_reporting_flag:
        return issues

    _check_ranking(issues, sub.aifm_principal_markets, "AIFM principal markets", 5)
    _check_ranking(issues, sub.aifm_principal_instruments, "AIFM principal instruments", 5)
    _check_rank_order(issues, sub.aifm_principal_markets, "aggregated_value", "AIFM principal markets", "CAM-012")
    _check_rank_order(issues, sub.aifm_principal_instruments, "aggregated_value", "AIFM principal instruments", "CAM-014")

    for row in sub.aifm_principal_markets or []:
        code_type = _text(row.get("market_code_type"))
        rank = row.get("ranking")
        if code_type == "MIC" and not _text(row.get("market_code")):
            issues.append(Issue(ERROR, "CAM-010",
                                f"AIFM principal market rank {rank}: a MIC code is mandatory when the market code "
                                f"type is 'MIC'."))
        if code_type and code_type != "NOT" and blank(row.get("aggregated_value")):
            issues.append(Issue(ERROR, "CAM-011",
                                f"AIFM principal market rank {rank}: the aggregated value is mandatory for a market "
                                f"code type other than 'NOT'."))
    for row in sub.aifm_principal_instruments or []:
        sub_asset = _text(row.get("sub_asset_type"))
        if sub_asset and sub_asset != "NTA_NTA_NOTA" and blank(row.get("aggregated_value")):
            issues.append(Issue(ERROR, "CAM-013",
                                f"AIFM principal instrument rank {row.get('ranking')}: the aggregated value is "
                                f"mandatory for a reported sub-asset type."))

    base_currency = _text(sub.aifm_base_currency).upper()
    _check_currency(issues, base_currency, "The AIFM base currency", "CAM-017", mandatory=True)
    aum_base = _d(sub.total_aum_base_currency) or Decimal(0)
    aum_eur = _d(sub.total_aum_eur) or Decimal(0)
    if base_currency == "EUR":
        if aum_base != aum_eur:
            issues.append(Issue(ERROR, "CSSF-031",
                                f"With a EUR base currency the AUM in base currency ({aum_base}) must equal the AUM "
                                f"in euro ({aum_eur})."))
        if _text(sub.aifm_fx_ref_rate_type) or (_d(sub.eur_fx_rate) or Decimal(1)) != Decimal(1):
            issues.append(Issue(WARNING, "CAM-020",
                                "The FX reference rate only applies to a non-euro base currency; it will not be "
                                "included in the file."))
    else:
        rate = _d(sub.eur_fx_rate)
        if rate is None or rate == 0:
            issues.append(Issue(ERROR, "CAM-016",
                                "The EUR FX rate is mandatory and cannot be zero for a non-euro base currency."))
        else:
            converted = aum_base * rate
            if abs(converted - aum_eur) > max(Decimal(1), abs(converted) * Decimal("0.01")):
                issues.append(Issue(WARNING, "CAM-016",
                                    f"The AUM in euro ({aum_eur}) does not match the AUM in base currency "
                                    f"({aum_base}) converted at the reported rate ({rate}): {converted}."))
        rate_type = _text(sub.aifm_fx_ref_rate_type)
        if not rate_type:
            issues.append(Issue(ERROR, "CAM-020",
                                "The FX EUR reference rate type is mandatory for a non-euro base currency."))
        elif rate_type == "OTH" and not _text(sub.aifm_fx_ref_rate_description):
            issues.append(Issue(ERROR, "CAM-020",
                                "The reference rate description is mandatory when the reference rate type is 'OTH'."))
        elif rate_type == "ECB" and _text(sub.aifm_fx_ref_rate_description):
            issues.append(Issue(WARNING, "CAM-020",
                                "The reference rate description only applies to the 'OTH' rate type; it will not be "
                                "included in the file."))
    return issues


# =============================================================================
# AIF file (DATAIF)
# =============================================================================

def validate_aif_file(sub) -> list[Issue]:
    """Controls on the AIF-level file — Annex 2 of the CSSF guidance."""
    from domain.aifmd.aifmd_engine import (
        AIF_CONTENT_TYPES, ARTICLE_24_2_AND_24_4_CODES, ARTICLE_24_2_CODES, ASSET_MACRO_TYPES,
        GEO_REGIONS, INVESTOR_GROUP_TYPES, LIQUIDITY_BUCKETS, MANDATORY_RISK_MEASURE_TYPES,
        STRATEGY_GROUPS, SUB_ASSET_TYPE_LABELS,
    )
    from domain.aifmd.aifmd_xml import (
        content_needs_article_24_4, content_needs_individual_info, content_needs_leverage_info,
    )

    issues: list[Issue] = []

    if _text(sub.reporting_member_state).upper() != "LU":
        issues.append(Issue(ERROR, "FIL-009",
                            f"The reporting member state must be 'LU', got {_text(sub.reporting_member_state)!r}."))

    # --- identification ------------------------------------------------------
    if not re.fullmatch(r"A\d{8}", _text(sub.aifm_national_code)):
        issues.append(Issue(ERROR, "CSSF-001",
                            f"The AIFM national code must be 'A' followed by 8 digits, got "
                            f"{_text(sub.aifm_national_code)!r}."))
    if _text(sub.aif_legal_form) not in ("O", "K", "V"):
        issues.append(Issue(ERROR, "ERR-008",
                            f"The AIF legal form must be 'O' (Part II fund or SIF), 'K' (SICAR) or 'V' (other "
                            f"vehicle), got {_text(sub.aif_legal_form)!r}."))
    if not re.fullmatch(r"\d{8}", _text(sub.aif_national_number)):
        issues.append(Issue(ERROR, "ERR-008",
                            f"The AIF national number must be 8 digits, got {_text(sub.aif_national_number)!r}."))
    if not re.fullmatch(r"\d{8}", _text(sub.aif_subfund_number)):
        issues.append(Issue(ERROR, "CSSF-015",
                            f"The compartment/sub-fund number must be 8 digits ('00000000' when the fund has no "
                            f"compartment), got {_text(sub.aif_subfund_number)!r}."))
    if not _text(sub.aif_name):
        issues.append(Issue(ERROR, "CSSF-017", "The AIF name is mandatory."))

    _check_country(issues, sub.aif_domicile, "The AIF domicile", "CAF-010", mandatory=True)
    domicile = _text(sub.aif_domicile).upper()
    if domicile in ISO_3166_ALPHA2:
        in_eea = domicile in EEA_COUNTRIES
        if bool(sub.aif_eea_flag) != in_eea:
            issues.append(Issue(ERROR, "CAF-009",
                                f"The AIF EEA flag is {str(bool(sub.aif_eea_flag)).lower()} but the domicile "
                                f"{domicile} is {'in' if in_eea else 'outside'} the EEA."))

    inception = as_date(sub.aif_inception_date)
    start = as_date(sub.reporting_period_start)
    if inception is None:
        issues.append(Issue(ERROR, "FOR-009", "The AIF inception date is mandatory."))
    elif start is not None and inception > start:
        issues.append(Issue(ERROR, "CAF-011",
                            f"The inception date ({inception.isoformat()}) must not be after the reporting period "
                            f"start date ({start.isoformat()})."))

    content = _text(sub.aif_content_type)
    reporting_code = int(sub.aif_reporting_code)
    if content not in AIF_CONTENT_TYPES:
        issues.append(Issue(ERROR, "CAF-002",
                            f"The AIF content type must be one of {', '.join(AIF_CONTENT_TYPES)}, got {content!r}."))
    if not 1 <= reporting_code <= 45:
        issues.append(Issue(ERROR, "CSSF-034", f"The AIF reporting code must be between 1 and 45, got {reporting_code}."))
    else:
        # CSSF-034: registered -> 1, authorised -> 2-34, Article 42 -> 35-45.
        aifm_content = _text(sub.aifm_content_type)
        expected = {"2": (1, 1), "1": (2, 34), "3": (35, 45)}.get(aifm_content)
        if expected and not expected[0] <= reporting_code <= expected[1]:
            issues.append(Issue(ERROR, "CSSF-034",
                                f"An AIF reporting code of {reporting_code} is not consistent with the AIFM content "
                                f"type {aifm_content}: a registered AIFM's AIFs use code 1, an authorised AIFM's AIFs "
                                f"codes 2 to 34, and an Article 42 AIFM's AIFs codes 35 to 45."))
    # CSSF-046: the content type and the reporting code must agree on which
    # articles apply.
    if content in AIF_CONTENT_TYPES and 1 <= reporting_code <= 45:
        needs_24_2 = reporting_code in ARTICLE_24_2_CODES
        needs_24_4 = reporting_code in ARTICLE_24_2_AND_24_4_CODES
        declares_24_2 = content_needs_individual_info(content)
        declares_24_4 = content_needs_article_24_4(content)
        if needs_24_2 and not declares_24_2:
            issues.append(Issue(ERROR, "CSSF-046",
                                f"The AIF reporting code {reporting_code} is subject to Article 24(2), so the content "
                                f"type must be 2 or 4, not {content}."))
        if needs_24_4 and not declares_24_4:
            issues.append(Issue(ERROR, "CSSF-046",
                                f"The AIF reporting code {reporting_code} is subject to Article 24(4), so the content "
                                f"type must be 4 or 5, not {content}."))

    _check_period(issues, sub, "CAF", bool(sub.aif_last_reporting_flag))
    _check_change_quarter(issues, sub.aif_change_frequency_code, sub.aif_change_contents_code,
                          sub.aif_change_quarter, "CAF-006")

    if sub.aif_no_reporting_flag:
        # CAF-012: an empty report carries no description at all.
        return issues

    # --- identifiers ---------------------------------------------------------
    _check_lei(issues, sub.aif_lei, "The AIF LEI", "CAF-013")
    _check_isin(issues, sub.aif_isin, "The AIF ISIN", "CAF-014")
    if _text(sub.aif_old_identifier_country) or _text(sub.aif_old_identifier_code):
        _check_country(issues, sub.aif_old_identifier_country,
                       "The country of the former AIF national code", "CAF-015", mandatory=True)

    # CSSF-040: a fund trading derivatives must carry a LEI.
    if (sub.exchange_traded_derivatives_exposure is not None or sub.otc_derivatives_amount is not None) \
            and not _text(sub.aif_lei):
        issues.append(Issue(ERROR, "CSSF-040",
                            "The AIF LEI is mandatory once an exchange-traded or OTC derivatives exposure is "
                            "reported (the fund trades derivatives and is in scope of EMIR)."))

    # --- share classes -------------------------------------------------------
    classes = [r for r in (sub.aif_share_classes or [])
               if any(_text(r.get(k)) for k in ("name", "national_code", "isin", "sedol", "cusip", "bloomberg", "reuters"))]
    if sub.aif_share_class_flag:
        if not classes:
            issues.append(Issue(ERROR, "CAF-023",
                                "The share class flag is true, so at least one share class must be reported."))
        for index, row in enumerate(classes, start=1):
            if not _text(row.get("name")):
                issues.append(Issue(ERROR, "CAF-023", f"Share class {index}: the name is mandatory."))
            _check_isin(issues, row.get("isin"), f"Share class {index}: the ISIN", "CAF-017")
    elif classes:
        issues.append(Issue(WARNING, "CAF-016",
                            "Share class identifiers are only allowed when the share class flag is true; they will "
                            "not be included in the file."))

    # --- master / feeder -----------------------------------------------------
    status = _text(sub.aif_master_feeder_status) or "NONE"
    masters = [r for r in (sub.aif_master_aifs or []) if _text(r.get("name"))]
    if status == "FEEDER" and not masters:
        issues.append(Issue(ERROR, "CAF-024",
                            "A feeder AIF must identify at least one master AIF by name."))
    if status != "FEEDER" and masters:
        issues.append(Issue(WARNING, "CAF-024",
                            f"A master AIF identification is only allowed for a feeder AIF (the status is {status}); "
                            f"it will not be included in the file."))
    for index, row in enumerate(masters, start=1):
        if _text(row.get("country")):
            _check_country(issues, row.get("country"), f"Master AIF {index}: the reporting member state", "CAF-025")
            if not _text(row.get("national_code")):
                issues.append(Issue(ERROR, "CAF-027",
                                    f"Master AIF {index}: the national code is mandatory once its reporting member "
                                    f"state is filled in."))

    for index, row in enumerate(sub.aif_prime_brokers or [], start=1):
        if _text(row.get("lei")) or _text(row.get("bic")):
            if not _text(row.get("name")):
                issues.append(Issue(ERROR, "CAF-028",
                                    f"Prime broker {index}: an identifier cannot be reported without the entity name."))
        _check_lei(issues, row.get("lei"), f"Prime broker {index}: the LEI", "CAF-028")
        _check_bic(issues, row.get("bic"), f"Prime broker {index}: the BIC", "CAF-028")

    # --- currency and NAV ----------------------------------------------------
    base_currency = _text(sub.aif_base_currency).upper()
    _check_currency(issues, base_currency, "The AIF base currency", "CAF-029", mandatory=True)
    if base_currency != "EUR":
        rate = _d(sub.aif_fx_rate)
        if rate is None or rate == 0:
            issues.append(Issue(ERROR, "CSSF-035",
                                "The EUR FX rate is mandatory and cannot be zero for a non-euro base currency."))
        rate_type = _text(sub.aif_fx_ref_rate_type)
        if not rate_type:
            issues.append(Issue(ERROR, "CAF-031",
                                "The FX EUR reference rate type is mandatory for a non-euro base currency."))
        elif rate_type == "OTH" and not _text(sub.aif_fx_ref_rate_description):
            issues.append(Issue(ERROR, "CAF-032",
                                "The reference rate description is mandatory when the reference rate type is 'OTH'."))
    else:
        if _text(sub.aif_fx_ref_rate_type) or (_d(sub.aif_fx_rate) or Decimal(1)) != Decimal(1):
            issues.append(Issue(WARNING, "CAF-030",
                                "The FX rate and its reference type are forbidden for a EUR base currency; they will "
                                "not be included in the file."))

    aum = _d(sub.aif_aum_base_currency) or Decimal(0)
    nav = _d(sub.aif_nav) or Decimal(0)
    if aum == 0 or nav == 0:
        issues.append(Issue(ERROR, "CSSF-047",
                            "Neither the AUM in base currency nor the net asset value can be zero."))

    for value, label, code in ((sub.funding_source_country_1, "The first funding source country", "CAF-033"),
                               (sub.funding_source_country_2, "The second funding source country", "CAF-034"),
                               (sub.funding_source_country_3, "The third funding source country", "CAF-035")):
        _check_country(issues, value, label, code)

    # --- investment strategies ----------------------------------------------
    predominant = _text(sub.predominant_aif_type) or "NONE"
    strategies = [r for r in (sub.investment_strategies or []) if _text(r.get("code"))]
    if predominant == "NONE" and len(strategies) < 2:
        issues.append(Issue(ERROR, "CSSF-012",
                            "At least two investment strategies must be reported when the predominant AIF type is "
                            "'NONE'."))
    group_codes = {group: {code for code, _label in codes} for group, _title, codes in STRATEGY_GROUPS}
    for group, _title, _codes in STRATEGY_GROUPS:
        rows = [r for r in strategies if r.get("group") == group]
        if not rows:
            continue
        if predominant not in ("NONE", group):
            issues.append(Issue(ERROR, "CAF-036",
                                f"A {group} investment strategy is reported while the predominant AIF type is "
                                f"{predominant}."))
        for row in rows:
            if _text(row.get("code")) not in group_codes[group]:
                issues.append(Issue(ERROR, "CAF-037",
                                    f"{_text(row.get('code'))!r} is not a valid investment strategy code for the "
                                    f"{group} group."))
        primaries = [r for r in rows if r.get("primary_flag")]
        if len(primaries) > 1:
            issues.append(Issue(ERROR, "CSSF-024",
                                f"Only one primary investment strategy is allowed in the {group} group, got "
                                f"{len(primaries)}."))
        for row in rows:
            code = _text(row.get("code"))
            if code.startswith("MULT_") and not row.get("primary_flag"):
                issues.append(Issue(ERROR, "CAF-038",
                                    f"A multi-strategy code ({code}) must be flagged as the primary strategy."))
            if code.startswith("OTHR_") and not _text(row.get("other_description")):
                issues.append(Issue(ERROR, "CAF-041",
                                    f"A description is mandatory for the 'other' strategy code {code}."))
        rated = [r for r in rows if not _text(r.get("code")).startswith("MULT_")]
        if rated:
            total = _sum(r.get("nav_rate") for r in rated)
            if abs(total - 100) > PCT_TOLERANCE:
                issues.append(Issue(ERROR, "CAF-039",
                                    f"The {group} investment strategy NAV percentages must add up to 100%, got "
                                    f"{total}%."))

    # --- geographical focus --------------------------------------------------
    nav_focus = sub.nav_geo_focus or {}
    if any(not blank(nav_focus.get(key)) for key, _n, _a in GEO_REGIONS):
        total = _sum(nav_focus.get(key) for key, _n, _a in GEO_REGIONS)
        if abs(total - 100) > PCT_TOLERANCE:
            issues.append(Issue(ERROR, "CAF-057",
                                f"The NAV geographical focus percentages must add up to 100%, got {total}%."))
    else:
        issues.append(Issue(ERROR, "CAF-057",
                            "The NAV geographical focus is mandatory: the eight regional percentages must add up "
                            "to 100%."))
    aum_focus = sub.aum_geo_focus or {}
    if any(not blank(aum_focus.get(key)) for key, _n, _a in GEO_REGIONS):
        total = _sum(aum_focus.get(key) for key, _n, _a in GEO_REGIONS)
        if abs(total - 100) > PCT_TOLERANCE:
            issues.append(Issue(ERROR, "CAF-058",
                                f"The AUM geographical focus percentages must add up to 100%, got {total}%."))

    # --- ranked tables -------------------------------------------------------
    _check_ranking(issues, sub.main_instruments, "Main instruments traded", 5)
    _check_ranking(issues, sub.ten_principal_exposures, "Principal exposures", 10)
    _check_ranking(issues, sub.portfolio_concentrations, "Portfolio concentrations", 5)
    _check_ranking(issues, sub.aif_principal_markets, "AIF principal markets", 3)
    _check_ranking(issues, sub.counterparty_exposures_to_aif, "Counterparty exposures of the AIF", 5)
    _check_ranking(issues, sub.counterparty_exposures_from_aif, "Counterparty exposures to the AIF", 5)
    _check_ranking(issues, sub.ccp_exposures, "CCP exposures", 3)
    _check_ranking(issues, sub.borrowing_sources, "Borrowing sources", 5)

    _check_rank_order(issues, sub.main_instruments, "position_value", "Main instruments traded", "CAF-055")
    _check_rank_order(issues, sub.ten_principal_exposures, "aggregated_value", "Principal exposures", "CAF-062")
    _check_rank_order(issues, sub.portfolio_concentrations, "aggregated_value", "Portfolio concentrations", "CAF-072")
    _check_rank_order(issues, sub.aif_principal_markets, "aggregated_value", "AIF principal markets", "CAF-083")
    _check_rank_order(issues, sub.counterparty_exposures_to_aif, "nav_pct", "Counterparty exposures of the AIF", "CAF-118")
    _check_rank_order(issues, sub.counterparty_exposures_from_aif, "nav_pct", "Counterparty exposures to the AIF", "CAF-124")
    _check_rank_order(issues, sub.ccp_exposures, "exposure_value", "CCP exposures", "CAF-127")
    _check_rank_order(issues, sub.borrowing_sources, "leverage_amount", "Borrowing sources", "CAF-146")

    _check_main_instruments(issues, sub)
    _check_principal_exposures(issues, sub, ASSET_MACRO_TYPES, SUB_ASSET_TYPE_LABELS)
    _check_portfolio_concentrations(issues, sub)

    for row in sub.aif_principal_markets or []:
        code_type = _text(row.get("market_code_type"))
        if code_type == "MIC" and not _text(row.get("market_code")):
            issues.append(Issue(ERROR, "CAF-080",
                                f"AIF principal market rank {row.get('ranking')}: a MIC code is mandatory when the "
                                f"market code type is 'MIC'."))
        if code_type and code_type != "NOT" and blank(row.get("aggregated_value")):
            issues.append(Issue(ERROR, "CAF-082",
                                f"AIF principal market rank {row.get('ranking')}: the aggregated value is mandatory "
                                f"for a market code type other than 'NOT'."))

    # --- investor concentration ----------------------------------------------
    owners = _d(sub.investor_beneficial_owners_rate)
    if owners is None or owners == 0:
        issues.append(Issue(ERROR, "CSSF-021",
                            "The percentage of the NAV held by the five largest beneficial owners cannot be zero."))
    professional = _d(sub.investor_professional_rate) or Decimal(0)
    retail = _d(sub.investor_retail_rate) or Decimal(0)
    if abs(professional + retail - 100) > PCT_TOLERANCE and (professional + retail) != 0:
        issues.append(Issue(ERROR, "CAF-084",
                            f"The professional and retail investor percentages must add up to 0% or 100%, got "
                            f"{professional + retail}%."))

    # --- typical position size ------------------------------------------------
    if _text(sub.typical_position_size) and predominant != "PEQF":
        issues.append(Issue(WARNING, "CAF-079",
                            "The typical position size only applies to a private equity fund; it will not be "
                            "included in the file."))
    if predominant == "PEQF" and not _text(sub.typical_position_size):
        issues.append(Issue(ERROR, "CAF-079",
                            "The typical position size is mandatory for a private equity fund."))

    if content_needs_individual_info(content):
        issues += _validate_article_24_2(sub, reporting_code, predominant,
                                         INVESTOR_GROUP_TYPES, LIQUIDITY_BUCKETS,
                                         MANDATORY_RISK_MEASURE_TYPES, ARTICLE_24_2_CODES)
    if content_needs_leverage_info(content):
        issues += _validate_leverage(sub, reporting_code, ARTICLE_24_2_AND_24_4_CODES,
                                     content_needs_article_24_4(content))
    return issues


def _check_main_instruments(issues: list[Issue], sub) -> None:
    for row in sub.main_instruments or []:
        rank = row.get("ranking")
        sub_asset = _text(row.get("sub_asset_type"))
        if not sub_asset or sub_asset == "NTA_NTA_NOTA":
            continue
        where = f"Main instrument traded rank {rank}"
        code_type = _text(row.get("instrument_code_type"))
        if not code_type:
            issues.append(Issue(ERROR, "CAF-042", f"{where}: the instrument code type is mandatory."))
        if not _text(row.get("instrument_name")):
            issues.append(Issue(ERROR, "CAF-043", f"{where}: the instrument name is mandatory."))
        if code_type == "ISIN":
            if not _text(row.get("isin")):
                issues.append(Issue(ERROR, "CAF-045", f"{where}: the ISIN is mandatory for the code type 'ISIN'."))
            _check_isin(issues, row.get("isin"), f"{where}: the ISIN", "CAF-044")
        elif code_type == "AII":
            for key, label, code in (("aii_exchange_code", "the AII exchange code (MIC)", "CAF-047"),
                                     ("aii_product_code", "the AII product code", "CAF-048"),
                                     ("aii_derivative_type", "the AII derivative type", "CAF-049"),
                                     ("aii_expiry_date", "the AII expiry date", "CAF-051")):
                if blank(row.get(key)):
                    issues.append(Issue(ERROR, code, f"{where}: {label} is mandatory for the code type 'AII'."))
            expiry = as_date(row.get("aii_expiry_date"))
            if expiry is not None and expiry <= date(2010, 1, 1):
                issues.append(Issue(ERROR, "CSSF-016",
                                    f"{where}: the AII expiry date must be after 2010-01-01, got {expiry.isoformat()}."))
            if _text(row.get("aii_derivative_type")) == "O" and _text(row.get("aii_put_call")) not in ("P", "C"):
                issues.append(Issue(ERROR, "CAF-050",
                                    f"{where}: an option must be identified as a put ('P') or a call ('C')."))
        if blank(row.get("position_value")):
            issues.append(Issue(ERROR, "CAF-054", f"{where}: the position value is mandatory."))
        position_type = _text(row.get("position_type"))
        if position_type not in ("L", "S"):
            issues.append(Issue(ERROR, "CAF-053", f"{where}: the position type must be 'L' or 'S'."))
        if position_type != "S" and not blank(row.get("hedging_rate")):
            issues.append(Issue(WARNING, "CAF-056",
                                f"{where}: the short-position hedging rate only applies to a short position; it will "
                                f"not be included in the file."))


def _check_principal_exposures(issues: list[Issue], sub, macro_types, sub_asset_labels) -> None:
    for row in sub.ten_principal_exposures or []:
        macro = _text(row.get("macro_type"))
        if not macro or macro == "NTA":
            continue
        where = f"Principal exposure rank {row.get('ranking')}"
        if macro not in macro_types:
            issues.append(Issue(ERROR, "CAF-059", f"{where}: {macro!r} is not an asset macro type."))
        sub_asset = _text(row.get("sub_asset_type"))
        if sub_asset and not sub_asset.startswith(macro):
            issues.append(Issue(ERROR, "CAF-059",
                                f"{where}: the sub-asset type {sub_asset!r} does not belong to the macro type {macro!r}."))
        if sub_asset and sub_asset not in sub_asset_labels:
            issues.append(Issue(ERROR, "CAF-059", f"{where}: {sub_asset!r} is not a valid sub-asset type."))
        if _text(row.get("position_type")) not in ("L", "S"):
            issues.append(Issue(ERROR, "CAF-060", f"{where}: the position type must be 'L' or 'S'."))
        if blank(row.get("aggregated_value")):
            issues.append(Issue(ERROR, "CAF-061", f"{where}: the aggregated value is mandatory."))
        if blank(row.get("aggregated_value_pct")):
            issues.append(Issue(ERROR, "CAF-063", f"{where}: the aggregated value percentage is mandatory."))
        if (_text(row.get("counterparty_lei")) or _text(row.get("counterparty_bic"))) \
                and not _text(row.get("counterparty_name")):
            issues.append(Issue(ERROR, "CAF-064",
                                f"{where}: a counterparty identifier cannot be reported without the counterparty name."))
        _check_lei(issues, row.get("counterparty_lei"), f"{where}: the counterparty LEI", "CAF-065")
        _check_bic(issues, row.get("counterparty_bic"), f"{where}: the counterparty BIC", "CAF-066")


def _check_portfolio_concentrations(issues: list[Issue], sub) -> None:
    for row in sub.portfolio_concentrations or []:
        asset_type = _text(row.get("asset_type"))
        if not asset_type or asset_type == "NTA_NTA":
            continue
        where = f"Portfolio concentration rank {row.get('ranking')}"
        if _text(row.get("position_type")) not in ("L", "S"):
            issues.append(Issue(ERROR, "CAF-067", f"{where}: the position type must be 'L' or 'S'."))
        code_type = _text(row.get("market_code_type"))
        if not code_type:
            issues.append(Issue(ERROR, "CAF-068", f"{where}: the market code type is mandatory."))
        elif code_type not in ("MIC", "OTC", "XXX"):
            issues.append(Issue(ERROR, "CAF-068",
                                f"{where}: the market code type must be 'MIC', 'OTC' or 'XXX', got {code_type!r}."))
        if code_type == "MIC" and not _text(row.get("market_code")):
            issues.append(Issue(ERROR, "CAF-069", f"{where}: a MIC code is mandatory for the market code type 'MIC'."))
        if code_type != "MIC" and _text(row.get("market_code")):
            issues.append(Issue(WARNING, "CAF-070",
                                f"{where}: a MIC code is only allowed for the market code type 'MIC'; it will not be "
                                f"included in the file."))
        if blank(row.get("aggregated_value")):
            issues.append(Issue(ERROR, "CAF-071", f"{where}: the aggregated value is mandatory."))
        if blank(row.get("aggregated_value_pct")):
            issues.append(Issue(ERROR, "CAF-073", f"{where}: the aggregated value percentage is mandatory."))
        if _text(row.get("counterparty_name")) and code_type != "OTC":
            issues.append(Issue(WARNING, "CAF-074",
                                f"{where}: a counterparty is only allowed for an OTC market; it will not be included "
                                f"in the file."))
        _check_lei(issues, row.get("counterparty_lei"), f"{where}: the counterparty LEI", "CAF-076")
        _check_bic(issues, row.get("counterparty_bic"), f"{where}: the counterparty BIC", "CAF-077")


# =============================================================================
# Article 24(2)
# =============================================================================

def _validate_article_24_2(sub, reporting_code, predominant, investor_group_types,
                           liquidity_buckets, mandatory_risk_measures, article_24_2_codes) -> list[Issue]:
    issues: list[Issue] = []

    exposures = [r for r in (sub.instrument_exposures or [])
                 if _text(r.get("code"))
                 and any(not blank(r.get(k)) for k in ("gross_value", "long_value", "short_value"))]
    if not exposures:
        issues.append(Issue(ERROR, "CAF-085",
                            "At least one individual exposure by sub-asset type must be reported under "
                            "Article 24(2)."))
    for row in exposures:
        code = _text(row.get("code"))
        if code == "NTA_NTA_NOTA":
            issues.append(Issue(ERROR, "CSSF-022",
                                "The sub-asset type 'NTA_NTA_NOTA' is forbidden in the individual exposures."))
        gross_only = code in ("DER_FEX_INVT", "DER_FEX_HEDG", "DER_IRD_INTR")
        if gross_only and blank(row.get("gross_value")):
            issues.append(Issue(ERROR, "CAF-085",
                                f"Individual exposure {code}: a gross value is mandatory for an FX or interest-rate "
                                f"derivative."))
        if not gross_only and blank(row.get("long_value")) and blank(row.get("short_value")):
            issues.append(Issue(ERROR, "CAF-086",
                                f"Individual exposure {code}: a long or a short value must be reported."))
        if not gross_only and not blank(row.get("gross_value")):
            issues.append(Issue(WARNING, "CAF-085",
                                f"Individual exposure {code}: a gross value only applies to an FX or interest-rate "
                                f"derivative; it will not be included in the file."))

    turnovers = [r for r in (sub.asset_turnovers or [])
                 if _text(r.get("code")) and any(not blank(r.get(k)) for k in ("market_value", "notional_value"))]
    if not turnovers:
        issues.append(Issue(ERROR, "CAF-088",
                            "At least one turnover by sub-asset type must be reported under Article 24(2)."))

    seen_currencies: set[str] = set()
    for row in sub.currency_exposures or []:
        currency = _text(row.get("currency")).upper()
        if not currency:
            continue
        _check_currency(issues, currency, "The currency of exposure", "CAF-089")
        if currency in seen_currencies:
            issues.append(Issue(ERROR, "CSSF-033",
                                f"Currency {currency} is reported more than once; one long and one short position "
                                f"are expected per currency."))
        seen_currencies.add(currency)

    companies = [r for r in (sub.dominant_influence_companies or []) if _text(r.get("name"))]
    if companies and predominant != "PEQF":
        issues.append(Issue(WARNING, "CAF-092",
                            "Companies in which the AIF has a dominant influence are only reported by a private "
                            "equity fund; they will not be included in the file."))
    for index, row in enumerate(companies, start=1):
        _check_lei(issues, row.get("lei"), f"Dominant influence company {index}: the LEI", "CAF-093")
        _check_bic(issues, row.get("bic"), f"Dominant influence company {index}: the BIC", "CAF-095")
        if _text(row.get("transaction_type")) == "OTHR" and not _text(row.get("other_description")):
            issues.append(Issue(ERROR, "CAF-097",
                                f"Dominant influence company {index}: a description is mandatory for the transaction "
                                f"type 'OTHR'."))

    # --- risk profile --------------------------------------------------------
    annual = _text(sub.annual_investment_return_rate)
    if not annual:
        issues.append(Issue(ERROR, "CAF-137",
                            "The annual investment return rate is mandatory under Article 24(2); report 'NA' when "
                            "it is not available."))
    elif annual.upper() != "NA" and _d(annual) is None:
        issues.append(Issue(ERROR, "CAF-137",
                            f"The annual investment return rate must be a percentage or 'NA', got {annual!r}."))

    measures = {_text(r.get("code")): r for r in (sub.market_risk_measures or []) if _text(r.get("code"))}
    for code in mandatory_risk_measures:
        row = measures.get(code)
        has_value = row is not None and any(
            not blank(row.get(k)) for k in
            ("value", "bucket_lt5", "bucket_5_15", "bucket_gt15", "vega_current", "vega_lower10",
             "vega_higher10", "var_value", "var_method"))
        if not has_value:
            issues.append(Issue(ERROR, "CAF-216",
                                f"The market risk measure {code} is mandatory under Article 24(2)."))
    for code, row in measures.items():
        if code in ("NET_DV01", "NET_CS01"):
            if not blank(row.get("value")):
                issues.append(Issue(WARNING, "CAF-100",
                                    f"{code} is reported by maturity bucket; the single risk measure value will not "
                                    f"be included in the file."))
        elif code == "VEGA_EXPO":
            if not blank(row.get("value")):
                issues.append(Issue(WARNING, "CAF-103",
                                    "VEGA_EXPO is reported as three vega values; the single risk measure value will "
                                    "not be included in the file."))
        elif code == "VAR":
            if _text(row.get("var_method")) and _text(row.get("var_method")) not in ("HISTO", "CARLO", "PARAM"):
                issues.append(Issue(ERROR, "CAF-107",
                                    f"The VAR calculation method must be HISTO, CARLO or PARAM, got "
                                    f"{_text(row.get('var_method'))!r}."))
        elif not blank(row.get("bucket_lt5")) or not blank(row.get("vega_current")) or not blank(row.get("var_value")):
            issues.append(Issue(WARNING, "CAF-099",
                                f"{code} is reported as a single value; the bucket, vega and VAR values will not be "
                                f"included in the file."))

    # --- clearing percentages ------------------------------------------------
    _check_pair_100(issues, "CAF-109", "Traded securities",
                    sub.trading_pct_securities_exchange, sub.trading_pct_securities_otc)
    _check_pair_100(issues, "CAF-111", "Traded derivatives",
                    sub.trading_pct_derivatives_exchange, sub.trading_pct_derivatives_otc)
    _check_pair_100(issues, "WAF-001", "Cleared derivatives",
                    sub.derivatives_ccp_rate, sub.derivatives_bilateral_rate)
    if any(v is not None for v in (sub.repo_ccp_rate, sub.repo_bilateral_rate, sub.repo_triparty_rate)):
        total = _sum((sub.repo_ccp_rate, sub.repo_bilateral_rate, sub.repo_triparty_rate))
        if abs(total - 100) > PCT_TOLERANCE:
            issues.append(Issue(ERROR, "WAF-002",
                                f"The cleared repo percentages (CCP, bilateral and tri-party) must add up to 100%, "
                                f"got {total}%."))

    for index, row in enumerate(sub.counterparty_exposures_to_aif or [], start=1):
        _check_counterparty_row(issues, row, f"Counterparty exposure of the AIF rank {row.get('ranking', index)}",
                                "CAF-113", "CAF-114", "CAF-117")
    for index, row in enumerate(sub.counterparty_exposures_from_aif or [], start=1):
        _check_counterparty_row(issues, row, f"Counterparty exposure to the AIF rank {row.get('ranking', index)}",
                                "CAF-119", "CAF-120", "CAF-123")

    if sub.ccp_clearing_flag and not [r for r in (sub.ccp_exposures or []) if _text(r.get("name"))]:
        issues.append(Issue(ERROR, "CAF-125",
                            "At least the first CCP exposure must be reported when transactions are cleared through "
                            "a central counterparty."))
    for index, row in enumerate(sub.ccp_exposures or [], start=1):
        _check_lei(issues, row.get("lei"), f"CCP exposure {index}: the LEI", "CAF-126")

    # --- liquidity -----------------------------------------------------------
    _check_buckets_100(issues, "CAF-128", "The portfolio liquidity profile", sub.portfolio_liquidity, liquidity_buckets)
    _check_buckets_100(issues, "CAF-129", "The investor liquidity profile", sub.investor_liquidity, liquidity_buckets)

    if reporting_code in article_24_2_codes:
        if sub.unencumbered_cash is None:
            issues.append(Issue(ERROR, "CAF-206",
                                "The unencumbered cash amount is mandatory under Article 24(2)."))
        if sub.provide_withdrawal_rights is None:
            issues.append(Issue(ERROR, "CAF-207",
                                "The 'provides investors with withdrawal rights' flag is mandatory under "
                                "Article 24(2)."))

    if sub.provide_withdrawal_rights is False:
        for value, label, code in ((sub.redemption_frequency, "the investor redemption frequency", "CAF-130"),
                                   (sub.redemption_notice_period_days, "the redemption notice period", "CAF-131"),
                                   (sub.redemption_lockup_period_days, "the redemption lock-up period", "CAF-132")):
            if not blank(value):
                issues.append(Issue(WARNING, code,
                                    f"The AIF provides no withdrawal rights, so {label} will not be included in the "
                                    f"file."))

    groups = [r for r in (sub.investor_groups or []) if _text(r.get("code")) and not blank(r.get("rate"))]
    if groups:
        seen: set[str] = set()
        for row in groups:
            code = _text(row.get("code"))
            if code not in investor_group_types:
                issues.append(Issue(ERROR, "CSSF-023", f"{code!r} is not a valid investor group type."))
            if code in seen:
                issues.append(Issue(ERROR, "CSSF-023",
                                    f"The investor group {code} is reported more than once; only one percentage per "
                                    f"group is allowed."))
            seen.add(code)
        total = _sum(r.get("rate") for r in groups)
        if abs(total - 100) > PCT_TOLERANCE:
            issues.append(Issue(ERROR, "CSSF-023",
                                f"The investor group percentages must add up to 100%, got {total}%."))
    else:
        issues.append(Issue(ERROR, "CSSF-023",
                            "The breakdown of the NAV by investor group is mandatory under Article 24(2)."))

    buckets = sub.financing_buckets or {}
    if sub.total_financing_amount is not None or any(not blank(buckets.get(k)) for k, _l in liquidity_buckets):
        total = _sum(buckets.get(key) for key, _label in liquidity_buckets)
        if abs(total - 100) > FINANCING_TOLERANCE:
            issues.append(Issue(ERROR, "CAF-204",
                                f"The financing liquidity percentages must add up to between 99% and 101%, got "
                                f"{total}%."))
        elif abs(total - 100) > PCT_TOLERANCE:
            issues.append(Issue(WARNING, "CSSF-042",
                                f"The financing liquidity percentages add up to {total}% rather than exactly 100%."))

    if not _text(sub.stress_test_article15):
        issues.append(Issue(WARNING, "CAF-STRESS15",
                            "No Article 15 stress-test result is reported; an empty narrative will be sent."))
    if not _text(sub.stress_test_article16):
        issues.append(Issue(WARNING, "CAF-STRESS16",
                            "No Article 16 stress-test result is reported; an empty narrative will be sent."))
    return issues


def _check_counterparty_row(issues: list[Issue], row: dict, where: str,
                            name_code: str, lei_code: str, rate_code: str) -> None:
    has_name = bool(_text(row.get("name")))
    if not has_name:
        if _text(row.get("lei")) or _text(row.get("bic")) or not blank(row.get("nav_pct")):
            issues.append(Issue(WARNING, name_code,
                                f"{where}: an identifier or an exposure rate is reported without a counterparty "
                                f"name; it will not be included in the file."))
        return
    _check_lei(issues, row.get("lei"), f"{where}: the LEI", lei_code)
    _check_bic(issues, row.get("bic"), f"{where}: the BIC", lei_code)
    if blank(row.get("nav_pct")):
        issues.append(Issue(ERROR, rate_code,
                            f"{where}: the percentage of the NAV is mandatory once a counterparty is reported."))


def _check_pair_100(issues: list[Issue], code: str, label: str, first: Any, second: Any) -> None:
    if first is None and second is None:
        return
    total = _sum((first, second))
    if abs(total - 100) > PCT_TOLERANCE:
        issues.append(Issue(ERROR, code, f"{label}: the two percentages must add up to 100%, got {total}%."))


def _check_buckets_100(issues: list[Issue], code: str, label: str, values: dict | None, buckets) -> None:
    values = values or {}
    if not any(not blank(values.get(key)) for key, _label in buckets):
        return
    total = _sum(values.get(key) for key, _label in buckets)
    if abs(total - 100) > PCT_TOLERANCE:
        issues.append(Issue(ERROR, code, f"{label}: the seven percentages must add up to 100%, got {total}%."))


# =============================================================================
# Articles 24(2) and 24(4) — leverage
# =============================================================================

def _validate_leverage(sub, reporting_code, article_24_2_and_24_4_codes, needs_24_4) -> list[Issue]:
    issues: list[Issue] = []

    if sub.rehypothecation_flag is None:
        issues.append(Issue(ERROR, "CAF-139",
                            "The collateral rehypothecation flag is mandatory under Article 24(2)."))
    elif sub.rehypothecation_flag and sub.rehypothecation_rate is None:
        issues.append(Issue(ERROR, "CAF-139",
                            "The rehypothecated share of the collateral is mandatory once the rehypothecation flag "
                            "is true."))
    elif not sub.rehypothecation_flag and sub.rehypothecation_rate is not None:
        issues.append(Issue(WARNING, "CAF-139",
                            "The rehypothecated share is forbidden when the rehypothecation flag is false; it will "
                            "not be included in the file."))

    if reporting_code in article_24_2_and_24_4_codes:
        for value, label, code in (
            (sub.unsecured_borrowing_amount, "The unsecured borrowing amount", "CAF-208"),
            (sub.secured_borrowing_prime_brokerage_amount, "The secured borrowing via prime brokerage", "CAF-209"),
            (sub.secured_borrowing_reverse_repo_amount, "The secured borrowing via reverse repo", "CAF-210"),
            (sub.secured_borrowing_other_amount, "The secured borrowing via other means", "CAF-211"),
            (sub.short_position_borrowed_securities_value, "The value of securities borrowed for short positions", "CAF-212"),
        ):
            if value is None:
                issues.append(Issue(ERROR, code, f"{label} is mandatory under Articles 24(2) and 24(4)."))

    if sub.gross_method_rate is None or sub.commitment_method_rate is None:
        issues.append(Issue(ERROR, "CSSF-045",
                            "The gross-method and commitment-method leverage rates are both mandatory for this "
                            "content type."))

    for index, row in enumerate(sub.controlled_structures or [], start=1):
        if _text(row.get("name")):
            _check_lei(issues, row.get("lei"), f"Controlled structure {index}: the LEI", "CAF-140")
            if blank(row.get("exposure_value")):
                issues.append(Issue(ERROR, "CAF-140",
                                    f"Controlled structure {index}: the exposure value is mandatory."))

    if needs_24_4:
        sources = [r for r in (sub.borrowing_sources or []) if _text(r.get("name"))]
        if not sources:
            issues.append(Issue(ERROR, "CAF-141",
                                "At least one of the five largest sources of borrowed cash or securities must be "
                                "reported under Article 24(4)."))
        for row in sources:
            where = f"Borrowing source rank {row.get('ranking')}"
            _check_lei(issues, row.get("lei"), f"{where}: the LEI", "CAF-142")
            _check_bic(issues, row.get("bic"), f"{where}: the BIC", "CAF-144")
            if blank(row.get("leverage_amount")):
                issues.append(Issue(ERROR, "CAF-145",
                                    f"{where}: the leverage amount is mandatory once a source is reported."))
    return issues


# =============================================================================
# Whole submission
# =============================================================================

def validation_issues(sub) -> list[Issue]:
    """Every control, both files, in reporting order."""
    return validate_aifm_file(sub) + validate_aif_file(sub)
