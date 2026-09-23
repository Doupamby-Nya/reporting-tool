"""Builds the filled-in workbooks the non-regression cases start from.

Run once, from Backend/api:

    poetry run python tests/non_regression/make_inputs.py

It fills each regime's own blank template with a fictitious but complete
data set and writes the result under ``inputs/``. The files are committed:
the Streamlit oracle and the API tests must read the very same bytes, so
they are built once rather than on each run. Every name, code and amount in
them is invented.
"""

from __future__ import annotations

import io
import sys
import warnings
from datetime import date
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from domain.esef import esef_engine  # noqa: E402
from domain.fatca import fatca_pipeline  # noqa: E402
from domain.o41 import o41_engine  # noqa: E402
from domain.saq import saq_engine  # noqa: E402
from domain.shared.sample_data import SAMPLE_FUNDS  # noqa: E402
from domain.urr import urr_engine  # noqa: E402

INPUTS = HERE / "inputs"

# openpyxl warns that it drops the templates' data-validation extensions;
# the drop-down lists are not what these fixtures test.
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _load(template: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(template))


def _save(workbook: openpyxl.Workbook, name: str) -> None:
    buffer = io.BytesIO()
    workbook.save(buffer)
    (INPUTS / name).write_bytes(buffer.getvalue())
    print(f"  wrote inputs/{name}")


def _headers(sheet) -> list[str]:
    return [cell.value for cell in sheet[1]]


def _fill_keyed(sheet, values: dict, *, key_header: str, value_header: str) -> None:
    """Sheets laid out as one row per key: writes each value on its key's row."""
    headers = _headers(sheet)
    key_col, value_col = headers.index(key_header) + 1, headers.index(value_header) + 1
    for row in range(2, sheet.max_row + 1):
        key = sheet.cell(row, key_col).value
        if key is not None and str(key) in values:
            sheet.cell(row, value_col, values[str(key)])


def _write_rows(sheet, rows: list[dict], *, start: int = 2) -> None:
    """Sheets laid out as a table under a header row: one record per row."""
    headers = _headers(sheet)
    sheet.delete_rows(start, max(sheet.max_row - start + 1, 0))
    for offset, record in enumerate(rows):
        for column, header in enumerate(headers, start=1):
            if header in record:
                sheet.cell(start + offset, column, record[header])


# =============================================================================
# U 1.1
# =============================================================================

def urr() -> None:
    workbook = _load(urr_engine.build_urr_template_workbook())
    _fill_keyed(workbook["Fund_Info"], {
        "reference_month": date(2025, 11, 1), "reporting_status": "final report",
        "sender_cssf_code": "B00000999", "employee_name": "Claire Martin",
        "employee_phone": "+352 000 000", "sender_email": "claire.martin@example.lu",
        "uci_cssf_code": "O00001234", "uci_name": "Demo Balanced Fund", "uci_currency": "EUR",
        "lei": "5493000DEMO0000000X1", "valuation_date": date(2025, 11, 28),
        "nav_frequency": 1, "launch_date": date(2019, 3, 1), "redemption_frequency": 1,
        "open_closed_end": 1, "nav_preceding_month": 120_000_000, "nav_this_month": 121_500_000,
        "proceeds_issued": 2_000_000, "payments_redeemed": 1_200_000, "total_distributions": 0,
        "dividends_shares": 150_000, "dividends_shares_lu": 20_000, "interest_bonds": 80_000,
        "charges": 95_000, "advisory_mgmt_fees": 70_000, "depositary_fees": 10_000,
        "admin_fees": 15_000, "net_realised": 300_000, "net_unrealised": 400_000,
    }, key_header="key", value_header="value")
    labels = dict(urr_engine.SHARE_CLASS_FIELDS)
    # Share-class dates are left empty on purpose: Excel hands them back as
    # timestamps, and the Streamlit original wrote those out with a time
    # part. The JSON cases cover share-class dates instead.
    rows = [
        {"cssf_code": "S00000101", "name": "A EUR Acc", "currency": "EUR", "isin": "LU0000000101",
         "investor_base": 1, "units_outstanding": 800_000, "nav_per_unit_uci_ccy": 100.25,
         "nav_per_unit_class_ccy": 100.25, "net_return_pct": 0.85, "units_issued": 15_000,
         "units_redeemed": 9_000, "income_uci_ccy": 180_000, "expenses_uci_ccy": 70_000},
        {"cssf_code": "S00000102", "name": "I USD Hedged", "currency": "USD", "isin": "LU0000000102",
         "spec_fx": True, "investor_base": 2, "units_outstanding": 400_000,
         "nav_per_unit_uci_ccy": 103.0, "nav_per_unit_class_ccy": 111.4, "net_return_pct": 1.1,
         "units_issued": 5_000, "units_redeemed": 3_000, "income_uci_ccy": 50_000,
         "expenses_uci_ccy": 25_000},
    ]
    # Every other column is filled with its default: the Streamlit original
    # crashed on a blank numeric cell (see filingsService._share_class).
    defaults = {k: v for k, v in urr_engine.SHARE_CLASS_DEFAULT_ROW.items() if not k.endswith("_date")
                and k != "closing_reason"}
    _write_rows(workbook["Share_Classes"],
                [{labels[k]: v for k, v in {**defaults, **row}.items()} for row in rows])
    _save(workbook, "urr_filled.xlsx")


# =============================================================================
# O 4.1 — the totals are derived, so the Annex B formulas hold
# =============================================================================

O41_LEAVES = {
    "1112": 40_000_000, "1113": 5_000_000, "1114": 2_000_000, "1115": 1_000_000,
    "1121": 20_000_000, "1122": 3_000_000, "1130": 1_500_000, "1140": 500_000,
    "1211": 4_000_000, "1212": 1_000_000, "1220": 800_000, "1230": 200_000,
    "1311": 600_000, "1312": 100_000, "1320": 300_000,
    "1410": 250_000, "1420": 50_000, "1510": 120_000, "1520": 30_000,
    "2100": 900_000, "2200": 100_000,
    "4100": 1_200_000, "4200": 800_000, "4300": 50_000, "4410": 20_000, "4420": 10_000, "4430": 5_000,
    "5110": 400_000, "5120": 60_000, "5130": 40_000, "5210": 30_000, "5220": 20_000, "5230": 10_000,
    "5310": 15_000, "5320": 5_000, "5400": 25_000, "5500": 35_000,
    "7100": 700_000, "7200": -300_000,
    "3001": 70_000_000, "8100": 9_000_000, "8200": 6_000_000, "9000": 0,
}


def o41_values() -> dict[str, float]:
    """The leaves above, with every total the Annex B formulas define."""
    values = dict(O41_LEAVES)
    for _ in range(len(o41_engine.VALIDATION_FORMULAS)):
        for result, components, operation in o41_engine.VALIDATION_FORMULAS:
            amounts = [values.get(code, 0.0) for code in components]
            values[result] = sum(amounts) if operation == "sum" else amounts[0] - sum(amounts[1:])
    # Line 3000 is also bound to the capital movements (3001 + 7000 + 8000 - 9000):
    # 3001 is solved for so both definitions of the net assets agree.
    values["3001"] = values["3000"] - values["7000"] - values["8000"] + values.get("9000", 0.0)
    return {code: float(amount) for code, amount in values.items()}


def o41() -> None:
    workbook = _load(o41_engine.build_o41_template_workbook())
    _write_rows(workbook["Fund_Info"], [{
        "uci_name": "Demo Umbrella SICAV", "subfund_name": "Demo Equity", "uci_id": "O00001234",
        "subfund_id": "00000001", "year_end": date(2025, 12, 31), "currency": "EUR",
        "employee_name": "Claire Martin", "employee_phone": "+352 000 000",
    }])
    _fill_keyed(workbook["Line_Items"], o41_values(), key_header="code", value_header="amount")
    _write_rows(workbook["Country_Breakdown"], [
        {"line_code": "1112", "country_iso": "LU", "amount": 10_000_000},
        {"line_code": "1112", "country_iso": "DE", "amount": 30_000_000},
    ])
    _write_rows(workbook["Marketing_Countries"], [
        {"country_iso": "LU", "pct": 60}, {"country_iso": "BE", "pct": 40},
    ])
    _save(workbook, "o41_filled.xlsx")


# =============================================================================
# ESEF
# =============================================================================

ESEF_FACTS = {
    "cash": 2_500_000, "investments": 118_000_000, "receivables": 1_500_000, "total_assets": 122_000_000,
    "payables": 1_000_000, "total_liabilities": 1_000_000, "issued_capital": 100_000_000,
    "retained_earnings": 21_000_000, "total_equity": 121_000_000, "revenue": 3_200_000,
    "investment_gains": 6_400_000, "admin_expenses": 1_100_000, "finance_costs": 50_000,
    "profit_before_tax": 8_450_000, "income_tax": 60_000, "profit_loss": 8_390_000,
    "other_comprehensive_income": 0, "comprehensive_income": 8_390_000, "cf_operating": 1_800_000,
    "cf_investing": -1_000_000, "cf_financing": -300_000, "cf_net_change": 500_000,
}
ESEF_NOTES = {
    "general_information": "Demo Fund S.A. is a fictitious investment company used for testing.",
    "basis_of_preparation": "Prepared under IFRS as adopted by the EU.",
    "accounting_policies": "Financial assets are measured at fair value through profit or loss.",
}


def esef() -> None:
    workbook = _load(esef_engine.build_esef_template_workbook())
    _write_rows(workbook["Fund_Info"], [{
        "entity_name": "Demo Fund S.A.", "lei": "5493000DEMO0000000X1", "currency": "EUR",
        "period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31),
    }])
    _fill_keyed(workbook["Line_Items"], ESEF_FACTS, key_header="key", value_header="value")
    _fill_keyed(workbook["Notes"], ESEF_NOTES, key_header="key", value_header="text")
    _save(workbook, "esef_filled.xlsx")


# =============================================================================
# SAQ
# =============================================================================

def saq() -> None:
    workbook = _load(saq_engine.build_saq_template_workbook())
    _write_rows(workbook["Entity_Info"], [{
        "entity_name": "Demo Fund S.A.", "uci_type": "UCITS",
        "financial_year_end": date(2025, 12, 31), "dirigeant_reviewed": True,
    }])
    answers, comments = {}, {}
    for index, question in enumerate(saq_engine.SAQ_QUESTIONS):
        options = [o for o in question.get("options", ["—", "Yes", "No", "N/A"]) if o != "—"]
        answers[question["key"]] = options[index % len(options)]
        if index % 3 == 0:
            comments[question["key"]] = f"Fictitious comment on question {index + 1}."
    _fill_keyed(workbook["Self_Assessment"], answers, key_header="key", value_header="answer")
    _fill_keyed(workbook["Self_Assessment"], comments, key_header="key", value_header="comment")
    _save(workbook, "saq_filled.xlsx")


# =============================================================================
# FATCA / CRS
# =============================================================================

FATCA_YEAR = 2025
_RFI = {
    "Reporting period": FATCA_YEAR, "Name of Reporting Financial Institution (RFI)": "Demo Fund SICAV",
    "Luxembourg TIN of RFI": "20231234567", "GIIN of RFI": "ABC123.99999.SL.442",
    "Address of RFI": "12 rue Eugene Ruppert", "code Postal and country of RFI": "L-2453 Luxembourg",
    "Name of point of contact (POC) of RFI": "Martin",
    "First Name of point of contact (POC) of RFI": "Claire",
    "E-mail of POC of RFI": "claire.martin@example.lu", "Phone number of POC of RFI": "+352 000 000",
    "Data notification": "Yes",
}
_AMOUNTS = ("Account balance, i.e. sum of equity and debt interest as at 31.12.{y}", "Proceeds during {y}",
            "Distributions (dividends) during {y}", "Interest paid/accrued in {y}", "Other paid/accrued in {y}")


def _money(balance, proceeds=0, dividends=0, interest=0, other=0) -> dict:
    return {label.format(y=FATCA_YEAR): amount
            for label, amount in zip(_AMOUNTS, (balance, proceeds, dividends, interest, other))}


def _account(**fields) -> dict:
    return {**_RFI, "Dormant Account": "false", "Undocumented Account": "false",
            "Type of account": "OECD605 - Other", "Self-certification inconsistencies": "No",
            f"Closed account in {FATCA_YEAR}": "false", "Currency": "EUR",
            "US TIN of account holder, if applicable": "", **fields}


FATCA_INDIVIDUALS = [
    _account(**{"Account Number of account holder": "A-1001", "TIN PP": "FR1234567890",
                "Name of PP": "Jean", "Surname of PP": "Dupont", "Tax residence of PP": "FR",
                "Country of residence of PP": "FR", "Adress of PP": "1 rue de Paris, 75001 Paris",
                "E-mail address for Specific Data protection notification": "jean.dupont@example.fr",
                "Telephone number": "+33 000", "Place of birth": "Lyon", "Date of Birth": "1970-05-17",
                **_money(125_000.5, dividends=1_500)}),
    _account(**{"Account Number of account holder": "A-1002", "TIN PP": "DE98765432101",
                "Name of PP": "Anna", "Surname of PP": "Schmidt", "Tax residence of PP": "DE",
                "Country of residence of PP": "DE", "Adress of PP": "Hauptstrasse 5, 10115 Berlin",
                "E-mail address for Specific Data protection notification": "anna.schmidt@example.de",
                "Telephone number": "+49 000", "Place of birth": "Hamburg", "Date of Birth": "1982-11-02",
                **_money(48_000, proceeds=2_000, interest=120)}),
]
FATCA_ACTIVE = [
    _account(**{"Account Number of account holder": "E-2001", "TIN active NFE": "BE0123456789",
                "Name of Active": "Example Trading SA", "Tax residence of Active": "BE",
                "Country of residence of active": "BE", "Adress of Active NFE": "Rue Royale 10, 1000 Bruxelles",
                "E-mail address for Specific Data protection notification": "info@example.be",
                "Telephone number": "+32 000", **_money(900_000, dividends=25_000)}),
]


def fatca(name: str, sheet_names: dict[str, str]) -> None:
    workbook = _load(fatca_pipeline.build_fatca_template_workbook(FATCA_YEAR))
    for sheet, rows in (("CPS", [dict(_RFI)]), ("Individual", FATCA_INDIVIDUALS), ("Active", FATCA_ACTIVE)):
        _write_rows(workbook[sheet], rows)
    for old, new in sheet_names.items():
        workbook[old].title = new
    _save(workbook, name)


def priips() -> None:
    """The ten fictitious demo funds both tools ship with, as the PRIIPs input."""
    import json

    (INPUTS / "priips_funds.json").write_text(json.dumps(SAMPLE_FUNDS, indent=1, ensure_ascii=False),
                                              encoding="utf-8")
    print("  wrote inputs/priips_funds.json")


def main() -> None:
    INPUTS.mkdir(exist_ok=True)
    priips()
    urr()
    o41()
    esef()
    saq()
    fatca("fatca_crs.xlsx", {})
    # The same data under the tab names a client's own workbook may use:
    # the CPS / Individual / Active tabs are recognised by name.
    fatca("fatca_crs_renamed_tabs.xlsx", {"CPS": "CPS 2025", "Individual": "Individuals", "Active": "Active NFEs"})


if __name__ == "__main__":
    main()
