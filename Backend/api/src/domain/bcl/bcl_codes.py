"""BCL code lists and code-level checks shared by every BCL report.

Sources (all bundled in this project, see BCL/ and data/regulation/bcl/):
- "Types of breakdowns" section of each report's instructions PDF
  (S0103_L4_S0213_L2_instructions_2025_EN.pdf §2) for the country, currency,
  economic-sector and initial-maturity code lists;
- TPTOBS_L3_instructions_2025_EN.pdf §4 for the security-level enumerations
  (identifier code type, type of holding, ESA 2010 security type, coupon type
  and coupon frequency);
- S0220_L0_instructions_2025_EN.pdf §2.4 / §3 for the institution types and
  the S 2.20 enumerations;
- the XSD datatypes files for the exact lexical patterns.
"""

from __future__ import annotations

import re

from domain.shared.iso_codes import (  # noqa: F401  (re-exported: the BCL modules import these from here)
    ISIN_EXTRA_PREFIXES, ISIN_FORBIDDEN_PREFIXES, ISO_3166_ALPHA2, ISO_4217, NO_LEI,
    is_valid_isin, isin_checksum_ok, isin_prefix_ok, lei_checksum_ok, lei_format_ok,
)

# =============================================================================
# Country
# =============================================================================

NO_BREAKDOWN_COUNTRY = "XX"
NO_BREAKDOWN_CURRENCY = "XXX"
NO_BREAKDOWN_SECTOR = "90000"
NO_BREAKDOWN_MATURITY = "I999-999"

NO_BREAKDOWN = {
    "country": NO_BREAKDOWN_COUNTRY,
    "currency": NO_BREAKDOWN_CURRENCY,
    "sector": NO_BREAKDOWN_SECTOR,
    "maturity": NO_BREAKDOWN_MATURITY,
}


# BCL codes for supranational/international institutions, usable wherever an
# ISO country code is expected (instructions §2.1). "XX" (no breakdown) is
# accepted only on the items whose chart of accounts says so.
BCL_SPECIAL_COUNTRY_CODES: dict[str, str] = {
    "XA": "European Central Bank",
    "XB": "International institutions, except European institutions, located outside Luxembourg",
    "XC": "International institutions, except European institutions, located in Luxembourg",
    "XD": "European institutions located in Luxembourg",
    "XE": "European Investment Bank",
    "XG": "European institutions located outside Luxembourg",
    "XH": "Bank for International Settlements",
    "XI": "European Stability Mechanism",
    "XJ": "European Financial Stability Facility",
    "XN": "Single Resolution Board",
    "XX": "No breakdown",
}

# Sector 12100 "State government" is only meaningful for countries with a
# federal structure (VER S 1.3/S 2.13 §2.1.1, TPTOBS VER rule 28). BCL's own
# list ("Types of breakdowns: List of countries that have a federal structure")
# is not bundled here, so this is used for a warning, never to block.
FEDERAL_COUNTRIES: frozenset[str] = frozenset(
    "AE AR AT AU BA BE BR CA CH CM DE ET IN IQ KM MX MY NG NP PK RU SD SS US VE".split()
)


def is_valid_country(code: str, *, allow_no_breakdown: bool = True) -> bool:
    code = (code or "").strip().upper()
    if code in ISO_3166_ALPHA2:
        return True
    if code == NO_BREAKDOWN_COUNTRY:
        return allow_no_breakdown
    return code in BCL_SPECIAL_COUNTRY_CODES


def country_label(code: str) -> str:
    return BCL_SPECIAL_COUNTRY_CODES.get((code or "").strip().upper(), "")


# =============================================================================
# Currency
# =============================================================================



def is_valid_currency(code: str, *, allow_no_breakdown: bool = True) -> bool:
    code = (code or "").strip().upper()
    if code in ISO_4217:
        return True
    if code == NO_BREAKDOWN_CURRENCY:
        return allow_no_breakdown
    # The XSD also accepts XX<A-Z0-9> for BCL-specific currency codes.
    return bool(re.fullmatch(r"XX[A-Z0-9]", code))


# =============================================================================
# Economic sector (BCL 2015)
# =============================================================================

BCL_SECTOR_CODES: dict[str, str] = {
    "11000": "Central government",
    "12100": "State government",
    "12200": "Local government",
    "12300": "Social security funds",
    "21000": "Non-financial corporations",
    "22110": "Households - Employers and own-account workers",
    "22120": "Households - Physical persons",
    "22200": "Non-profit institutions serving households",
    "31000": "Central bank",
    "32100": "Credit institutions",
    "32200": "Other deposit taking corporations",
    "33000": "Money market funds (MMF)",
    "41000": "Non MMF investment funds",
    "42100": "Securitisation vehicles",
    "42200": "Central counterparties",
    "42900": "Other financial intermediaries",
    "43000": "Financial auxiliaries",
    "44000": "Captive financial institutions and money lenders",
    "45000": "Insurance corporations",
    "46000": "Pension funds",
    "90000": "No breakdown",
}

# Sectors accepted where "no breakdown" is forbidden (TPTOBS issuer sector).
REAL_SECTOR_CODES: dict[str, str] = {k: v for k, v in BCL_SECTOR_CODES.items() if k != NO_BREAKDOWN_SECTOR}

FUND_SECTORS = ("33000", "41000")  # MMF / non-MMF investment funds


def is_valid_sector(code: str, *, allow_no_breakdown: bool = True) -> bool:
    code = (code or "").strip()
    if code == NO_BREAKDOWN_SECTOR:
        return allow_no_breakdown
    return code in REAL_SECTOR_CODES


# =============================================================================
# Initial maturity (BCL 2015)
# =============================================================================

BCL_MATURITY_CODES: dict[str, str] = {
    "I000-01A": "Up to 1 year",
    "I01A-02A": "Over 1 and up to 2 years",
    "I02A-05A": "Over 2 and up to 5 years",
    "I05A-999": "Over 5 years",
    "I999-999": "No breakdown",
}


def is_valid_maturity(code: str, *, allow_no_breakdown: bool = True) -> bool:
    code = (code or "").strip()
    if code == NO_BREAKDOWN_MATURITY:
        return allow_no_breakdown
    return code in BCL_MATURITY_CODES


# =============================================================================
# TPTOBS security-level enumerations
# =============================================================================

SECURITY_CODE_TYPES: dict[str, str] = {
    "1": "Securities with ISIN code",
    "2": "Securities without ISIN code",
}

HOLD_SECURITY_TYPES: dict[str, str] = {
    "01": "Securities held and not affected by a temporary transfer",
    "02": "Securities lent",
    "03": "Securities sold in a repurchase agreement",
    "04": "Securities issued",
    "05": "Short sale of securities",
}

# Per-item restriction — TPTOBS compendium of verification rules, rule 9.
HOLD_TYPES_BY_ITEM: dict[str, tuple[str, ...]] = {
    "1-003000": ("01", "02", "03"),
    "1-005000": ("01", "02", "03"),
    "2-002050": ("05",),
    "2-003000": ("04",),
    "2-004000": ("04",),
}

ESA2010_SECURITY_TYPES: dict[str, str] = {
    "F.3": "Debt securities",
    "F.511": "Quoted shares",
    "F.512": "Unquoted shares",
    "F.519": "Other equity",
    "F.52": "Shares/units of investment funds",
}

# Per-item restriction — TPTOBS compendium of verification rules, rule 11.
SECURITY_TYPES_BY_ITEM: dict[str, tuple[str, ...]] = {
    "1-003000": ("F.3",),
    "1-005000": ("F.511", "F.512", "F.519", "F.52"),
    "2-002050": ("F.3", "F.511", "F.512", "F.519", "F.52"),
    "2-003000": ("F.3",),
    "2-004000": ("F.52",),
}

DEBT_TYPE = "F.3"
FUND_SHARE_TYPE = "F.52"
EQUITY_TYPES = ("F.511", "F.512", "F.519", "F.52")

COUPON_TYPES: dict[str, str] = {
    "01": "Fixed", "02": "Progressive", "03": "Floating",
    "04": "Zero coupon", "05": "Index linked", "99": "Other",
}

COUPON_FREQUENCIES: dict[str, str] = {
    "00": "Zero coupon", "01": "Annual", "02": "Semi-annual", "04": "Quarterly",
    "06": "Bi-monthly", "12": "Monthly", "24": "Fortnightly", "99": "Other",
}

# Maximum days between the closing date and the last coupon payment date,
# by coupon frequency — TPTOBS compendium of verification rules, rule 22
# (twice the nominal period, to allow for a long first coupon). None = no bound.
COUPON_FREQUENCY_MAX_DAYS: dict[str, int | None] = {
    "00": None, "01": 720, "02": 360, "04": 180, "06": 124, "12": 62, "24": 31, "99": None,
}

QUOTATION_TYPES: dict[str, str] = {
    "percent": "Quoted in % of the nominal (typical for debt securities)",
    "currency": "Quoted in currency / number of units (typical for equities)",
}

# Reported when the reporter has no identifier at all for the issuer (§4.3).
NO_NATIONAL_ID_TYPE = "XX_NOTAP"
NO_NATIONAL_ID_CODE = "XX"

# Default split date/ratio for shares issued (TPTOBS VER rules 25 and 27).
DEFAULT_SPLIT_DATE = "2008-12-31"
DEFAULT_SPLIT_RATIO = "1"
DEFAULT_POOL_FACTOR = "1"
PERPETUAL_MATURITY_DATE = "2999-01-01"  # TPTOBS instructions §4.6.1.3
