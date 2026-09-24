"""Wires the ported FATCA/CRS engine (core/fatca/, a direct port of Mazars
Luxembourg's production PyQt5 CRS/FATCA reporting tool) into the platform:
Excel ingestion -> per-category classification -> final AEOI XML.

The business rules (classification codes, reference-ID formats, XML
structure) are reused verbatim from core/fatca/core_functions*.py — this
module only adapts the orchestration (file handling, error surfacing,
preparer/config storage) to the Streamlit app's conventions.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from domain.fatca.lib.core_functions import (
    assign_template_tabs,
    create_CRS_DataReport_Initial_XML,
    create_FATCA_DataReport_Initial_XML,
    create_zero_report_crs_xml,
    create_zero_report_fatca_xml,
    dict_to_xml_str,
    find_available_tab,
    get_company_nickname,
    process_fixed_parts,
)
from domain.fatca.lib.core_functions_active import get_info_Active, get_info_Active_fatca
from domain.fatca.lib.core_functions_begin import get_info_CPS
from domain.fatca.lib.core_functions_controlling import get_info_controlling, get_info_controlling_fatca
from domain.fatca.lib.core_functions_individual import get_info_Individual, get_info_Individual_fatca
from domain.fatca.lib.core_functions_passive import get_info_passive, get_info_passive_fatca
from domain.shared.io_utils import ensure_dir_resilient, write_text_resilient

from utils.paths import RESOURCES_DIR, org_config_dir
REFERENCE_DIR = RESOURCES_DIR / "reference"
CONFIG_DIR = RESOURCES_DIR / "config"
POSTAL_CODE_PATH = str(REFERENCE_DIR / "post-courrier-colis-telechargements-Codes-Postaux.xlsx")
REPORTABLE_COUNTRIES_PATH = str(REFERENCE_DIR / "Reportable_Countries.xlsx")
PREPARERS_DEFAULT_FILE = CONFIG_DIR / "fatca_preparers.default.json"

FILER_CATEGORIES = [
    "FATCA601 - PFFI (excl. Model 2 & U.S. branch PFFI)",
    "FATCA602 - RDC FFI",
    "FATCA603 - Limited Branch or Limited FFI",
    "FATCA604 - Reporting Model 2 FFI",
    "FATCA605 - QI, WP or WT",
    "FATCA606 - Direct Reporting NFFE",
    "FATCA607 - Sponsoring Entity of a Sponsored FFI",
    "FATCA608 - Sponsoring Entity of a Sponsored Direct Reporting NFFE",
    "FATCA609 - Trustee of a Trustee-Documented Trust",
    "FATCA610 - Withholding Agent",
    "FATCA611 - Territory Financial Institution",
]

# Account-holder classification codes assigned by the legacy engine (see
# core/fatca/core_functions_{active,individual,controlling,passive}.py) —
# surfaced in the Rules Engine view so the classification is transparent.
ACCT_HOLDER_TYPE_LABELS = {
    "CRS101": "Passive NFE with Controlling Person(s) (look-through)",
    "CRS102": "Active NFE / reportable entity",
    "CRS103": "Passive NFE reported standalone",
    "FATCA102": "Passive NFFE (standalone or with Substantial Owner(s))",
    "FATCA104": "Active NFFE / reportable entity",
}


# --- Preparers (depositor point-of-contact) config -------------------------

def _preparers_file() -> Path:
    """Each organisation files under its own preparers."""
    return org_config_dir() / "fatca_preparers.json"


def load_preparers() -> dict[str, dict[str, str]]:
    path = _preparers_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_preparers(preparers: dict[str, dict[str, str]]) -> None:
    path = _preparers_file()
    ensure_dir_resilient(path.parent)
    write_text_resilient(path, json.dumps(preparers, ensure_ascii=False, indent=2))


# --- Ingestion ---------------------------------------------------------------

def load_workbook_tabs(file_bytes: bytes) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Reads every sheet of the uploaded workbook and buckets CPS/Active/
    Individual tabs by (fuzzy) sheet name, exactly like the legacy tool."""
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheets = {name: xls.parse(name) for name in xls.sheet_names}
    template_tabs = assign_template_tabs(sheets)
    return sheets, template_tabs


# --- Classification (Rules Engine) -------------------------------------------

@dataclass
class PipelineResult:
    cps_info: dict[str, Any] = field(default_factory=dict)
    active_info: Any = False
    individual_info: Any = False
    controlling_info: Any = False
    passive_info: Any = False
    errors: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "Active NFE": len(self.active_info) if isinstance(self.active_info, list) else 0,
            "Individual": len(self.individual_info) if isinstance(self.individual_info, list) else 0,
            "Controlling Person": len(self.controlling_info) if isinstance(self.controlling_info, list) else 0,
            "Passive NFE": len(self.passive_info) if isinstance(self.passive_info, list) else 0,
        }

    def acct_holder_types(self) -> dict[str, int]:
        """Counts account reports by their assigned AcctHolderType code, read
        back out of the nested dicts built by the legacy engine."""
        counts: dict[str, int] = {}
        for section in (self.active_info, self.individual_info, self.controlling_info, self.passive_info):
            if not isinstance(section, list):
                continue
            for item in section:
                report = item.get("crs:AccountReport") or item.get("fatca:AccountReport") or {}
                holder = report.get("crs:AccountHolder") or report.get("fatca:AccountHolder") or {}
                code = holder.get("crs:AcctHolderType") or holder.get("fatca:AcctHolderType")
                if code:
                    counts[code] = counts.get(code, 0) + 1
        return counts

    def reportable_countries(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for section in (self.active_info, self.individual_info, self.controlling_info, self.passive_info):
            if not isinstance(section, list):
                continue
            for item in section:
                report = item.get("crs:AccountReport") or item.get("fatca:AccountReport") or {}
                country = report.get("ReportableCountry")
                if country:
                    counts[country] = counts.get(country, 0) + 1
        return counts


def classify(template_tabs: dict[str, pd.DataFrame], params: dict[str, Any]) -> PipelineResult:
    """Runs the CPS header parse plus per-category classification (no XML
    assembly yet) — this is what the Rules Engine step shows the reviewer
    before anything is generated."""
    result = PipelineResult()
    crs_fatca = params["crs_fatca"]
    report_type = params["report_type"]
    selection = params["selection"]
    version = params["version"]

    available_tab = find_available_tab(template_tabs)
    if available_tab is None:
        result.errors.append("No usable CPS, Active or Individual sheet was found in the uploaded workbook.")
        return result

    try:
        result.cps_info = get_info_CPS(
            template_tabs.get("CPS", available_tab), POSTAL_CODE_PATH, crs_fatca, version, report_type, selection,
        )
    except Exception as exc:
        result.errors.append(f"Report header (CPS tab) parsing failed: {exc}")

    if report_type != "Data Report":
        return result

    if "Active" in template_tabs and not template_tabs["Active"].empty:
        try:
            df = template_tabs["Active"]
            result.active_info = (
                get_info_Active(df, report_type, selection, crs_fatca) if crs_fatca == "CRS"
                else get_info_Active_fatca(df, report_type, selection, crs_fatca)
            )
        except Exception as exc:
            result.errors.append(f"Active NFE classification failed: {exc}")

    if "Individual" in template_tabs and not template_tabs["Individual"].empty:
        try:
            df = template_tabs["Individual"]
            result.individual_info = (
                get_info_Individual(df, report_type, selection, crs_fatca) if crs_fatca == "CRS"
                else get_info_Individual_fatca(df, report_type, selection, crs_fatca)
            )
        except Exception as exc:
            result.errors.append(f"Individual classification failed: {exc}")

    if "CPS" in template_tabs and not template_tabs["CPS"].empty:
        cps_df = template_tabs["CPS"]
        try:
            result.controlling_info = (
                get_info_controlling(cps_df, report_type, selection, crs_fatca) if crs_fatca == "CRS"
                else get_info_controlling_fatca(cps_df, report_type, selection, crs_fatca)
            )
        except Exception as exc:
            result.errors.append(f"Controlling Person classification failed: {exc}")
        try:
            result.passive_info = (
                get_info_passive(cps_df, report_type, selection, crs_fatca) if crs_fatca == "CRS"
                else get_info_passive_fatca(cps_df, report_type, selection, crs_fatca)
            )
        except Exception as exc:
            result.errors.append(f"Passive NFE classification failed: {exc}")

    return result


# --- XML generation -----------------------------------------------------------

def generate_xml(
    template_tabs: dict[str, pd.DataFrame], params: dict[str, Any], preparer: dict[str, str],
) -> tuple[str | None, str | None, list[str]]:
    """Runs the full pipeline through to a final XML string + suggested
    filename, mirroring the legacy tool's "Launch" button exactly (same
    branching on CRS/FATCA x Zero/Data Report x Initial/Correction)."""
    crs_fatca = params["crs_fatca"]
    report_type = params["report_type"]
    selection = params["selection"]
    version = params["version"]
    filer_category = params.get("filer_category") or ""

    if selection == "Correction" and report_type == "Data Report":
        return None, None, [
            "Correction filings are not implemented by the underlying engine yet "
            "(the legacy tool itself has no coded path for Data Report + Correction). "
            "Use Initial for now, or contact the regulatory team to extend the engine."
        ]

    result = classify(template_tabs, params)
    if result.errors:
        return None, None, result.errors

    try:
        fixed_parts = process_fixed_parts(preparer)
        if crs_fatca == "CRS":
            if report_type == "Zero Report":
                final_dict = create_zero_report_crs_xml(
                    result.cps_info, POSTAL_CODE_PATH, crs_fatca, version, report_type, selection, preparer,
                )
            else:
                final_dict = create_CRS_DataReport_Initial_XML(
                    fixed_parts, result.cps_info,
                    active_accounts=result.active_info, individual_accounts=result.individual_info,
                    controlling_accounts=result.controlling_info, passive_accounts=result.passive_info,
                    report_type=report_type, selection=selection, version=version,
                    reportable_countries_path=REPORTABLE_COUNTRIES_PATH,
                )
        else:
            if report_type == "Zero Report":
                final_dict = create_zero_report_fatca_xml(
                    result.cps_info, POSTAL_CODE_PATH, crs_fatca, version, report_type, selection, preparer,
                )
            else:
                final_dict = create_FATCA_DataReport_Initial_XML(
                    fixed_parts, result.cps_info,
                    active_accounts=result.active_info, individual_accounts=result.individual_info,
                    controlling_accounts=result.controlling_info, passive_accounts=result.passive_info,
                    report_type=report_type, selection=selection, version=version,
                    filer_category=filer_category.split(" - ")[0],
                    reportable_countries_path=REPORTABLE_COUNTRIES_PATH,
                )
        xml_str = dict_to_xml_str(final_dict)
    except Exception as exc:
        return None, None, [f"XML generation failed: {exc}"]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    ri = crs_fatca.upper()
    company = get_company_nickname(result.cps_info.get("NameReportingFI", "NA"))
    rep_year = str(result.cps_info.get("ReportingPeriod", "NA"))[:4]
    pin = fixed_parts.get("aeoi_lux:PersonalIdentificationNumberDepositor", "NA")
    rfi_id = result.cps_info.get("RFI_Identifier", "NA")
    filename = f"{ri}_{timestamp}_{company}_{rep_year}_{version}_{pin}_{rfi_id}_P.xml"
    return xml_str, filename, []


# --- Ingestion template -------------------------------------------------------
#
# The exact column layout (CPS / Individual / Active / Country list) is
# taken verbatim from Forvis Mazars Luxembourg's real "Data Report Template"
# workbook, reused as-is rather than reconstructed, so both the downloadable
# template and the Manual entry grids (see views/fatca_ingestion.py) match
# the field names core/fatca/core_functions_*.py reads off each row exactly.
FATCA_TEMPLATE_FILE = REFERENCE_DIR / "FATCA_CRS_Data_Report_Template.xlsx"

# Columns of each sheet in that template, in order — used to build the
# Manual entry data_editor grids (see views/fatca_ingestion.py) and to seed
# an empty DataFrame per sheet when nothing has been uploaded yet.
CPS_TEMPLATE_COLUMNS = [
    "Reporting period", "Name of Reporting Financial Institution (RFI)", "Luxembourg TIN of RFI",
    "GIIN of RFI", "Address of RFI", "code Postal and country of RFI",
    "Name of point of contact (POC) of RFI", "First Name of point of contact (POC) of RFI",
    "E-mail of POC of RFI", "Phone number of POC of RFI", "Data notification",
    "Account Number of account holder /CP", "Type of account", "Dormant Account", "Undocumented Account",
    "TIN passive NFE", "Name of AH", "Adress of passive NFE", "Tax residence of AH", "Name of CP",
    "First Name of CP", "Tax residence of CP", "TIN of CP", "Country of residence of CP", "Address of CP",
    "Zip code", "E-mail address for Specific Data protection notification", "Place of birth CP",
    "Date of Birth CP", "US TIN of account holder/CP, if applicable", "Type of control exercised by CP",
    "Self-certification inconsistencies", "Closed account in {year}", "Currency",
    "Account balance, i.e. sum of equity and debt interest as at 31.12.{year}", "Proceeds during {year}",
    "Distributions (dividends) during {year}", "Interest paid/accrued in {year}", "Other paid/accrued in {year}",
]
INDIVIDUAL_TEMPLATE_COLUMNS = [
    "Reporting period", "Name of Reporting Financial Institution (RFI)", "Luxembourg TIN of RFI",
    "GIIN of RFI", "Address of RFI", "code Postal and country of RFI",
    "Name of point of contact (POC) of RFI", "First Name of point of contact (POC) of RFI",
    "E-mail of POC of RFI", "Phone number of POC of RFI", "Data notification",
    "Account Number of account holder", "Dormant Account", "Undocumented Account", "TIN PP",
    "Type of account", "Name of PP", "Surname of PP", "Tax residence of PP", "Country of residence of PP",
    "Adress of PP", "E-mail address for Specific Data protection notification", "Telephone number",
    "Place of birth", "Date of Birth", "US TIN of account holder, if applicable",
    "Self-certification inconsistencies", "Closed account in {year}", "Currency",
    "Account balance, i.e. sum of equity and debt interest as at 31.12.{year}", "Proceeds during {year}",
    "Distributions (dividends) during {year}", "Interest paid/accrued in {year}", "Other paid/accrued in {year}",
]
ACTIVE_TEMPLATE_COLUMNS = [
    "Reporting period", "Name of Reporting Financial Institution (RFI)", "Luxembourg TIN of RFI",
    "GIIN of RFI", "Address of RFI", "code Postal and country of RFI",
    "Name of point of contact (POC) of RFI", "First Name of point of contact (POC) of RFI",
    "E-mail of POC of RFI", "Phone number of POC of RFI", "Data notification",
    "Account Number of account holder", "TIN active NFE", "Type of account", "Dormant Account",
    "Undocumented Account", "Name of Active", "Tax residence of Active", "Country of residence of active",
    "Adress of Active NFE", "E-mail address for Specific Data protection notification", "Telephone number",
    "US TIN of account holder, if applicable", "Self-certification inconsistencies", "Closed account in {year}",
    "Currency", "Account balance, i.e. sum of equity and debt interest as at 31.12.{year}",
    "Proceeds during {year}", "Distributions (dividends) during {year}", "Interest paid/accrued in {year}",
    "Other paid/accrued in {year}",
]


def resolved_columns(template: list[str], year: int | None = None) -> list[str]:
    y = year or (date.today().year - 1)
    return [c.format(year=y) for c in template]


def build_fatca_template_workbook(reporting_year: int | None = None) -> bytes:
    """Returns the real Data Report Template workbook (CPS / Individual /
    Active / Country list sheets). The dynamic column headers (e.g. "Closed
    account in 2024") are live formulas concatenating the "Reporting period"
    example cell (A2) on each sheet — setting that cell to the target year
    is enough for Excel to recompute the right label labels on open."""
    year = reporting_year or (date.today().year - 1)
    wb = openpyxl.load_workbook(FATCA_TEMPLATE_FILE)
    for sheet in ("CPS", "Individual", "Active"):
        if sheet in wb.sheetnames:
            wb[sheet]["A2"] = year
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
