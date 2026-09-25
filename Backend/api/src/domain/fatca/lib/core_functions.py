# core_functions.py
import pandas as pd
import re
import numpy as np
import math
from dicttoxml import dicttoxml
import xml.etree.ElementTree as ET

from utils.paths import RESOURCES_DIR

# The country reference tables, read from the API's bundled resources rather
# than from beside this file: one copy of each, wherever the service runs.
REFERENCE_DIR = RESOURCES_DIR / "reference"
REPORTABLE_COUNTRIES_FILE = str(REFERENCE_DIR / "Reportable_Countries.xlsx")
ADDITIONAL_COUNTRIES_FILE = str(REFERENCE_DIR / "Additional list of countries.xlsx")

def process_fixed_parts(user_data):
    """
    Process and return the fixed parts of the reporting data based on the selected user data.

    Parameters:
        user_data (dict): Dictionary containing user details like Name, FirstName, Email, etc.

    Returns:
        dict: A dictionary with fixed parts including the person depositor info.
    """

    # Fixed depositor details
    NameDepositor = "Forvis Mazars Advisory Services"
    PersonalIdentificationNumberDepositor = "20112206982"

    # Instead, store it as a dictionary with the final sub-keys:
    AddressDepositor = {
        "aeoi_lux:StreetPhysical": "rue Guillaume J. Kroll",
        "aeoi_lux:NumberPhysical": "5",
        "aeoi_lux:PostalCodePhysical": "L-1882",
        "aeoi_lux:CityPhysical": "LUXEMBOURG",
        "aeoi_lux:CountryPhysical": "LU"
    }

    # PersonDepositor: use the passed user_data
    # Ensure all required keys are present or provide defaults/errors if strict validation is needed elsewhere
    person_depositor = {
        "aeoi_lux:Name": user_data.get("aeoi_lux:Name", "UNKNOWN"),
        "aeoi_lux:FirstName": user_data.get("aeoi_lux:FirstName", "UNKNOWN"),
        "aeoi_lux:EmailPersonal": user_data.get("aeoi_lux:EmailPersonal", "unknown@forvismazars.com"),
        "aeoi_lux:EmailOrganisation": user_data.get("aeoi_lux:EmailOrganisation", "unknown@forvismazars.com"),
        "aeoi_lux:TelephoneDirect": user_data.get("aeoi_lux:TelephoneDirect", "N/A")
    }

    # Combine all fixed parts into a single dictionary
    fixed_parts = {
        "aeoi_lux:NameDepositor": NameDepositor,
        "aeoi_lux:PersonalIdentificationNumberDepositor": PersonalIdentificationNumberDepositor,
        "aeoi_lux:AddressDepositor": AddressDepositor,
        "aeoi_lux:PersonDepositor": person_depositor
    }
    return fixed_parts



def read_excel_tabs_dynamic(file_path):
    """
    Reads an Excel file and returns a dictionary where each key is a sanitized sheet name
    and the value is the corresponding DataFrame. It forces certain columns to be strings
    and applies .strip() to all string cells (to remove leading/trailing spaces).
    """
    import pandas as pd
    import re

    sheets_vars = {}
    try:
        # Force these columns to be read as strings
        dtype_dict = {
            "Luxembourg TIN of RFI": str,
            "TIN active NFE": str,
            "Account Number of account holder": str,
            "Account Number of account holder /CP": str,
            "TIN PP": str,
            "TIN of CP": str,
            "Account number reporting": str
        }

        # Read all sheets
        sheets_dict = pd.read_excel(file_path, sheet_name=None, dtype=dtype_dict)

        for sheet_name, df in sheets_dict.items():
            # Sanitize sheet name
            var_name = re.sub(r'\W|^(?=\d)', '_', sheet_name)

            # Strip all string-type cells only (vectorized & efficient)
            df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            # Replace all NaN values with empty strings
            df = df.fillna("")
            sheets_vars[var_name] = df

        return sheets_vars

    except Exception as e:
        logger.warning("Error reading Excel file: %s", type(e).__name__)
        return {}

    
def assign_template_tabs(sheets_dict):
    """
    Takes a dictionary of DataFrames (from an Excel file) and processes each sheet name
    by removing spaces and converting it to lowercase. Then, it assigns the DataFrame
    to one of the standard keys: "CPS", "Individual", or "Active" if that substring is found
    in the processed sheet name.

    Parameters:
        sheets_dict (dict): Dictionary with sheet names as keys and DataFrames as values.

    Returns:
        dict: A dictionary with the keys "CPS", "Individual", and "Active" (if detected)
              and their corresponding DataFrames.
    """
    template_tabs = {}
    for sheet_name, df in sheets_dict.items():
        # Remove spaces and convert to lowercase.
        processed_name = sheet_name.replace(" ", "").lower()
        if "cps" in processed_name:
            template_tabs["CPS"] = df
        elif "individual" in processed_name:
            template_tabs["Individual"] = df
        elif "active" in processed_name:
            template_tabs["Active"] = df
    return template_tabs

def find_available_tab(template_tabs):
    """
    Returns the first non-empty DataFrame among CPS, Active, or Individual (in that order).
    """
    for key in ["CPS", "Active", "Individual"]:
        if key in template_tabs and not template_tabs[key].empty:
            return template_tabs[key]
    return None


def transform_country_code(country_name):
    """
    Cherche le code pays (colonne "A-2") correspondant au nom de pays fourni (colonne "Country")
    dans l'un des deux fichiers suivants:
      - Reportable_Countries.xlsx
      - Additional list of countries.xlsx

    Si le pays est trouvé dans le premier fichier, la fonction renvoie son code.
    Sinon, elle cherche dans le second fichier.
    
    Parameters:
        country_name (str): Le nom du pays (ex. "Italy").

    Returns:
        str: Le code pays trouvé dans la colonne "A-2", ou None si non trouvé.
    """
    file_paths = [REPORTABLE_COUNTRIES_FILE, ADDITIONAL_COUNTRIES_FILE]
    
    for file in file_paths:
        try:
            # Assume the file uses the default sheet.
            df = pd.read_excel(file)
            # First, try to find the country by name in the "Country" column (case-insensitive).
            mask_name = df["Country"].str.lower() == country_name.strip().lower()
            if mask_name.any():
                code = df.loc[mask_name, "A-2"].iloc[0]
                return str(code).strip()
            # Otherwise, check if the provided country_name is already a valid country code in column "A-2"
            mask_code = df["A-2"].astype(str).str.strip() == country_name.strip()
            if mask_code.any():
                code = df.loc[mask_code, "A-2"].iloc[0]
                return str(code).strip()
        except Exception as e:
            logger.warning("Error reading file %s: %s", file, type(e).__name__)
    
    # If not found in any file, return the original country_name.
    return country_name

def country_code_to_name(alpha2_code):
    """
    Look up the full country name for a given ISO alpha‑2 code in your reference files.

    Parameters:
        alpha2_code (str): A 2‑letter country code (e.g. "IT").

    Returns:
        str: The matching country name from the "Country" column, or the original code if not found.
    """
    files = [REPORTABLE_COUNTRIES_FILE, ADDITIONAL_COUNTRIES_FILE]

    # Normalize the input
    key = str(alpha2_code).strip().lower()

    for fp in files:
        try:
            df = pd.read_excel(fp)
            # Ensure the A-2 column is treated as string
            codes = df["A-2"].astype(str).str.strip().str.lower()
            mask = codes == key
            if mask.any():
                # Return the first matching "Country" value
                return str(df.loc[mask, "Country"].iloc[0]).strip()
        except Exception:
            # If file is missing or corrupt, skip to the next
            continue

    # Fallback: if not found, just return what was passed in
    return alpha2_code

# Define helper function for company nickname extraction (used in both branches)
def get_company_nickname(entity_name):
    ignore_words = {
        "s.a.", "sa", "s.a", "s.a.s.", "sas", "s.a.r.l.", "sarl", "s.p.a.", "spa", 
        "a.g.", "ag", "a.s.", "as", "a.b.", "ab",
        "inc.", "inc", "incorporated", "incorp.",
        "ltd", "ltd.", "limited", "ltd liability", "ltd liab.",
        "llc", "llc.", "l.l.c.", "l.l.c",
        "corp", "corp.", "corporation", "corps", "corps.",
        "co.", "co", "company", "co. ltd", "co ltd", "co. limited", "co limited",
        "lp", "l.p.", "limited partnership", "llp", "l.l.p.", "limited liability partnership",
        "plc", "plc.", "public limited company",
        "gmbh", "g.m.b.h.", "scsp", "s.c.s.p.", "kgaa", "k.g.a.a.", "nv", "n.v.", "bv", "b.v.", 
        "pte ltd", "pte. ltd."
    }
    words = entity_name.split()
    cleaned_words = [word.lower().strip(".,;:()") for word in words]
    while cleaned_words and cleaned_words[-1] in ignore_words:
        words.pop()
        cleaned_words.pop()
    if not words:
        return entity_name[:3].upper()
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(word[0].upper() for word in words)


def create_RefId(available_tab, crs_fatca, version, tag="HL", DestCode="LU", tin="Luxembourg TIN of RFI"):
    """
    Creates a reference ID based on values extracted from the available_tab DataFrame,
    the CRS/FATCA selection, and the provided version (or in Active, the Account Number).
    
    For "FATCA", the function returns:
         version + "." + <Year> + "_" + tag + "_" + <RFI_Nickname> + <Year> + "F"
         
    For "CRS", it returns:
         "LU" + <Year> + transform_country_code(DestCode) +
         "_" + tag + "_" + <IdentificationNumber> +
         "M00000000_" + <RFI_Nickname> + <Year> + crs_fatca + version
         
    Parameters:
        available_tab (DataFrame): The DataFrame containing the tab data.
        crs_fatca (str): The CRS/FATCA selection (either "FATCA" or "CRS").
        version (str): The version string provided (or in Active, the Account Number).
        tag (str): A tag indicating the type of ID ("HL" for header, "AR" for account report, etc.).
        DestCode (str): The destination code (often from the "Country of residence of active" column).
        tin (str): The column name for the Luxembourg TIN.
        
    Returns:
        str: The generated reference ID.
        
    Raises:
        ValueError: If required values are missing or invalid.
    """
    import re  # in case not imported

    # Build a mapping of stripped column names to the actual column names.
    col_map = {col.strip(): col for col in available_tab.columns}

    # --- Extract the Year (common for both branches) ---
    # Always derive the four‐digit year from the Reporting period
    if "Reporting period" in col_map:
        vals = available_tab[col_map["Reporting period"]].dropna()
        if vals.empty:
            raise ValueError("No value found in 'Reporting period'.")
        year_int = int(float(vals.iloc[0]))
    else:
        raise ValueError("Neither 'Reporting period' nor usable year column found.")
    
    year_str = str(year_int)
    if not year_str.isdigit() or len(year_str) != 4:
        raise ValueError("The extracted year is not a valid 4-digit year.")

    # --- Check crs_fatca early ---
    crs_fatca_upper = crs_fatca.upper()
    if crs_fatca_upper not in {"CRS", "FATCA"}:
        raise ValueError("crs_fatca must be either 'CRS' or 'FATCA'")

    # --- Extract Reporting Financial Institution's name (needed in both branches) ---
    if "Name of Reporting Financial Institution (RFI)" not in col_map:
        raise ValueError("No value found in 'Name of Reporting Financial Institution (RFI)'.")
    rfi_vals = available_tab[col_map["Name of Reporting Financial Institution (RFI)"]].dropna().unique()
    if len(rfi_vals) == 0:
        raise ValueError("No value found in 'Name of Reporting Financial Institution (RFI)'.")
    rfi_name = str(rfi_vals[0]).strip()
    rfi_nickname = get_company_nickname(rfi_name)
    try:
        GIINofRFI = str(available_tab.get(col_map.get("GIIN of RFI"), pd.Series()).dropna().iloc[0]).strip() if not available_tab.get(col_map.get("GIIN of RFI"), pd.Series()).dropna().empty else ""
    except KeyError as e:
        pass

    # --- Process based on crs_fatca ---
    if crs_fatca_upper == "FATCA":
        # Minimal processing for FATCA: only use year and RFI nickname.
        ref_id = GIINofRFI + "." + year_str + "_" + tag + "_" + rfi_nickname + year_str + "F" + version
        return ref_id
    else:
        # For CRS: continue with TIN extraction and full reference ID creation.
        tin_key = tin.strip()
        if tin_key not in col_map:
            raise ValueError(f"No value found in '{tin}'.")
        tin_vals = available_tab[col_map[tin_key]].dropna().unique()
        if len(tin_vals) == 0:
            raise ValueError(f"No value found in '{tin}'.")
        tin_raw = str(tin_vals[0]).strip()
        if "." in tin_raw:
            identification = tin_raw.split(".")[0]
        else:
            identification = tin_raw

        # If TIN is empty or equals "notprovided" (ignoring spaces and case), set to "#NTA001#"
        identification = process_tin(identification)

        
        # Create RefId
        ref_id = (
            "LU" + year_str + transform_country_code(DestCode) +
            "_" + tag + "_" + identification +
            "M00000000_" + rfi_nickname +
            year_str + crs_fatca + version
        )
        return ref_id


def process_tin(identification):
    """
    Process a TIN (Tax Identification Number) value and returns a standardized version.
    
    If the identification meets any of these conditions:
      - After removing spaces and converting to lowercase, it equals "notprovided"
      - It is an empty string
      - It is considered a missing value (NaN) by pandas
      - It equals "nan" (case-insensitive)
      - It equals "NaN"
      - It equals "0"
      
    then the function returns "#NTA001#". Otherwise, it returns the original identification.
    
    Parameters:
      identification: The TIN value (can be of any type convertible to string).
    
    Returns:
      A processed TIN string.
    """
    identification = str(identification).strip()
    
    # Check if identification is missing or "not provided"
    if (identification.replace(" ", "").lower() == "notprovided" or
        identification == "" or
        pd.isna(identification) or
        identification.lower() == "nan" or
        identification == "NaN" or
        identification == "0"):
        return "#NTA001#"
    
    return identification

def get_payment(row, col_name, payment_type, curr_code):
    try:
        # Check that the column exists, is not NaN, and is not an empty string
        if col_name in row and not pd.isna(row[col_name]) and str(row[col_name]).strip():
            value = float(row[col_name])
            value = np.maximum(0.0, value)          # Ensure negative amounts are set to zero
        else:
            value = 0.0
    except Exception:                        # Catches KeyError, ValueError, TypeError, etc.
        value = 0.0

    return {
        "crs:Type": payment_type,
        "crs:PaymentAmnt": {
            "@currCode": curr_code,
            "#text": f"{value:.2f}"          # Always format with two decimal places
        }
    }


def get_payment_fatca(row, col_name, payment_type, curr_code):
    try:
        # Check that the column exists, is not NaN, and is not an empty string
        if col_name in row and not pd.isna(row[col_name]) and str(row[col_name]).strip():
            value = float(row[col_name])
            value = np.maximum(0.0, value)          # Same logic: prevent negative amounts
        else:
            value = 0.0
    except Exception:
        value = 0.0

    return {
        "fatca:Type": payment_type,
        "fatca:PaymentAmnt": {
            "@currCode": curr_code,
            "#text": f"{value:.2f}"          # Always format with two decimal places
        }
    }


def reportable_countries(account_reports):
    """
    For each account report (a dict), if the key "ReportableCountry" is not set,
    attempt to derive it from the RawData DataFrame by checking, in order:
      - "Tax residence of Active"
      - "Tax residence of PP"
      - "Tax residence of CP"
      - "Tax residence of AH"
    If the obtained value is "LU" (Luxembourg) or empty, do not include it.
    Returns a sorted list of unique reportable country codes.
    """
    for report in account_reports:
        if not report.get("ReportableCountry"):
            if "RawData" in report and hasattr(report["RawData"], "columns"):
                df = report["RawData"]
                # Try the columns in order
                if "Tax residence of Active" in df.columns and pd.notna(df.iloc[0]["Tax residence of Active"]):
                    rc = str(df.iloc[0]["Tax residence of Active"]).strip()
                elif "Tax residence of PP" in df.columns and pd.notna(df.iloc[0]["Tax residence of PP"]):
                    rc = str(df.iloc[0]["Tax residence of PP"]).strip()
                elif "Tax residence of CP" in df.columns and pd.notna(df.iloc[0]["Tax residence of CP"]):
                    rc = str(df.iloc[0]["Tax residence of CP"]).strip()
                elif "Tax residence of AH" in df.columns and pd.notna(df.iloc[0]["Tax residence of AH"]):
                    rc = str(df.iloc[0]["Tax residence of AH"]).strip()
                else:
                    rc = ""
                # Do not use "LU" (Luxembourg) as reportable.
                report["ReportableCountry"] = rc if rc.upper() != "LU" and rc != "" else None
    # Get unique non-None countries.
    unique = sorted({report["ReportableCountry"] for report in account_reports if report.get("ReportableCountry")})
    return unique

def get_reportable_countries_for_year(year, reportable_countries_path):
    """
    Reads the Excel file at 'reportable_countries_path',
    filters rows where the 'Year' column <= the given 'year',
    and returns a set of country codes from the 'A-2' column.
    
    For example, if the Excel has columns:
        'A-2' (the ISO code or short code)
        'Country' (the name)
        'Year' (the earliest year it becomes reportable)
    then we do something like:
    
        df = pd.read_excel(reportable_countries_path)
        # keep only rows with Year <= year
        df_filtered = df[df["Year"] <= year]
        # return a set of the A-2 codes
        return set(df_filtered["A-2"].unique())
    """
    import pandas as pd
    
    df = pd.read_excel(reportable_countries_path)
    # Filter for rows whose 'Year' <= year
    df_filtered = df[df["Year"] <= year]
    # Return a set of the codes in column 'A-2'
    allowed_codes = set(df_filtered["A-2"].astype(str).str.strip())
    return allowed_codes


def create_CRS_DataReport_Initial_XML(depositor_info, CPS_info,
                   active_accounts, individual_accounts,
                   controlling_accounts, passive_accounts,
                   report_type, selection, version, reportable_countries_path):
    """
    Constructs the final CRS XML.
    
    Steps:
      1. Gather all account reports from active, individual, controlling, and passive sections.
      2. Group the account reports by their ReportableCountry (if a valid non-empty, non-"LU" value exists).
      3. For each group, create a <crs:CrsBody> block. In that block, include a header
         <crs:ReportingFI> that contains a <crs:DocSpec> with tag "RF". Its DocRefId is generated by
         calling create_RefId using the CPS_info’s RawData (or a dummy fallback) and with DestCode equal to the country.
      4. Build the final XML dictionary with the required header fields and the ReportContent.
      
    Note: Any extraneous keys (like RawData, BeaconVersion, etc.) are omitted.
    """
    import pandas as pd

    # 1. Gather all account reports from the sections.
    account_reports = []
    for section in [active_accounts, individual_accounts, controlling_accounts, passive_accounts]:
        if section and isinstance(section, list):
            account_reports.extend(section)
    
    # 2. Group account reports by ReportableCountry.
    # Do not default to "LU"; only include accounts that have a valid reportable country (non-empty and not "LU").
    grouped_reports = {}
    for item in account_reports:
        acct_report = item.get("crs:AccountReport", {})
        country = acct_report.pop("ReportableCountry", None)
        if country and country.upper() != "LU":
            grouped_reports.setdefault(country, []).append(acct_report)
            logger.debug(country)
    
    # 3. Build a <crs:CrsBody> for each country group.
    crs_bodies = []
    message_type = CPS_info.get("MessageType", "CRS").upper()
    # Note: For CRS, get allowed reportable countries based on the ReportingPeriod year.
    # We assume the ReportingPeriod is in the format "YYYY-...". Convert its year to int.
    try:
        rep_year_int = int(CPS_info.get("ReportingPeriod").split("-")[0])
    except Exception:
        rep_year_int = 2023
    allowed_country_codes = (get_reportable_countries_for_year(rep_year_int, reportable_countries_path)
                               if message_type == "CRS" else ["US"])
    
    # Prepare a DataFrame for create_RefId from CPS_info["RawData"] if available; otherwise, use a fallback.
    available_tab = CPS_info.get("RawData")
    if available_tab is None:
        available_tab = pd.DataFrame([{"Year following reporting period": "2024"}])
    
    # Determine the DocTypeIndic for the RF header.
    if report_type == "Zero Report":
        doc_type_indic_rf = "OECD0"
    else:
        doc_type_indic_rf = "OECD1" if selection == "Initial" else "OECD2"
    
    # The TIN column remains as defined in create_RefId.
    tin_column = "Luxembourg TIN of RFI"
    
    for country, reports in grouped_reports.items():
        # Skip if the reportable country is not in the allowed list.
        if message_type == "CRS":
            if country not in allowed_country_codes:
                continue
        
        # 3a. Create the header DocSpec for this country (tag "RF")
        doc_ref_id_rf = create_RefId(
            available_tab,
            CPS_info.get("MessageType", "CRS"),
            version,
            tag="RF",
            DestCode=country,  # use the actual reportable country
            tin=tin_column
        )
        doc_spec_rf = {
            "crsstf:DocTypeIndic": doc_type_indic_rf,
            "crsstf:DocRefId": doc_ref_id_rf
        }
        
        # 3b. Build the ReportingFI header for this group.
        # Per your instructions, this header always uses LU for the institutional details.
        reporting_fi_group = {
            "crs:ResCountryCode": "LU",
            "crs:IN": {
                "@issuedBy": CPS_info.get("issuedBy", "LU"),
                "#text": CPS_info.get("IN", "")
            },
            "crs:Name": CPS_info.get("NameReportingFI", ""),
            "crs:Address": {
                "commontypesfatcacrs:CountryCode": "LU",
                "commontypesfatcacrs:AddressFix": {
                    "commontypesfatcacrs:Street": CPS_info.get("AddressFix", {}).get("Street", ""),
                    "commontypesfatcacrs:BuildingIdentifier": CPS_info.get("AddressFix", {}).get("BuildingIdentifier", ""),
                    "commontypesfatcacrs:PostCode": CPS_info.get("AddressFix", {}).get("PostCode", ""),
                    "commontypesfatcacrs:City": CPS_info.get("AddressFix", {}).get("City", ""),
                    "commontypesfatcacrs:SuiteIdentifier": CPS_info.get("SuiteIdentifier", "")
                }
            },
            "crs:DocSpec": doc_spec_rf
        }
        
        crs_body = {
            "crs:ReportingFI": reporting_fi_group,
            "crs:ReportingGroup": {
                "crs:AccountReport": reports
            }
        }
        crs_bodies.append(crs_body)
    
    # 4. Build the final XML dictionary.
    final_dict = {
        "aeoi_lux_crs:AEOI_LUX": {
            "@xmlns:crs": "urn:oecd:ties:crs:v2",
            "@xmlns:aeoi_lux_crs": "urn:lu:etat:acd:aeoi_crs:v2.0",
            "@xmlns:aeoi_crs": "urn:lu:etat:acd:aeoi_crs:v2.0",
            "@xmlns:commontypesfatcacrs": "urn:oecd:ties:commontypesfatcacrs:v2",
            "@xmlns:aeoi_lux": "urn:lu:etat:acd:aeoi_lux:v3.0",
            "@xmlns:crsstf": "urn:oecd:ties:crsstf:v5",
            "@xmlns:fatca": "urn:oecd:ties:fatca:v1",
            "aeoi_crs:AEOI_CRS": {
                "aeoi_crs:AEOI_RefId": CPS_info.get("AEOI_RefId", ""),
                "aeoi_crs:AEOI_Depositor": depositor_info,
                "aeoi_crs:AEOI_ReportingFI": {
                    "aeoi_lux:NameReportingFI": CPS_info.get("NameReportingFI", ""),
                    "aeoi_lux:IdentificationNumber": CPS_info.get("IdentificationNumber", ""),
                    "aeoi_lux:IdentificationNumberExtension": CPS_info.get("IdentificationNumberExtension", ""),
                    "aeoi_lux:AddressReportingFI": CPS_info.get("AddressReportingFI", {}),
                    "aeoi_lux:PointOfContactReportingFI": {
                        "aeoi_lux:Name": CPS_info.get("PointOfContactReportingFI", {}).get("Name", ""),
                        "aeoi_lux:FirstName": CPS_info.get("PointOfContactReportingFI", {}).get("FirstName", ""),
                        "aeoi_lux:EmailPersonal": CPS_info.get("PointOfContactReportingFI", {}).get("EmailPersonal", ""),
                        "aeoi_lux:EmailOrganisation": CPS_info.get("PointOfContactReportingFI", {}).get("EmailOrganisation", ""),
                        "aeoi_lux:TelephoneDirect": CPS_info.get("PointOfContactReportingFI", {}).get("TelephoneDirect", "")
                    }
                },
                "aeoi_crs:RFI_Identifier": CPS_info.get("RFI_Identifier", ""),
                "aeoi_crs:ReportContent": {
                    "crs:CRS_OECD": {
                        "crs:MessageSpec": {
                            "crs:SendingCompanyIN": CPS_info.get("SendingCompanyIN", ""),
                            "crs:TransmittingCountry": CPS_info.get("TransmittingCountry", ""),
                            "crs:ReceivingCountry": CPS_info.get("ReceivingCountry", ""),
                            "crs:MessageType": CPS_info.get("MessageType", ""),
                            "crs:MessageRefId": CPS_info.get("MessageRefId", ""),
                            "crs:MessageTypeIndic": CPS_info.get("MessageTypeIndic", ""),
                            "crs:ReportingPeriod": CPS_info.get("ReportingPeriod", ""),
                            "crs:Timestamp": CPS_info.get("Timestamp", "")
                        },
                        "crs:CrsBody": crs_bodies
                    }
                }
            }
        }
    }
    return final_dict


def create_FATCA_DataReport_Initial_XML(depositor_info, CPS_info,
                                          active_accounts, individual_accounts,
                                          controlling_accounts, passive_accounts,
                                          report_type, selection, version, filer_category,
                                          reportable_countries_path=REPORTABLE_COUNTRIES_FILE):
    """
    Constructs the final FATCA XML.
    
    Steps:
      1. Gather all account reports from active, individual, controlling, and passive sections.
      2. Group the account reports by their ReportableCountry (if a valid non-empty, non-"LU" value exists).
      3. For each group, create a FATCA body block. In that block, include a header 
         <fatca:ReportingFI> that contains a <fatca:DocSpec> with tag "RF". Its DocRefId is generated by
         calling create_RefId using CPS_info’s RawData (or a fallback) and with DestCode equal to the country.
      4. Build the final XML dictionary with the required header fields and the ReportContent.
    
    Note:
      The DocTypeIndic is determined as:
          ("OECD1" if (report_type == "Zero Report" or selection == "Initial") else "OECD2")
          if message_type.upper() == "CRS" else ("FATCA1" if selection == "Initial" else "FATCA2")
      For FATCA messages this yields "FATCA1" or "FATCA2".
      For now, create_RefId is used as-is.
    """
    import pandas as pd

    # 1. Gather all account reports from the sections.
    account_reports = []
    for section in [active_accounts, individual_accounts, controlling_accounts, passive_accounts]:
        if section and isinstance(section, list):
            account_reports.extend(section)
    
    # 2. Group account reports by ReportableCountry.
    grouped_reports = {}
    for item in account_reports:
        # In FATCA output the key is "fatca:AccountReport"
        acct_report = item.get("fatca:AccountReport", {})
        country = acct_report.pop("ReportableCountry", None)
        if country and country.upper() != "LU":
            grouped_reports.setdefault(country, []).append(acct_report)
    
    # 3. Build a FATCA body for each country group.
    fatca_body = {}
    message_type = CPS_info.get("MessageType", "FATCA").upper()
    try:
        rep_year_int = int(CPS_info.get("ReportingPeriod").split("-")[0])
    except Exception:
        rep_year_int = 2023
    allowed_country_codes = ["US"]
    
    available_tab = CPS_info.get("RawData")
    if available_tab is None:
        available_tab = pd.DataFrame([{"Year following reporting period": "2024"}])
    
    # Determine the DocTypeIndic for the header.
    doc_type_indic_rf = (
        ("OECD1" if (report_type == "Zero Report" or selection == "Initial") else "OECD2")
        if message_type == "CRS" else
        ("FATCA1" if selection == "Initial" else "FATCA2")
    )
    
    tin_column = "Luxembourg TIN of RFI"
    
    # Process only one allowed country group (e.g., US)
    for country, reports in grouped_reports.items():
        if country not in allowed_country_codes:
            continue
        
        # 3a. Create the header DocSpec for this country (tag "RF")
        doc_ref_id_rf = create_RefId(
            available_tab,
            CPS_info.get("MessageType", "FATCA"),
            version,
            tag="RF",
            DestCode=country,
            tin=tin_column
        )
        doc_spec_rf = {
            "fatca:DocTypeIndic": doc_type_indic_rf,
            "fatca:DocRefId": doc_ref_id_rf
        }
        
        # 3b. Build the ReportingFI header for this group using stffatcatypes keys.
        # For the address, we now assume CPS_info["AddressFix"] has keys: "Street", "BuildingIdentifier", "PostCode", "City"
        reporting_fi_group = {
            "stffatcatypes:ResCountryCode": "LU",
            "stffatcatypes:TIN": {
                "@issuedBy": "US",
                "#text": CPS_info.get("GIINofRFI", "")
            },
            "stffatcatypes:Name": CPS_info.get("NameReportingFI", ""),
            "stffatcatypes:Address": {
                "stffatcatypes:CountryCode": "LU",
                "stffatcatypes:AddressFix": {
                    "stffatcatypes:Street": CPS_info.get("AddressFix", {}).get("Street", ""),
                    "stffatcatypes:BuildingIdentifier": CPS_info.get("AddressFix", {}).get("BuildingIdentifier", ""),
                    "stffatcatypes:PostCode": CPS_info.get("AddressFix", {}).get("PostCode", ""),
                    "stffatcatypes:City": CPS_info.get("AddressFix", {}).get("City", "")
                }
            },
            "fatca:FilerCategory": filer_category.split(" - ")[0],
            "fatca:DocSpec": doc_spec_rf
        }
        
        fatca_body = {
            "fatca:ReportingFI": reporting_fi_group,
            "fatca:ReportingGroup": {
                "fatca:AccountReport": reports
            }
        }
        # Process only one allowed country group (e.g., US)
        break
    
    # 4. Process each account report's account number (pad single-digit numbers).
    for report in account_reports:
        if "fatca:AccountNumber" in report:
            raw = str(report["fatca:AccountNumber"]).strip()
            processed = (lambda s: ("0" + s) if len(s) == 1 else s)(
                (lambda s: s[:-2] if s.endswith(".0") else s)(raw)
            )
            report["fatca:AccountNumber"] = processed
    
    # 5. Build the final XML dictionary.
    # Ensure that the AddressReportingFI and PointOfContactReportingFI dictionaries have their keys properly prefixed.
    # For AddressReportingFI: expected keys are "aeoi_lux:StreetPhysical", "aeoi_lux:NumberPhysical", "aeoi_lux:PostalCodePhysical", "aeoi_lux:CityPhysical", "aeoi_lux:CountryPhysical".
    # For PointOfContactReportingFI: expected keys are "aeoi_lux:Name", "aeoi_lux:FirstName", "aeoi_lux:EmailPersonal", "aeoi_lux:EmailOrganisation", "aeoi_lux:TelephoneDirect".
    # Here we assume that CPS_info already provides these dictionaries with the proper keys. If not, you may wrap them accordingly.
    # 5. Build the final XML dictionary.
    final_dict = {
        "aeoi_lux_fatca:AEOI_LUX": {
            "@xmlns:aeoi_lux_fatca": "urn:lu:etat:acd:aeoi_fatca:v3.0",
            "@xmlns:stffatcatypes": "urn:oecd:ties:stffatcatypes:v2",
            "@xmlns:aeoi_lux": "urn:lu:etat:acd:aeoi_lux:v3.0",
            "@xmlns:fatca": "urn:lu:etat:acd:fatca:v2.0",
            "aeoi_lux_fatca:AEOI_FATCA": {
                "aeoi_lux_fatca:AEOI_RefId": CPS_info.get("AEOI_RefId", ""),
                "aeoi_lux_fatca:AEOI_Depositor": depositor_info,
                "aeoi_lux_fatca:AEOI_ReportingFI": {
                    "aeoi_lux:NameReportingFI": CPS_info.get("NameReportingFI", ""),
                    "aeoi_lux:IdentificationNumber": CPS_info.get("IdentificationNumber", ""),
                    "aeoi_lux:IdentificationNumberExtension": CPS_info.get("IdentificationNumberExtension", ""),
                    "aeoi_lux:AddressReportingFI": CPS_info.get("AddressReportingFI", {}),
                    "aeoi_lux:PointOfContactReportingFI": {
                        "aeoi_lux:Name": CPS_info.get("PointOfContactReportingFI", {}).get("Name", ""),
                        "aeoi_lux:FirstName": CPS_info.get("PointOfContactReportingFI", {}).get("FirstName", ""),
                        "aeoi_lux:EmailPersonal": CPS_info.get("PointOfContactReportingFI", {}).get("EmailPersonal", ""),
                        "aeoi_lux:EmailOrganisation": CPS_info.get("PointOfContactReportingFI", {}).get("EmailOrganisation", ""),
                        "aeoi_lux:TelephoneDirect": CPS_info.get("PointOfContactReportingFI", {}).get("TelephoneDirect", "")
                    }
                },
                "aeoi_lux_fatca:RFI_Identifier": CPS_info.get("GIINofRFI", ""),
                "aeoi_lux_fatca:ReportContent": {
                    "aeoi_lux_fatca:ReportingPeriod": CPS_info.get("ReportingPeriod", ""),
                    "fatca:FATCA_LUX": {
                        "fatca:MessageSpec": {
                            "stffatcatypes:SendingCompanyIN": CPS_info.get("GIINofRFI", ""),
                            "stffatcatypes:TransmittingCountry": CPS_info.get("TransmittingCountry", ""),
                            "stffatcatypes:ReceivingCountry": CPS_info.get("ReceivingCountry", ""),
                            "stffatcatypes:MessageType": CPS_info.get("MessageType", ""),
                            "stffatcatypes:MessageRefId": CPS_info.get("MessageRefId", "").replace("_HC_", "_HF_"),
                            "stffatcatypes:ReportingPeriod": CPS_info.get("ReportingPeriod", ""),
                            "stffatcatypes:Timestamp": CPS_info.get("Timestamp", "")
                        },
                        "fatca:FATCA": fatca_body
                    }
                }
            }
        }
    }
    return final_dict


def create_zero_report_crs_xml(CPS, postal_code_path, crs_fatca, version, report_type, selection, user):
    """
    Constructs a CRS Zero Report (Initial) XML using CPS data.
    
    If CPS is a DataFrame, it calls get_info_CPS to extract the reporting information.
    If CPS is already a dictionary (i.e. CPS_info), then that dictionary is used directly.
    
    It also uses process_fixed_parts to get the fixed depositor information.
    Header IDs are created using create_RefId with tag "HL" for AEOI_RefId and "HC" for MessageRefId.
    
    For a Zero Report, the <crs:CrsBody> contains an empty ReportingGroup.
    
    Returns:
        dict: The final XML dictionary with exactly one root key.
    """
    from .core_functions_begin import get_info_CPS

    # If CPS is a DataFrame, extract info; otherwise, assume it is already CPS_info.
    if isinstance(CPS, pd.DataFrame):
        CPS_info = get_info_CPS(CPS, postal_code_path, crs_fatca, version, report_type, selection)
    else:
        CPS_info = CPS

    # Get fixed depositor info from the selected user.
    fixed_parts = process_fixed_parts(user)
    
    # Create the header reference IDs using create_RefId:
    aeoi_ref_id = create_RefId(CPS_info.get("RawData", CPS_info), crs_fatca, version, tag="HL")
    OECD_message_ref_id = create_RefId(CPS_info.get("RawData", CPS_info), crs_fatca, version, tag="HC")
    message_ref_id = create_RefId(CPS_info.get("RawData", CPS_info), crs_fatca, version, tag="RF")
    
    # Build the final XML dictionary.
    # For a Zero Report, we assume there are no account report bodies.
    final_dict = {
        "aeoi_lux_crs:AEOI_LUX": {
            "@xmlns:crs": "urn:oecd:ties:crs:v2",
            "@xmlns:aeoi_lux_crs": "urn:lu:etat:acd:aeoi_crs:v2.0",
            "@xmlns:aeoi_crs": "urn:lu:etat:acd:aeoi_crs:v2.0",
            "@xmlns:commontypesfatcacrs": "urn:oecd:ties:commontypesfatcacrs:v2",
            "@xmlns:aeoi_lux": "urn:lu:etat:acd:aeoi_lux:v3.0",
            "@xmlns:crsstf": "urn:oecd:ties:crsstf:v5",
            "@xmlns:fatca": "urn:oecd:ties:fatca:v1",
            "aeoi_crs:AEOI_CRS": {
                "aeoi_crs:AEOI_RefId": aeoi_ref_id,
                "aeoi_crs:AEOI_Depositor": fixed_parts,
                "aeoi_crs:AEOI_ReportingFI": {
                    "aeoi_lux:NameReportingFI": CPS_info.get("NameReportingFI", ""),
                    "aeoi_lux:IdentificationNumber": CPS_info.get("IdentificationNumber", ""),
                    "aeoi_lux:IdentificationNumberExtension": CPS_info.get("IdentificationNumberExtension", "M00000000"),
                    "aeoi_lux:AddressReportingFI": CPS_info.get("AddressReportingFI", {}),
                    "aeoi_lux:PointOfContactReportingFI": {
                        "aeoi_lux:Name": CPS_info.get("PointOfContactReportingFI", {}).get("Name", ""),
                        "aeoi_lux:FirstName": CPS_info.get("PointOfContactReportingFI", {}).get("FirstName", ""),
                        "aeoi_lux:EmailPersonal": CPS_info.get("PointOfContactReportingFI", {}).get("EmailPersonal", ""),
                        "aeoi_lux:EmailOrganisation": CPS_info.get("PointOfContactReportingFI", {}).get("EmailOrganisation", ""),
                        "aeoi_lux:TelephoneDirect": CPS_info.get("PointOfContactReportingFI", {}).get("TelephoneDirect", "")
                    }
                },
                "aeoi_crs:RFI_Identifier": CPS_info.get("RFI_Identifier", ""),
                "aeoi_crs:ReportContent": {
                    "crs:CRS_OECD": {
                        "crs:MessageSpec": {
                            "crs:SendingCompanyIN": CPS_info.get("SendingCompanyIN", ""),
                            "crs:TransmittingCountry": CPS_info.get("TransmittingCountry", "LU"),
                            "crs:ReceivingCountry": CPS_info.get("ReceivingCountry", "LU"),
                            "crs:MessageType": CPS_info.get("MessageType", "CRS"),
                            "crs:MessageRefId": OECD_message_ref_id,
                            "crs:MessageTypeIndic": "CRS703",  # For Zero Report (Initial)
                            "crs:ReportingPeriod": CPS_info.get("ReportingPeriod", ""),
                            "crs:Timestamp": CPS_info.get("Timestamp", "")
                        },
                        "crs:CrsBody": [
                            {
                                "crs:ReportingFI": {
                                    "crs:ResCountryCode": "LU",
                                    "crs:IN": {"@issuedBy": "LU", "#text": CPS_info.get("IN", "")},
                                    "crs:Name": CPS_info.get("NameReportingFI", ""),
                                    "crs:Address": {
                                        "commontypesfatcacrs:CountryCode": "LU",
                                        "commontypesfatcacrs:AddressFix": {
                                            "commontypesfatcacrs:Street": CPS_info.get("AddressFix", {}).get("Street", ""),
                                            "commontypesfatcacrs:BuildingIdentifier": CPS_info.get("AddressFix", {}).get("BuildingIdentifier", ""),
                                            "commontypesfatcacrs:PostCode": CPS_info.get("AddressFix", {}).get("PostCode", ""),
                                            "commontypesfatcacrs:City": CPS_info.get("AddressFix", {}).get("City", ""),
                                            "commontypesfatcacrs:SuiteIdentifier": CPS_info.get("SuiteIdentifier", "")
                                        }
                                    },
                                    "crs:DocSpec": {
                                        "crsstf:DocTypeIndic": "OECD1",  # No specific DocTypeIndic for zero report header
                                        "crsstf:DocRefId": message_ref_id
                                    }
                                },
                                "crs:ReportingGroup": {}  # Empty ReportingGroup for Zero Report
                            }
                        ]
                    }
                }
            }
        }
    }
    return final_dict


def create_zero_report_fatca_xml(CPS, postal_code_path, crs_fatca, version, report_type, selection, user):
    """
    Constructs a FATCA Zero Report (Initial) XML using CPS data.
    
    If CPS is a DataFrame, it calls get_info_CPS to extract the reporting information.
    If CPS is already a dictionary (i.e. CPS_info), then that dictionary is used directly.
    
    It also uses process_fixed_parts to get the fixed depositor information.
    Header IDs are created using a different convention for FATCA:
      AEOI_RefId = GIIN + "." + year + "_HL_" + company_nickname + year + "F0"
      RFI_Identifier = version
      
    For a Zero Report, no account report bodies are included.
    
    Returns:
        dict: The final XML dictionary with exactly one root key.
    """
    from .core_functions_begin import get_info_CPS

    # If CPS is a DataFrame, extract CPS_info; otherwise, assume it is already CPS_info.
    if isinstance(CPS, pd.DataFrame):
        CPS_info = get_info_CPS(CPS, postal_code_path, crs_fatca, version, report_type, selection)
    else:
        CPS_info = CPS

    # Get fixed depositor info from the selected user.
    fixed_parts = process_fixed_parts(user)

    # Compute the year from the ReportingPeriod (assumed to be in the format "YYYY-...").
    year = int(CPS_info.get("ReportingPeriod").split("-")[0])

    # Get GIIN of RFI
    GIIN_of_RFI = CPS_info.get("GIINofRFI", "")
    
    # Compute the company nickname.
    # (Assume that CPS_info already contains "CompanyNickname" or compute from the institution name.)
    company_nickname = get_company_nickname(CPS_info.get("NameReportingFI"))

    # Build the AEOI_RefId using the required format:
    # version + "." + year + "_HL_" + company_nickname + year + "F0"
    aeoi_ref_id = f"{GIIN_of_RFI}.{year}_HL_{company_nickname}{year}F0"
    
    # For a zero report, we do not include account report bodies.
    # The RFI_Identifier for FATCA in this beacon is simply set to the version.
    final_dict = {
        "aeoi_lux_fatca:AEOI_LUX": {
            "@xmlns:aeoi_lux_fatca": "urn:lu:etat:acd:aeoi_fatca:v3.0",
            "@xmlns:stffatcatypes": "urn:oecd:ties:stffatcatypes:v2",
            "@xmlns:aeoi_lux": "urn:lu:etat:acd:aeoi_lux:v3.0",
            "@xmlns:fatca": "urn:lu:etat:acd:fatca:v2.0",
            "aeoi_lux_fatca:AEOI_FATCA": {
                "aeoi_lux_fatca:AEOI_RefId": aeoi_ref_id,
                "aeoi_lux_fatca:AEOI_Depositor": fixed_parts,
                "aeoi_lux_fatca:AEOI_ReportingFI": {
                    "aeoi_lux:NameReportingFI": CPS_info.get("NameReportingFI", ""),
                    "aeoi_lux:IdentificationNumber": CPS_info.get("IdentificationNumber", ""),
                    "aeoi_lux:IdentificationNumberExtension": CPS_info.get("IdentificationNumberExtension", "M00000000"),
                    "aeoi_lux:AddressReportingFI": CPS_info.get("AddressReportingFI", {}),
                    "aeoi_lux:PointOfContactReportingFI": {
                        "aeoi_lux:Name": CPS_info.get("PointOfContactReportingFI", {}).get("Name", ""),
                        "aeoi_lux:FirstName": CPS_info.get("PointOfContactReportingFI", {}).get("FirstName", ""),
                        "aeoi_lux:EmailPersonal": CPS_info.get("PointOfContactReportingFI", {}).get("EmailPersonal", ""),
                        "aeoi_lux:EmailOrganisation": CPS_info.get("PointOfContactReportingFI", {}).get("EmailOrganisation", ""),
                        "aeoi_lux:TelephoneDirect": CPS_info.get("PointOfContactReportingFI", {}).get("TelephoneDirect", "")
                    }
                },
                "aeoi_lux_fatca:RFI_Identifier": CPS_info.get("GIINofRFI", ""),
                "aeoi_lux_fatca:ReportContent": {
                    "aeoi_lux_fatca:ReportingPeriod": CPS_info.get("ReportingPeriod", ""),
                    "aeoi_lux_fatca:ZeroReporting": "true"
                }
            }
        }
    }
    return final_dict


import math
import xml.etree.ElementTree as ET

import logging

logger = logging.getLogger(__name__)


def dict_to_element(tag, d):
    """
    Recursively build an ElementTree Element from a dictionary or value.

    - If d is not a dict, it is treated as a leaf value.
      • float NaN values become empty strings.
      • All other values are cast to str.
    - If d is a dict:
      • Keys starting with '@' define attributes.
      • A '#text' key defines the element's text content.
      • Other keys define child elements; list values generate multiple children.

    Empty or missing numeric data (NaN) will be output as "" rather than "nan".
    """
    # Create the XML element with the exact tag (including any namespace prefix).
    elem = ET.Element(tag)

    # --- Leaf node case: d is not a dict ---
    if not isinstance(d, dict):
        if isinstance(d, float) and math.isnan(d):
            # Represent NaN as empty string
            elem.text = ""
        else:
            # Convert all other values to string
            elem.text = str(d)
        return elem

    # --- Attribute handling ---
    # Any key starting with '@' becomes an XML attribute
    for key, val in d.items():
        if key.startswith("@"):
            attr_name = key[1:]  # drop the '@' prefix
            if isinstance(val, float) and math.isnan(val):
                # NaN attributes become empty string
                elem.attrib[attr_name] = ""
            else:
                elem.attrib[attr_name] = str(val)

    # --- Text content handling ---
    if "#text" in d:
        text_val = d["#text"]
        if isinstance(text_val, float) and math.isnan(text_val):
            # Represent NaN text as empty string
            elem.text = ""
        else:
            # Cast text content to string
            elem.text = str(text_val)

    # --- Child elements handling ---
    for key, val in d.items():
        # Skip attributes and text, already handled
        if key.startswith("@") or key == "#text":
            continue

        # If the value is a list, generate a child for each item
        if isinstance(val, list):
            for item in val:
                child = dict_to_element(key, item)
                elem.append(child)
        else:
            # Single child element
            child = dict_to_element(key, val)
            elem.append(child)

    return elem


def dict_to_xml_str(data_dict):
    """
    Convert a nested dictionary 'data_dict' to an XML string using our custom dict_to_element.
    """
    # data_dict is expected to have a single root key, e.g. {"aeoi_lux_crs:AEOI_LUX": {...}}
    if len(data_dict) != 1:
        raise ValueError("Dictionary must have exactly one root key.")
    root_tag = list(data_dict.keys())[0]
    root_val = data_dict[root_tag]

    root_elem = dict_to_element(root_tag, root_val)

    # Convert the ElementTree to a string
    import xml.etree.ElementTree as ET
    rough_string = ET.tostring(root_elem, encoding="utf-8")
    # For pretty printing, we can use minidom:
    import xml.dom.minidom
    reparsed = xml.dom.minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
