"""ISO reference data and identifier check digits, shared across regimes.

Country and currency codes, the EEA membership list, and the check-digit
algorithms for ISIN (ISO 6166), LEI (ISO 17442) and BIC (ISO 9362) are used
identically by the BCL engines (domain.bcl.bcl_codes re-exports them) and by the
AIFMD Annex IV engine, whose CSSF controls verify exactly these.
"""

from __future__ import annotations

import re

# =============================================================================
# ISO 3166-1 alpha-2
# =============================================================================

ISO_3166_ALPHA2: frozenset[str] = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO
FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE
JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO
MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW
PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM
TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())

# European Economic Area: the EU 27 plus Iceland, Liechtenstein and Norway.
# Used by CSSF control CAF-009 (the AIF EEA flag must match its domicile).
EEA_COUNTRIES: frozenset[str] = frozenset(
    "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IS IT LI LT LU LV MT NL NO PL PT RO SE SI SK".split()
)

# =============================================================================
# ISO 4217
# =============================================================================

ISO_4217: frozenset[str] = frozenset("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF
CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF
GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD
LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP
PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP
TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XCD XCG XDR XOF XPD XPF XPT XSU
XUA YER ZAR ZMW ZWG
""".split())


# =============================================================================
# ISIN — ISO 6166
# =============================================================================

_ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")

# Prefixes that never identify a real ISIN (BCL TPTOBS verification rule 6).
ISIN_FORBIDDEN_PREFIXES = frozenset({"DU", "EV", "HF", "HS", "QS", "QT", "QU", "QY", "TE", "XF", "XX", "ZZ"})
ISIN_EXTRA_PREFIXES = frozenset({"EU", "XA", "XB", "XC", "XD", "XS"})


def isin_checksum_ok(code: str) -> bool:
    """ISO 6166 check digit (Luhn over the base-36 expansion)."""
    code = (code or "").strip().upper()
    if not _ISIN_RE.fullmatch(code):
        return False
    digits = "".join(str(int(c, 36)) for c in code[:11])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == int(code[11])


def isin_prefix_ok(code: str) -> bool:
    prefix = (code or "").strip().upper()[:2]
    if prefix in ISIN_FORBIDDEN_PREFIXES:
        return False
    return prefix in ISO_3166_ALPHA2 or prefix in ISIN_EXTRA_PREFIXES


def is_valid_isin(code: str) -> bool:
    return isin_checksum_ok(code) and isin_prefix_ok(code)


# =============================================================================
# LEI — ISO 17442
# =============================================================================

_LEI_RE = re.compile(r"[A-Z0-9]{18}[0-9]{2}")

# BCL's explicit "the issuer has no LEI" placeholder.
NO_LEI = "0" * 20


def lei_format_ok(code: str) -> bool:
    return bool(_LEI_RE.fullmatch((code or "").strip().upper()))


def lei_checksum_ok(code: str) -> bool:
    """ISO 17442 check digits (mod 97-10)."""
    code = (code or "").strip().upper()
    if not lei_format_ok(code):
        return False
    if code == NO_LEI:
        return True
    return int("".join(str(int(c, 36)) for c in code)) % 97 == 1


# =============================================================================
# BIC — ISO 9362
# =============================================================================

# The AIFMD schema's BICCodeType is the 11-character form only.
_BIC_RE = re.compile(r"[A-Z0-9]{11}")


def bic_format_ok(code: str) -> bool:
    code = (code or "").strip().upper()
    if not _BIC_RE.fullmatch(code):
        return False
    return code[:4].isalpha() and code[4:6] in ISO_3166_ALPHA2
