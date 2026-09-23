"""BCL-specific helpers on top of the shared XML primitives.

The element tree, the serializer, the exact decimal/date formatting and the
``Issue`` type live in domain.shared.xml_common and are shared with the AIFMD engine;
they are re-exported here so the BCL modules keep a single import site. What
is genuinely BCL-specific — the institution-type table and the BCL file naming
convention — stays below.
"""

from __future__ import annotations

import re
from datetime import date

from domain.shared.xml_common import (  # noqa: F401  (re-exported for the BCL modules)
    ERROR, WARNING, Issue, Node, as_date, blank, clean_text, creation_datetime, errors_of,
    fmt_bool, fmt_date, fmt_decimal, fmt_int, fmt_integer, is_number, serialize, to_decimal,
    warnings_of,
)

# =============================================================================
# File naming convention
# =============================================================================
# From BCL's S 2.20 compendium (rule RNOM00) and the official example files:
#   S0220_L0_202512_B000000341_NAF66012345600001_20250701_001.xml
#   S0103_L4_202512_B000000789_O001220003_20141009_001.xml
# The identification-number type (2 digits, as used inside the XML) maps to a
# one-letter (or "NAF") prefix in the file name — table of item 1031 in the
# S 2.20 instructions.

ID_TYPE_TO_FILENAME_PREFIX: dict[str, str] = {
    "01": "1", "05": "5", "06": "6", "23": "B", "26": "O", "27": "K",
    "30": "S", "32": "P", "36": "I", "40": "A", "42": "NAF",
}

ID_TYPE_LABELS: dict[str, str] = {
    "01": "Number allocated by the CSSF to other entities",
    "05": "Number allocated by the BCL to resident entities non-registered by the CSSF",
    "06": "Number allocated by the BCL to non-resident entities",
    "23": "Number allocated by the CSSF to banks",
    "26": "Number allocated by the CSSF to the UCIs (5 digits) and to the compartments (4 digits)",
    "27": "Number allocated by the CSSF to the SICAR",
    "30": "Number allocated by the CSSF to management companies",
    "32": "Number allocated by the CSSF to professionals of the financial sector",
    "36": "Number allocated by the CSSF to professionals of the financial sector - support",
    "40": "Number allocated by the CSSF to alternative investment fund managers",
    "42": "Number allocated by the BCL to investment funds non-authorised by the CSSF",
}


def filename_id_token(id_type: str, code: str, *, role: str = "reporter") -> str:
    """``23`` + ``789`` -> ``B000000789``; ``42`` + ``66012345600001`` as
    declarant -> ``NAF66012345600001``. Raises ValueError if it cannot be
    expressed in the file-name convention."""
    prefix = ID_TYPE_TO_FILENAME_PREFIX.get(str(id_type).strip())
    if prefix is None:
        raise ValueError(f"institution type {id_type!r} has no file-name prefix (expected one of {', '.join(ID_TYPE_TO_FILENAME_PREFIX)})")
    digits = str(code).strip()
    if not digits.isdigit():
        raise ValueError(f"institution code {code!r} must be numeric to be used in the file name")
    width = 14 if (prefix == "NAF" and role == "declarant") else 9
    if len(digits) > width:
        raise ValueError(f"institution code {code!r} is longer than {width} digits")
    return f"{prefix}{digits.zfill(width)}"


_S220_FILENAME_RE = re.compile(
    r"(?i)^((S0220)_((L[0-9])_)*(((19|20)\d\d)(0[0-9]|1[0-2]))_([1|5|6|B|S|P|I|A][0-9]{9}|NAF[0-9]{9})_(NAF[0-9]{14})_"
    r"((19|20)\d\d(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1]))_([0-9]{3})\.(xml))$"
)


def build_filename(
    report_code: str, layout: int, period_yyyymm: str, reporter_token: str, declarant_token: str,
    creation_date: date | None = None, sequence: int = 1,
) -> str:
    """``S0103`` + 4 + ``202512`` ... -> ``S0103_L4_202512_B..._O..._20260105_001.xml``"""
    if not re.fullmatch(r"(19|20)\d\d(0[1-9]|1[0-2])", period_yyyymm):
        raise ValueError(f"period {period_yyyymm!r} must be YYYYMM")
    if not 0 <= int(sequence) <= 999:
        raise ValueError("sequence number must be between 0 and 999")
    stamp = (creation_date or date.today()).strftime("%Y%m%d")
    return f"{report_code}_L{int(layout)}_{period_yyyymm}_{reporter_token}_{declarant_token}_{stamp}_{int(sequence):03d}.xml"


def filename_regex(report_code: str) -> "re.Pattern[str]":
    """S 2.20 uses BCL's own published regex verbatim; the other reports use the
    same shape generalised to their report code."""
    if report_code == "S0220":
        return _S220_FILENAME_RE
    return re.compile(
        rf"(?i)^{re.escape(report_code)}_L[0-9]_((19|20)\d\d(0[1-9]|1[0-2]))_([156BOKSPIA][0-9]{{9}}|NAF[0-9]{{9}}|NAF[0-9]{{14}})_"
        rf"([156BOKSPIA][0-9]{{9}}|NAF[0-9]{{14}})_((19|20)\d\d(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01]))_[0-9]{{3}}\.xml$"
    )
