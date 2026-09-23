# core_functions_individual.py
import pandas as pd
import re
import numpy as np
from datetime import datetime
from .core_functions import create_RefId, transform_country_code, get_payment, get_payment_fatca, process_tin

def get_info_Individual(individual_df, report_type, selection, crs_fatca="CRS"):
    """
    Processes all rows from the Individual tab DataFrame and returns a list of dictionaries,
    one for each account.
    
    The key change here is that the destination country (for generating the DocRefId) and the
    residence country in the account holder are taken exclusively from the column 
    "Tax residence of PP". If that value is missing or blank, it will be an empty string.
    
    Payment amounts are converted to float, rounded to the nearest integer, then to a string;
    if a payment value is missing, it is set to "0.00".
    """
    results = []

    # --- Determine the reporting year dynamically ---
    try:
        rep_year = str(int(float(individual_df["Reporting period"].dropna().iloc[0])))
    except Exception:
        rep_year = "2024"
    
    # Define dynamic column names based on rep_year
    closed_col    = f"Closed account in {rep_year}"
    balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    dividends_col = f"Distributions (dividends) during {rep_year}"
    interest_col  = f"Interest paid/accrued in {rep_year}"
    proceeds_col  = f"Proceeds during {rep_year}"
    other_col     = f"Other paid/accrued in {rep_year}"
    
    # Filter rows: only process rows with a non-empty "Reporting period"
    individual_df = individual_df[
        individual_df["Reporting period"].notna() & 
        (individual_df["Reporting period"].astype(str).str.strip() != "")
    ]

    # Dictionary to count different INDV
    ah_indv_counts = {}

    for idx, row in individual_df.iterrows():
        # Create a one-row DataFrame for generating DocRefId.
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"]
        
        # --- Build DocSpec block ---
        doc_type_indic = "OECD0" if report_type == "Zero Report" else ("OECD1" if selection == "Initial" else "OECD2")
        # Use Tax residence of PP exclusively (if missing, result will be empty)
        dest_code = dest_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())
        raw_account = (lambda x: "0"+x if len(x)==1 else x)(str(row["Account Number of account holder"]).strip()) if "Account Number of account holder" in row else ""
 
        # Create a key composed of the account number
        ah_key = raw_account
        # Adjusted section: increment the CP counter for each occurrence
        if ah_key not in ah_indv_counts:
            ah_indv_counts[ah_key] = 1
        else:
            ah_indv_counts[ah_key] += 1
        indv_counter = ah_indv_counts[ah_key]

        doc_ref_id = create_RefId(row_df, crs_fatca, raw_account, tag="AR", DestCode=dest_code, tin="Luxembourg TIN of RFI") + "INDV" + str(indv_counter)
        doc_spec = {
            "crsstf:DocTypeIndic": doc_type_indic,
            "crsstf:DocRefId": doc_ref_id
        }
        
        # --- Build AccountNumber dictionary as attributes ---
        acct_type_raw = str(row.get("Type of account", "")).strip().upper()
        if "IBAN" in acct_type_raw or "OECD601" in acct_type_raw:
            acct_num_type = "OECD601"
        elif "OBAN" in acct_type_raw or "OECD602" in acct_type_raw:
            acct_num_type = "OECD602"
        elif "ISIN" in acct_type_raw or "OECD603" in acct_type_raw:
            acct_num_type = "OECD603"
        elif "OSIN" in acct_type_raw or "OECD604" in acct_type_raw:
            acct_num_type = "OECD604"
        elif "OTHER" in acct_type_raw or "OECD605" in acct_type_raw:
            acct_num_type = "OECD605"
        else:
            acct_num_type = "OECD605"
        undocumented = str(row.get("Undocumented Account", "false")).strip().lower() or "false"
        closed = str(row.get(closed_col, "false")).strip().lower() or "false"
        dormant = str(row.get("Dormant Account", "false")).strip().lower() or "false"
        account_number = (lambda x: "0"+x if len(x)==1 else x)(str(row["Account Number of account holder"]).strip()) if "Account Number of account holder" in row else ""
        account_number_dict = {
            "@AcctNumberType": acct_num_type,
            "@UndocumentedAccount": undocumented,
            "@ClosedAccount": closed,
            "@DormantAccount": dormant,
            "#text": account_number
        }
        
        # --- Build AccountHolder dictionary for Individual ---
        # Use Tax residence of PP exclusively for residence and issuedBy
        res_country_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())
        country_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Country of residence of PP", "")).strip())
        tin_pp = process_tin(str(row.get("TIN PP", "")).strip())
        issued_by = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())
        individual_holder = {
            "crs:ResCountryCode": res_country_code,
            "crs:TIN": {
                "@issuedBy": issued_by,
                "#text": tin_pp
            },
            "crs:Name": {
                "crs:FirstName": str(row.get("Name of PP", "")).strip(),
                "crs:LastName": str(row.get("Surname of PP", "")).strip()
            },
            "crs:Address": {
                "commontypesfatcacrs:CountryCode": country_code,
                "commontypesfatcacrs:AddressFree": str(row.get("Adress of PP", "")).strip()
            },
            "crs:BirthInfo": {        # --- Build BirthInfo dictionary ---
                "crs:BirthDate": (pd.to_datetime(row["Date of Birth"]).strftime('%Y-%m-%dZ')
                                if "Date of Birth" in row else str(row.get("Date of Birth", "")).strip()),
                "crs:City": str(row.get("Place of birth", "")).strip()
            }        
        }
        account_holder = {
            "crs:Individual": individual_holder
        }
        
        
        # --- Build AccountBalance ---
        try:
            # Parse the raw balance value
            balance_val = float(row[balance_col])
            # Reset any negative balances to zero
            balance_val = np.maximum(0.0, balance_val)
            # Round to the nearest whole unit and convert to string
            account_balance_str = f"{balance_val:.2f}"
        except Exception:  # Handles KeyError, ValueError, TypeError, etc.
            account_balance_str = "0.00"

        account_balance = {
            "@currCode": str(row.get("Currency", "EUR")).strip(),
            "#text": account_balance_str
        }

        # --- Build Payments ---
        curr_code = str(row.get("Currency", "EUR")).strip()
        payment501 = get_payment(row, dividends_col, "CRS501", curr_code)
        payment502 = get_payment(row, interest_col, "CRS502", curr_code)
        payment503 = get_payment(row, proceeds_col, "CRS503", curr_code)
        payment504 = get_payment(row, other_col, "CRS504", curr_code)
        payments = [payment501, payment502, payment503, payment504]
        
        individual_result = {
            "crs:DocSpec": doc_spec,
            "crs:AccountNumber": account_number_dict,
            "crs:AccountHolder": {
                "crs:Individual": account_holder["crs:Individual"]
            },
            "crs:BirthInfo": individual_holder["crs:BirthInfo"],
            "crs:AccountBalance": account_balance,
            "crs:Payment": payments,
            "ReportableCountry": res_country_code
        }
        
        results.append({"crs:AccountReport": individual_result})
    
    return results


def get_info_Individual_fatca(individual_df, report_type, selection, crs_fatca="FATCA"):
    """
    Processes all rows from the Individual tab DataFrame and returns a list of dictionaries,
    one for each account, adapted for FATCA.
    
    The key change here is that the destination country (for generating the DocRefId) and the
    residence country in the account holder are taken exclusively from the column 
    "Tax residence of PP". If that value is missing or blank, it will be an empty string.
    
    Payment amounts are converted to float, rounded to the nearest integer, then to a string;
    if a payment value is missing, it is set to "0.00".
    """

    results = []

    # --- Determine the reporting year dynamically ---
    try:
        if ("Year following reporting period" in individual_df.columns and 
            not individual_df["Year following reporting period"].dropna().empty):
            rep_year = str(int(float(individual_df["Year following reporting period"].dropna().iloc[0])) - 1)
        else:
            rep_year = str(int(float(individual_df["Reporting period"].dropna().iloc[0])))
    except Exception:
        rep_year = "2023"
    
    # Define dynamic column names based on rep_year
    closed_col    = f"Closed account in {rep_year} (YES/NO)"
    balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    dividends_col = f"Distributions (dividends) during {rep_year}"
    interest_col  = f"Interest paid/accrued in {rep_year}"
    proceeds_col  = f"Proceeds during {rep_year}"
    other_col     = f"Other paid/accrued in {rep_year}"
    
    # Filter rows: only process rows with a non-empty "Reporting period"
    individual_df = individual_df[
        individual_df["Reporting period"].notna() & 
        (individual_df["Reporting period"].astype(str).str.strip() != "")
    ]

    # Dictionary to count different INDV
    ah_indv_counts = {}
    
    for idx, row in individual_df.iterrows():
        # Create a one-row DataFrame for generating DocRefId.
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"]
        
        # --- Build DocSpec block ---
        doc_type_indic = "FATCA0" if report_type == "Zero Report" else ("FATCA1" if selection == "Initial" else "FATCA2")
        # Use Tax residence of PP exclusively (if missing, result will be empty)
        dest_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())
        raw_account = (lambda s: ("0" + s) if len(s) == 1 else s)((lambda s: s[:-2] if s.endswith(".0") else s)(str(row.get("Account Number of account holder", "")).strip()))

        # Normalize INDV name: remove spaces and convert to lowercase
        name_indv = str(row.get("Name of PP", "")).strip()
        surname_indv = str(row.get("Surname of PP", "")).strip()
        full_name_indv = name_indv + surname_indv
        normalized_name_ah = re.sub(r'\s+', '', full_name_indv).lower()

        # Create a key composed of the account number and normalized AH name
        ah_key = (raw_account, normalized_name_ah)
        
        # Adjusted section: increment the CP counter for each occurrence
        if ah_key not in ah_indv_counts:
            ah_indv_counts[ah_key] = 1
        else:
            ah_indv_counts[ah_key] += 1
        indv_counter = ah_indv_counts[ah_key]

        doc_ref_id = create_RefId(row_df, crs_fatca, raw_account, tag="AR", DestCode=dest_code, tin="Luxembourg TIN of RFI") + "INDV" + str(indv_counter)
        doc_spec = {
            "fatca:DocTypeIndic": doc_type_indic,
            "fatca:DocRefId": doc_ref_id
        }
        
        # --- Build AccountNumber dictionary as attributes ---
        acct_type_raw = str(row.get("Type of account", "")).strip().upper()
        if "IBAN" in acct_type_raw or "OECD601" in acct_type_raw:
            acct_num_type = "OECD601"
        elif "OBAN" in acct_type_raw or "OECD602" in acct_type_raw:
            acct_num_type = "OECD602"
        elif "ISIN" in acct_type_raw or "OECD603" in acct_type_raw:
            acct_num_type = "OECD603"
        elif "OSIN" in acct_type_raw or "OECD604" in acct_type_raw:
            acct_num_type = "OECD604"
        elif "OTHER" in acct_type_raw or "OECD605" in acct_type_raw:
            acct_num_type = "OECD605"
        else:
            acct_num_type = "OECD605"
        closed = str(row.get(closed_col, "false")).strip().lower() or "false"
        account_number = (lambda x: "0" + x if len(x)==1 else x)(
                             str(row.get("Account Number of account holder", "")).strip()
                         ) if "Account Number of account holder" in row else ""
        
        # --- Build AccountHolder dictionary for Individual ---
        # Use Tax residence of PP exclusively for residence and issuedBy
        res_country_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())
        country_code = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Country of residence of PP", "")).strip())
        tin_pp = process_tin(str(row.get("TIN PP", "")).strip())
        issued_by = (lambda t: t.upper() if len(t)==2 and t.isalpha() else transform_country_code(t))(str(row.get("Tax residence of PP", "")).strip())

        individual_holder = {
            "stffatcatypes:ResCountryCode": res_country_code,
            "stffatcatypes:TIN": {
                "@issuedBy": issued_by,
                "#text": tin_pp
            },
            "stffatcatypes:Name": {
                "stffatcatypes:FirstName": str(row.get("Name of PP", "")).strip(),
                "stffatcatypes:LastName": str(row.get("Surname of PP", "")).strip()
            },
            "stffatcatypes:Address": {
                "stffatcatypes:CountryCode": country_code,
                "stffatcatypes:AddressFree": str(row.get("Adress of PP", "")).strip()
            },
            "stffatcatypes:BirthInfo": {
                "stffatcatypes:BirthDate": (pd.to_datetime(row["Date of Birth"]).strftime('%Y-%m-%dZ')
                                    if "Date of Birth" in row else str(row.get("Date of Birth", "")).strip()),
                "stffatcatypes:City": str(row.get("Place of birth", "")).strip()
            }        
        }
        account_holder = {
            "fatca:Individual": individual_holder
        }
        
        # --- Build AccountBalance ---
        try:
            # Parse the raw balance value
            balance_val = float(row[balance_col])
            # Reset any negative balances to zero
            balance_val = np.maximum(0.0, balance_val)
            # Round to the nearest whole unit and convert to string
            account_balance_str = f"{balance_val:.2f}"
        except Exception:  # Catches KeyError, ValueError, TypeError, etc.
            account_balance_str = "0.00"

        account_balance = {
            "@currCode": str(row.get("Currency", "EUR")).strip(),
            "#text": account_balance_str
        }

        # --- Build Payments ---
        curr_code = str(row.get("Currency", "EUR")).strip()
        payment501 = get_payment_fatca(row, dividends_col, "FATCA501", curr_code)
        payment502 = get_payment_fatca(row, interest_col, "FATCA502", curr_code)
        payment503 = get_payment_fatca(row, proceeds_col, "FATCA503", curr_code)
        payment504 = get_payment_fatca(row, other_col, "FATCA504", curr_code)
        payments = [payment501, payment502, payment503, payment504]
        
        individual_result = {
            "fatca:DocSpec": doc_spec,
            "fatca:AccountNumber": account_number,
            "fatca:AccountClosed":closed,
            "fatca:AccountHolder": {
                "fatca:Individual": account_holder["fatca:Individual"]
            },
            "fatca:AccountBalance": account_balance,
            "fatca:Payment": payments,
            "ReportableCountry": res_country_code
        }
        
        results.append({"fatca:AccountReport": individual_result})
    
    return results
