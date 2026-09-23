"""O 4.1 "Renseignements financiers annuels" reporting engine (CSSF/IML).

Table O 4.1 (annual financial information) is a YEARLY report filed by
Luxembourg UCIs under Circular IML 97/136 (as amended by CSSF Circular
07/310 and CSSF Circular 08/348) — genuinely still active today per CSSF's
own "Reporting to be submitted by UCIs" page, and distinct from — not
superseded by — the monthly U 1.1 report under Circular 15/627 (see
domain.urr.urr_engine). Unlike U 1.1's XML, O 4.1 is transmitted in EDIFACT
format (an older EDI message-segment standard); the real segment structure
and a real worked message example are given in the CSSF's own "Table O 4.1"
technical note, and build_o41_edifact() below follows that structure
directly, not guessed.

Line codes and labels are taken directly from Annexe B of Circular IML
97/136 (the human-readable form, e.g. "1111 - Shares, excluding UCI
units") together with the 23 real validation/cross-check formulas printed
immediately below that annex. The EDIFACT wire format actually transmitted
to the CSSF uses a renumbered variant of these same codes, documented in
the "Table O 4.1" technical note (append a trailing 0 to every code,
except 1112->11111, 1113->11112, 1114->11120, 1115->11130) —
EDIFACT_CODE_MAP below is that exact renumbering, verified line-by-line:
every mapped code was checked to resolve to the parent code the technical
note's own S/E/T/I hierarchy table declares for it.

Scope: the four numbered sections of Annexe B (I. Statement of Net Assets,
II. Statement of Operations, III. Changes in Net Assets, IV. Changes in
the Portfolio — 68 line items total) plus a representative, free-form
breakdown for sections V (securities portfolio by country) and VI
(countries in which the UCI is marketed, which must sum to 100%) — not a
fixed per-ISO-code/per-line-type grid (Annex B's own sub-tables 2/3 would
need every line type x every ISO country code, hundreds of mostly-empty
cells). The generated EDIFACT message is structurally faithful (real
segment tags/qualifiers, real CPT+VAL+QTY triplets using the real
renumbered codes) but its control fields (interchange reference, segment
count in UNT, authentication password) are illustrative placeholders —
this has not been validated against a live IML/CSSF EDIFACT parser.

Note on O 1.1: the OLDER monthly table (also under Circular IML 97/136, as
amended by CSSF Circular 07/310) was repealed and replaced by U 1.1
(Circular CSSF 15/627) as of the June 2016 reporting period. It is not
implemented here since it is no longer a live reporting obligation.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

SECTIONS = [
    "I. STATEMENT OF NET ASSETS",
    "II. STATEMENT OF OPERATIONS",
    "III. CHANGES IN NET ASSETS",
    "IV. CHANGES IN THE PORTFOLIO",
]

# (code, label, section) — codes/labels copied verbatim (including case —
# ALL CAPS marks a header/subtotal line exactly as printed in the source)
# from Annexe B of Circular IML 97/136. No word added, dropped or
# paraphrased relative to that source text.
LINE_ITEMS: list[tuple[str, str, str]] = [
    ("1000", "TOTAL ASSETS", SECTIONS[0]),
    ("1100", "SECURITIES PORTFOLIO", SECTIONS[0]),
    ("1110", "Shares and other variable-yield securities", SECTIONS[0]),
    ("1111", "Shares, excluding UCI units", SECTIONS[0]),
    ("1112", "Listed shares or shares traded on another regulated market", SECTIONS[0]),
    ("1113", "Unquoted shares", SECTIONS[0]),
    ("1114", "Other participating interests", SECTIONS[0]),
    ("1115", "UCI units", SECTIONS[0]),
    ("1120", "Bonds and other debt securities", SECTIONS[0]),
    ("1121", "Short-term securities (initial maturity: up to one year)", SECTIONS[0]),
    ("1122", "Medium/long-term securities (initial maturity: more than one year)", SECTIONS[0]),
    ("1130", "Money market instruments (residual maturity: more than one year)", SECTIONS[0]),
    ("1140", "Warrants and other rights", SECTIONS[0]),
    ("1200", "FINANCIAL INSTRUMENTS", SECTIONS[0]),
    ("1210", "Options contracts", SECTIONS[0]),
    ("1211", "Options purchased", SECTIONS[0]),
    ("1212", "Options sold", SECTIONS[0]),
    ("1220", "Forward contracts", SECTIONS[0]),
    ("1230", "Others", SECTIONS[0]),
    ("1300", "LIQUID ASSETS", SECTIONS[0]),
    ("1310", "Cash at bank", SECTIONS[0]),
    ("1311", "in Luxembourg", SECTIONS[0]),
    ("1312", "abroad", SECTIONS[0]),
    ("1320", "Other liquid assets", SECTIONS[0]),
    ("1400", "FIXED ASSETS", SECTIONS[0]),
    ("1410", "Real estate", SECTIONS[0]),
    ("1420", "Formation expenses", SECTIONS[0]),
    ("1500", "OTHER ASSETS", SECTIONS[0]),
    ("1510", "Precious metals", SECTIONS[0]),
    ("1520", "Others", SECTIONS[0]),
    ("2000", "TOTAL LIABILITIES", SECTIONS[0]),
    ("2100", "BORROWINGS", SECTIONS[0]),
    ("2200", "OTHER LIABILITIES", SECTIONS[0]),
    ("3000", "NET ASSETS AT THE END OF THE FINANCIAL YEAR", SECTIONS[0]),
    ("4000", "TOTAL INCOME", SECTIONS[1]),
    ("4100", "DIVIDENDS", SECTIONS[1]),
    ("4200", "INTEREST ON BONDS AND OTHER DEBT SECURITIES", SECTIONS[1]),
    ("4300", "BANK INTEREST", SECTIONS[1]),
    ("4400", "OTHER INCOME", SECTIONS[1]),
    ("4410", "Rental income", SECTIONS[1]),
    ("4420", "Commission income", SECTIONS[1]),
    ("4430", "Other", SECTIONS[1]),
    ("5000", "TOTAL CHARGES", SECTIONS[1]),
    ("5100", "COMMISSIONS PAYABLE", SECTIONS[1]),
    ("5110", "Advisory and/or management commission", SECTIONS[1]),
    ("5120", "Depositary bank commission", SECTIONS[1]),
    ("5130", "Other commission", SECTIONS[1]),
    ("5200", "ADMINISTRATIVE EXPENSES", SECTIONS[1]),
    ("5210", "Central administration costs", SECTIONS[1]),
    ("5220", "Audit and inspection costs", SECTIONS[1]),
    ("5230", "Other administrative expenses", SECTIONS[1]),
    ("5300", "TAXES", SECTIONS[1]),
    ("5310", "Subscription tax", SECTIONS[1]),
    ("5320", "Other taxes", SECTIONS[1]),
    ("5400", "INTEREST PAID", SECTIONS[1]),
    ("5500", "OTHER CHARGES", SECTIONS[1]),
    ("6000", "NET INVESTMENT INCOME", SECTIONS[1]),
    ("7100", "NET REALISED GAINS/LOSSES", SECTIONS[1]),
    ("7200", "CHANGE IN NET UNREALISED GAINS/LOSSES", SECTIONS[1]),
    ("7000", "PROFIT OR LOSS ON OPERATIONS", SECTIONS[1]),
    ("3001", "NET ASSETS AT THE BEGINNING OF THE FINANCIAL YEAR", SECTIONS[2]),
    ("8000", "NET SHARES OR UNITS ISSUED (OR REDEEMED)", SECTIONS[2]),
    ("8100", "Net proceeds from units or shares issued", SECTIONS[2]),
    ("8200", "Payments made in settlement of redemptions", SECTIONS[2]),
    ("9000", "DISTRIBUTIONS", SECTIONS[2]),
    ("9100", "of which: reinvested dividends", SECTIONS[2]),
    ("9500", "TOTAL PURCHASES OF TRANSFERABLE SECURITIES AND OTHER INVESTMENTS", SECTIONS[3]),
    ("9600", "TOTAL SALES OF TRANSFERABLE SECURITIES AND OTHER INVESTMENTS", SECTIONS[3]),
]
LINE_LABELS = {code: label for code, label, _ in LINE_ITEMS}

# (result_code, [component codes], "sum"|"diff") — the 23 two-level
# validation formulas printed directly below Annexe B ("Validation of the
# annual table O 4.1."). "diff" means components[0] - sum(components[1:]).
VALIDATION_FORMULAS: list[tuple[str, list[str], str]] = [
    ("1000", ["1100", "1200", "1300", "1400", "1500"], "sum"),
    ("1100", ["1110", "1120", "1130", "1140"], "sum"),
    ("1110", ["1111", "1114", "1115"], "sum"),
    ("1111", ["1112", "1113"], "sum"),
    ("1120", ["1121", "1122"], "sum"),
    ("1200", ["1210", "1220", "1230"], "sum"),
    ("1210", ["1211", "1212"], "sum"),
    ("1300", ["1310", "1320"], "sum"),
    ("1310", ["1311", "1312"], "sum"),
    ("1400", ["1410", "1420"], "sum"),
    ("1500", ["1510", "1520"], "sum"),
    ("2000", ["2100", "2200"], "sum"),
    ("3000", ["1000", "2000"], "diff"),
    ("4000", ["4100", "4200", "4300", "4400"], "sum"),
    ("4400", ["4410", "4420", "4430"], "sum"),
    ("5000", ["5100", "5200", "5300", "5400", "5500"], "sum"),
    ("5100", ["5110", "5120", "5130"], "sum"),
    ("5200", ["5210", "5220", "5230"], "sum"),
    ("5300", ["5310", "5320"], "sum"),
    ("6000", ["4000", "5000"], "diff"),
    ("7000", ["6000", "7100", "7200"], "sum"),
    ("8000", ["8100", "8200"], "diff"),
]

# Short, single-line overrides for the manual-entry grid (views.o41_ingestion)
# — only for the handful of Annexe B labels long enough to wrap onto 2-3
# lines at 3-column width; every other line item keeps its LINE_ITEMS label
# as-is. The full Annexe B wording is always in that field's "?" tooltip
# (same pattern as the AIFMD module), so nothing is lost.
SHORT_LABELS: dict[str, str] = {
    "1110": "Shares & other variable-yield securities",
    "1112": "Listed shares (regulated market)",
    "1121": "Short-term securities (≤1 year)",
    "1122": "Medium/long-term securities (>1 year)",
    "1130": "Money market instruments (>1 year)",
    "3000": "NET ASSETS — END OF YEAR",
    "3001": "NET ASSETS — BEGINNING OF YEAR",
    "4200": "INTEREST ON BONDS/DEBT SECURITIES",
    "8000": "NET SHARES/UNITS ISSUED (OR REDEEMED)",
    "8100": "Net proceeds from units issued",
    "8200": "Payments for redemptions",
    "9500": "TOTAL PURCHASES (SECURITIES)",
    "9600": "TOTAL SALES (SECURITIES)",
}


# Real renumbering rule from the "Table O 4.1" technical note: append a
# trailing 0 to every Annexe B code, except the four listed exceptions —
# verified against that note's own S/E/T/I hierarchy table (see module
# docstring).
_EXCEPTIONS = {"1112": "11111", "1113": "11112", "1114": "11120", "1115": "11130"}
EDIFACT_CODE_MAP: dict[str, str] = {
    code: _EXCEPTIONS.get(code, f"{code}0") for code, _, _ in LINE_ITEMS
}


@dataclass
class O41Submission:
    uci_name: str
    subfund_name: str
    uci_id: str
    subfund_id: str
    year_end: date
    currency: str
    employee_name: str
    employee_phone: str
    values: dict[str, float] = field(default_factory=dict)  # LINE_ITEMS code -> amount
    country_breakdown: list[dict[str, Any]] = field(default_factory=list)  # [{"line_code","country_iso","amount"}]
    marketing_countries: list[dict[str, Any]] = field(default_factory=list)  # [{"country_iso","pct"}]

    def v(self, code: str) -> float:
        return float(self.values.get(code, 0.0) or 0.0)

    def validation_errors(self, tolerance: float = 1.0) -> list[str]:
        errors: list[str] = []
        if not self.uci_name:
            errors.append("UCI name is required.")
        if not self.uci_id:
            errors.append("Identification number of the UCI is required.")
        if len(self.currency) != 3:
            errors.append("Currency must be a 3-letter ISO code.")
        if self.year_end is None:
            errors.append("Year-end is required.")

        for result, components, op in VALIDATION_FORMULAS:
            if op == "sum":
                expected = sum(self.v(c) for c in components)
                formula = " + ".join(components)
            else:
                expected = self.v(components[0]) - sum(self.v(c) for c in components[1:])
                formula = " - ".join(components)
            if abs(expected - self.v(result)) > tolerance:
                errors.append(
                    f"Line {result} ({LINE_LABELS.get(result, '')}) should equal {formula} = "
                    f"{expected:,.2f}, but is {self.v(result):,.2f} (Annexe B validation formula)."
                )

        expected_3000 = self.v("3001") + self.v("7000") + self.v("8000") - self.v("9000")
        if abs(expected_3000 - self.v("3000")) > tolerance:
            errors.append(
                f"Line 3000 should equal 3001 + 7000 + 8000 - 9000 = {expected_3000:,.2f}, "
                f"but is {self.v('3000'):,.2f} (Annexe B validation formula)."
            )

        if self.marketing_countries:
            total_pct = sum(float(c.get("pct", 0) or 0) for c in self.marketing_countries)
            if abs(total_pct - 100) > 0.5:
                errors.append(
                    f"Section VI (countries in which the UCI is marketed) percentages must sum to "
                    f"100 — currently {total_pct:.1f}."
                )
        return errors


def _edifact_date(d: date) -> str:
    return d.strftime("%Y%m%d")


def build_o41_edifact(sub: O41Submission) -> str:
    """Builds a structurally faithful EDIFACT message for table O 4.1,
    following the real segment structure and example in the CSSF's "Table
    O 4.1" technical note — see module docstring for what is and isn't
    validated about the control fields."""
    now = datetime.now()
    period_start = date(sub.year_end.year, 1, 1)
    msg_ref = f"X{now.strftime('%y%m%d%H%M')}"
    lines: list[str] = []
    lines.append("UNA:+.? '")
    lines.append(f"UNB+UNOA:1+SENDER-FINREP-LU+IML-FINREP-LU+{now.strftime('%y%m%d:%H%M')}+{msg_ref}+APPLICPASSWORD'")
    lines.append(f"UNH+{msg_ref}00002+FINREP:1:911:UN'")
    lines.append(f"BGM+411:ZZZ:5+TABLE-O-4.1--D-L-00001+9'")
    lines.append(f"DTM+242:{_edifact_date(period_start)}0000:203'")
    lines.append(f"DTM+243:{_edifact_date(sub.year_end)}0000:203'")
    lines.append(f"PEI+Y+183+{_edifact_date(period_start)}{_edifact_date(sub.year_end)}+718'")
    lines.append(f"SJS+FCP+O{sub.uci_id}:ZZZ+{sub.subfund_id}'")
    lines.append(f"NAD+DT+{sub.uci_name}++{sub.subfund_name}++LUXEMBOURG++L-2955+LU'")
    lines.append("NAD+AE+CENTR.ADMINISTR.S.W.I.F.T.ADDRESS:25:17'")
    lines.append(f"CTA+AD+:MR.-{sub.employee_name}'")
    if sub.employee_phone:
        lines.append(f"COM+{sub.employee_phone}:TE'")
    lines.append("NAD+DO+IMLULULL:25:17'")
    lines.append(f"CUX+2:{sub.currency}:4'")
    lines.append("UNS+D'")

    count = 0
    for code, _label, _section in LINE_ITEMS:
        if code not in sub.values:
            continue
        wire_code = EDIFACT_CODE_MAP[code]
        amount = sub.v(code)
        sign = "CD" if amount >= 0 else "DB"
        lines.append(f"CPT+DET:1-{wire_code}'")
        lines.append(f"VAL+AMT+{abs(amount):.0f}+{sign}'")
        lines.append("QTY+140:1'")
        count += 3

    for row in sub.country_breakdown:
        line_code = row.get("line_code")
        wire_code = EDIFACT_CODE_MAP.get(line_code, line_code)
        iso = row.get("country_iso", "")
        amount = float(row.get("amount", 0) or 0)
        lines.append(f"CPT+DET:2-{wire_code}-{iso}'")
        lines.append(f"VAL+AMT+{abs(amount):.0f}+CD'")
        lines.append("QTY+140:1'")
        count += 3

    for row in sub.marketing_countries:
        iso = row.get("country_iso", "")
        pct = float(row.get("pct", 0) or 0)
        lines.append(f"CPT+DET:3-{iso}'")
        lines.append(f"VAL+AMT+{pct:.2f}+CD'")
        lines.append("QTY+140:1'")
        count += 3

    lines.append("UNS+S'")
    lines.append(f"QTY+140:{count // 3}'")
    lines.append("VAL+AMT+0'")
    lines.append("AUT+AUTHENTPASSWORD'")
    lines.append(f"DTM+218:{now.strftime('%Y%m%d%H%M')}:203'")
    lines.append(f"UNT+{len(lines) + 1}+{msg_ref}00001'")
    lines.append(f"UNZ+1+{msg_ref}'")
    return "\n".join(lines)


def build_o41_template_workbook() -> bytes:
    """Ingestion template: 'Fund_Info' header row, 'Line_Items' row per
    Annexe B line, 'Country_Breakdown' (section V) and 'Marketing_Countries'
    (section VI, percentages) sheets."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    fill = PatternFill("solid", fgColor="0A2647")

    def header_row(ws, cols):
        for idx, col in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=idx, value=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = fill
            ws.column_dimensions[cell.column_letter].width = max(16, len(col) + 2)
        ws.freeze_panes = "A2"

    ws1 = wb.active
    ws1.title = "Fund_Info"
    header_row(ws1, [
        "uci_name", "subfund_name", "uci_id", "subfund_id", "year_end", "currency",
        "employee_name", "employee_phone",
    ])

    ws2 = wb.create_sheet("Line_Items")
    header_row(ws2, ["code", "label", "section", "amount"])
    for r, (code, label, section) in enumerate(LINE_ITEMS, start=2):
        ws2.cell(row=r, column=1, value=code)
        ws2.cell(row=r, column=2, value=label.strip())
        ws2.cell(row=r, column=3, value=section)
        ws2.cell(row=r, column=4, value=None)
    ws2.column_dimensions["B"].width = 60

    ws3 = wb.create_sheet("Country_Breakdown")
    header_row(ws3, ["line_code", "country_iso", "amount"])

    ws4 = wb.create_sheet("Marketing_Countries")
    header_row(ws4, ["country_iso", "pct"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_o41_workbook(file_bytes: bytes) -> tuple[dict[str, Any], dict[str, float], list[dict], list[dict], list[str]]:
    """Parses a workbook built from build_o41_template_workbook() back into
    (fund_info dict, values dict, country_breakdown list, marketing_countries
    list, errors)."""
    import io as _io

    import pandas as pd

    errors: list[str] = []
    try:
        xls = pd.ExcelFile(_io.BytesIO(file_bytes))
    except Exception as exc:
        return {}, {}, [], [], [f"Could not read this workbook: {exc}"]

    fund_info: dict[str, Any] = {}
    if "Fund_Info" in xls.sheet_names:
        df = xls.parse("Fund_Info")
        if not df.empty:
            fund_info = {k: v for k, v in df.iloc[0].to_dict().items() if pd.notna(v)}
    else:
        errors.append("Sheet 'Fund_Info' not found.")

    values: dict[str, float] = {}
    if "Line_Items" in xls.sheet_names:
        df = xls.parse("Line_Items")
        for row in df.to_dict("records"):
            code = row.get("code")
            amount = row.get("amount")
            if code and pd.notna(amount):
                try:
                    values[str(code)] = float(amount)
                except (TypeError, ValueError):
                    pass
    else:
        errors.append("Sheet 'Line_Items' not found.")

    country_breakdown: list[dict] = []
    if "Country_Breakdown" in xls.sheet_names:
        df = xls.parse("Country_Breakdown")
        for row in df.to_dict("records"):
            if row.get("line_code") and pd.notna(row.get("amount")):
                country_breakdown.append({
                    "line_code": str(row["line_code"]), "country_iso": str(row.get("country_iso", "")).upper(),
                    "amount": float(row["amount"]),
                })

    marketing_countries: list[dict] = []
    if "Marketing_Countries" in xls.sheet_names:
        df = xls.parse("Marketing_Countries")
        for row in df.to_dict("records"):
            if row.get("country_iso") and pd.notna(row.get("pct")):
                marketing_countries.append({"country_iso": str(row["country_iso"]).upper(), "pct": float(row["pct"])})

    return fund_info, values, country_breakdown, marketing_countries, errors
