# core_functions_active.py
import pandas as pd
import re
from datetime import datetime
import numpy as np
from .core_functions import *

def get_info_Active(active_df, report_type, selection, crs_fatca="CRS"):
    """
    Processes all rows from the Active tab DataFrame and returns a list of dictionaries,
    one for each account, with the following structure:
    
    {
       "crs:DocSpec": {
            "crsstf:DocTypeIndic": <"OECD0" if Zero Report, "OECD1" if Data Report + Initial, "OECD2" if Data Report + Correction>,
            "crsstf:DocRefId": create_RefId(row_df, crs_fatca, AccountNumber, tag="AR", DestCode=<Country of residence of active>, tin="Luxembourg TIN of RFI")
       },
       "crs:AccountNumber": {
            "@AcctNumberType": <OECD code based on "Type of account">,
            "@UndocumentedAccount": <value from "Undocumented Account" (default "false")>,
            "@ClosedAccount": <value from "Closed account in {rep_year} (YES/NO)" (default "false")>,
            "@DormantAccount": <value from "Dormant Account" (default "false")>,
            "#text": <"Account Number of account holder" as an integer string>
       },
       "crs:AccountHolder": {
            "crs:Organisation": {
                 "crs:ResCountryCode": <"Country of residence of active">,
                 "crs:IN": {
                     "@issuedBy": <"Tax residence of Active">,
                     "#text": <"TIN active NFE">
                 },
                 "crs:Name": <"Name of Active">,
                 "crs:Address": {
                     "commontypesfatcacrs:CountryCode": <"Country of residence of active">,
                     "commontypesfatcacrs:AddressFree": <"Adress of Active NFE" + " " + "Code and Country of Active NFE">
                 }
            },
            "crs:AcctHolderType": "CRS102",
            "AccountNumber": <same as in crs:AccountNumber>
       },
       "crs:AccountBalance": {
            "@currCode": <"Currency">,
            "#text": <Account balance (rounded and converted to string)>
       },
       "crs:Payment": [ list of 4 payment dicts ],
       "ReportableCountry": <value from "Tax residence of Active" if not LU; otherwise None>
    }
    
    Payment amounts are converted to float, rounded, then to string;
    if a payment value is missing, it is set to "0.00".
    """
    results = []
    # --- Determine the reporting year dynamically ---
    if "Reporting period" in active_df.columns and not active_df["Reporting period"].dropna().empty:
        rep_year = str(int(float(active_df["Reporting period"].dropna().iloc[0])))
    else:
        rep_year = "2024"  # default fallback

    # Define dynamic column names based on rep_year
    closed_col    = f"Closed account in {rep_year}"
    balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    proceeds_col  = f"Proceeds during {rep_year}"
    dividends_col = f"Distributions (dividends) during {rep_year}"
    interest_col  = f"Interest paid/accrued in {rep_year}"
    other_col     = f"Other paid/accrued in {rep_year}"

    # Filter rows: only process rows with a non-empty "Name of Reporting Financial Institution (RFI)"
    active_df = active_df[
        active_df["Name of Reporting Financial Institution (RFI)"].notna() &
        (active_df["Name of Reporting Financial Institution (RFI)"].astype(str).str.strip() != "")
    ]
 
    for idx, row in active_df.iterrows():
        # Create a one-row DataFrame for generating DocRefId.
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"] + 1
        
        # --- Determine ReportableCountry from "Tax residence of Active" (if present)
        reportable = None
        if "Tax residence of Active" in row and pd.notna(row["Tax residence of Active"]):
            tmp = transform_country_code(str(row["Tax residence of Active"]).strip())
            if tmp.upper() != "LU" and tmp != "":
                reportable = tmp
        
        # --- Process Account Number: convert to integer then to string
        try:
            AccountNumber = (lambda x: "0"+x if len(x)==1 else x)(str(row["Account Number of account holder"]).strip())
        except Exception:
            AccountNumber = str(row["Account Number of account holder"]).strip()
        
        # --- Determine AcctNumberType based on "Type of account"
        type_of_account = str(row["Type of account"]).strip().upper()

        if "IBAN" in type_of_account or "OECD601" in type_of_account:
            AcctNumberType = "OECD601"
        elif "OBAN" in type_of_account or "OECD602" in type_of_account:
            AcctNumberType = "OECD602"
        elif "ISIN" in type_of_account or "OECD603" in type_of_account:
            AcctNumberType = "OECD603"
        elif "OSIN" in type_of_account or "OECD604" in type_of_account:
            AcctNumberType = "OECD604"
        elif "OTHER" in type_of_account or "OECD605" in type_of_account:
            AcctNumberType = "OECD605"
        else:
            AcctNumberType = "OECD605"
        
        UndocumentedAccount = str(row["Undocumented Account"]).strip().lower() if "Undocumented Account" in row else "false"
        ClosedAccount = str(row[closed_col]).strip().lower() if closed_col in row else "false"
        DormantAccount = str(row["Dormant Account"]).strip().lower() if "Dormant Account" in row else "false"
                
        # --- Determine the reporting year (from "Year following reporting period")
        year_values = active_df["Reporting period"].dropna().unique()

        try:
            year_int = int(float(year_values[0]))
            year_str = str(year_int)
        except Exception as e:
            raise ValueError("Cannot convert 'Reporting period' to a valid integer.") from e
        
        # --- Build the DocSpec dictionary ---
        DocTypeIndic = "OECD0" if report_type == "Zero Report" else ("OECD1" if selection == "Initial" else "OECD2")
        # For DestCode, use "Country of residence of active" if available, else use the ReportableCountry
        if "Country of residence of active" in row and str(row["Country of residence of active"]).strip() != "":
            DestCode = str(row["Country of residence of active"]).strip()
        elif reportable:
            DestCode = reportable
        else:
            DestCode = "LU"  # fallback (should normally not be used)
        DocRefId = create_RefId(row_df, crs_fatca, AccountNumber, tag="AR", DestCode=DestCode, tin="Luxembourg TIN of RFI")
        DocSpec = {
            "DocTypeIndic": DocTypeIndic,
            "DocRefId": DocRefId
        }
        
        # --- Build AccountHolder dictionary ---
        Organisation = {
            "ResCountryCode": transform_country_code(str(row["Tax residence of Active"]).strip()),
            "TIN": str(row["TIN active NFE"]).strip(),
            "IssuedBy": transform_country_code(str(row["Tax residence of Active"]).strip()),
            "Name": str(row["Name of Active"]).strip(),
            "Address": {
                "CountryCode": transform_country_code(str(row["Country of residence of active"]).strip()),
                "AddressFree": " ".join(filter(None, [
                    str(row["Adress of Active NFE"]).strip() if pd.notna(row["Adress of Active NFE"]) else ""
                ]))
            }
        }
        AccountHolder = {
            "Organisation": Organisation,
            "AcctHolderType": "CRS102",
            "AccountNumber": AccountNumber
        }
        
        # --- Get AccountBalance ---
        try:
            # Get the raw balance and convert to float
            balance_val = float(row[balance_col])
            # Reset any negative balances to zero
            balance_val = np.maximum(0.0, balance_val)
            # Round to the nearest whole unit and convert to string
            AccountBalance = f"{balance_val:.2f}"
        except Exception:  # Handles KeyError, ValueError, TypeError, etc.
            AccountBalance = "0.00"

        # Retrieve the currency code (default to "EUR" if missing) and strip whitespace
        currCode = str(row.get("Currency", "EUR")).strip()
        Payment501 = get_payment(row, dividends_col, "CRS501", currCode)
        Payment502 = get_payment(row, interest_col, "CRS502", currCode)
        Payment503 = get_payment(row, proceeds_col, "CRS503", currCode)
        Payment504 = get_payment(row, other_col, "CRS504", currCode)
        payments = [Payment501, Payment502, Payment503, Payment504]

        # --- Assemble the account report dictionary ---
        account_report = {
            "crs:DocSpec": {
                "crsstf:DocTypeIndic": DocSpec["DocTypeIndic"],
                "crsstf:DocRefId": DocSpec["DocRefId"]
            },
            "crs:AccountNumber": {
                "@AcctNumberType": AcctNumberType,
                "@UndocumentedAccount": UndocumentedAccount,
                "@ClosedAccount": ClosedAccount,
                "@DormantAccount": DormantAccount,
                "#text": AccountNumber
            },
            "crs:AccountHolder": {
                "crs:Organisation": {
                    "crs:ResCountryCode": AccountHolder["Organisation"]["ResCountryCode"],
                    "crs:IN": {
                        "@issuedBy": AccountHolder["Organisation"]["IssuedBy"],
                        "#text": AccountHolder["Organisation"]["TIN"]
                    },
                    "crs:Name": AccountHolder["Organisation"]["Name"],
                    "crs:Address": {
                        "commontypesfatcacrs:CountryCode": AccountHolder["Organisation"]["Address"]["CountryCode"],
                        "commontypesfatcacrs:AddressFree": AccountHolder["Organisation"]["Address"]["AddressFree"]
                    }
                },
                "crs:AcctHolderType": AccountHolder["AcctHolderType"]
            },
            "crs:AccountBalance": {
                "@currCode": currCode,
                "#text": AccountBalance
            },
            "crs:Payment": payments,
            "ReportableCountry": reportable  # This key will be used later for grouping by reportable country.
        }
        
        results.append({"crs:AccountReport": account_report})
    
    return results


def get_info_Active_fatca(active_df, report_type, selection, crs_fatca="FATCA"):
    """
    Processes all rows from the Active tab DataFrame and returns a list of dictionaries,
    one for each account, structured as a complete <fatca:AccountReport> for the active section.
    
    Expected structure per account:
    
    {
       "fatca:DocSpec": {
            "fatca:DocTypeIndic": <"FATCA0" if Zero Report, "FATCA1" if Data Report + Initial, "FATCA2" if Data Report + Correction>,
            "fatca:DocRefId": create_RefId(row_df, crs_fatca, AccountNumber, tag="AR", DestCode=<Country of residence of active>, tin="Luxembourg TIN of RFI")
       },
       "fatca:AccountNumber": <"Account Number of account holder" (padded if single digit)>
       "fatca:AccountClosed": <"Closed account in YYYY" (default "false")>,
       "fatca:AccountHolder": {
            "fatca:Organisation": {
                 "stffatcatypes:ResCountryCode": <"Tax residence of Active">,
                 "stffatcatypes:TIN": {
                     "@issuedBy": <"Tax residence of Active">,
                     "#text": <"TIN active NFE">
                 },
                 "stffatcatypes:Name": <"Name of Active">,
                 "stffatcatypes:Address": {
                     "stffatcatypes:CountryCode": <"Country of residence of active">,
                     "stffatcatypes:AddressFree": <"Adress of Active NFE" + " " + "Code and Country of Active NFE">
                 }
            },
            "fatca:AcctHolderType": "FATCA104",
       },
       "fatca:AccountBalance": {
            "@currCode": <Currency>,
            "#text": <Account balance (rounded and converted to string)>
       },
       "fatca:Payment": [ list of 4 payment dicts ],
       "ReportableCountry": <value from "Tax residence of Active" if not LU; otherwise None>
    }
    
    Payment amounts are converted to float, rounded, then to string;
    if a payment value is missing, it is set to "0.00".
    """
    import pandas as pd
    import re
    from .core_functions import create_RefId, transform_country_code, get_payment_fatca

    results = []
    # --- Determine the reporting year dynamically ---
    if "Reporting period" in active_df.columns and not active_df["Reporting period"].dropna().empty:
        rep_year = str(int(float(active_df["Reporting period"].dropna().iloc[0])))
    else:
        rep_year = "2024"  # default fallback

    # Define dynamic column names based on rep_year
    closed_col    = f"Closed account in {rep_year} (YES/NO)"
    balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    proceeds_col  = f"Proceeds during {rep_year}"
    dividends_col = f"Distributions (dividends) during {rep_year}"
    interest_col  = f"Interest paid/accrued in {rep_year}"
    other_col     = f"Other paid/accrued in {rep_year}"

    # Filter rows: only process rows with a non-empty "Name of Reporting Financial Institution (RFI)"
    active_df = active_df[
        active_df["Name of Reporting Financial Institution (RFI)"].notna() &
        (active_df["Name of Reporting Financial Institution (RFI)"].astype(str).str.strip() != "")
    ]
    
    for idx, row in active_df.iterrows():
        # Create a one-row DataFrame for generating DocRefId.
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"] + 1
        
        # --- Determine ReportableCountry from "Tax residence of Active" (if present)
        reportable = None
        if "Tax residence of Active" in row and pd.notna(row["Tax residence of Active"]):
            tmp = transform_country_code(str(row["Tax residence of Active"]).strip())
            if tmp.upper() != "LU" and tmp != "":
                reportable = tmp
        
        # --- Process Account Number: pad with a "0" if it is a single character
        try:
            AccountNumber = (lambda x: "0" + x if len(x) == 1 else x)(
                str(row["Account Number of account holder"]).strip()
            )
        except Exception:
            AccountNumber = str(row["Account Number of account holder"]).strip()
        
        ClosedAccount = str(row[closed_col]).strip().lower() if closed_col in row else "false"
        
        # --- Determine the reporting year (from "Reporting period")
        year_values = active_df["Reporting period"].dropna().unique()
        try:
            year_int = int(float(year_values[0]))
            year_str = str(year_int)
        except Exception as e:
            raise ValueError("Cannot convert 'Reporting period' to a valid integer.") from e
        
        # --- Build the DocSpec dictionary ---
        DocTypeIndic = "FATCA0" if report_type == "Zero Report" else ("FATCA1" if selection == "Initial" else "FATCA2")
        # For DestCode, use "Country of residence of active" if available, else use the ReportableCountry
        if "Country of residence of active" in row and str(row["Country of residence of active"]).strip() != "":
            DestCode = str(row["Country of residence of active"]).strip()
        elif reportable:
            DestCode = reportable
        else:
            DestCode = "LU"  # fallback
        DocRefId = create_RefId(row_df, crs_fatca, AccountNumber, tag="AR", DestCode=DestCode, tin="Luxembourg TIN of RFI")
        DocSpec = {
            "fatca:DocTypeIndic": DocTypeIndic,
            "fatca:DocRefId": DocRefId
        }
        
        # --- Build AccountHolder dictionary ---
        Organisation = {
            "stffatcatypes:ResCountryCode": transform_country_code(str(row.get("Tax residence of Active", "")).strip()),
            "stffatcatypes:TIN": {
                "@issuedBy": transform_country_code(str(row.get("Tax residence of Active", "")).strip()),
                "#text": str(row.get("TIN active NFE", "")).strip()
            },
            "stffatcatypes:Name": str(row.get("Name of Active", "")).strip(),
            "stffatcatypes:Address": {
                "stffatcatypes:CountryCode": transform_country_code(str(row.get("Country of residence of active", "")).strip()),
                "stffatcatypes:AddressFree": (str(row.get("Adress of Active NFE", "")).strip() + " " +
                                                    str(row.get("Code and Country of Active NFE", "")).strip())
            }
        }
        AccountHolder = {
            "fatca:Organisation": Organisation,
            "fatca:AcctHolderType": "FATCA104",
            "AccountNumber": AccountNumber
        }
        
        # --- Get AccountBalance ---
        try:
            # Get the raw balance from the row; default to 0 if the key is missing
            balance_val = float(row.get(balance_col, 0))

            # Ensure negative balances are reset to zero
            balance_val = np.maximum(0.0, balance_val)

            # Round to the nearest whole unit and convert to string
            account_balance = f"{balance_val:.2f}"
        except Exception:  # Handles KeyError, ValueError, TypeError, etc.
            account_balance = "0.00"

        AccountBalance_dict = {
            "@currCode": str(row.get("Currency", "EUR")).strip(),
            "#text": account_balance
        }
        curr_code = str(row.get("Currency", "EUR")).strip()
        
        # --- Build Payment blocks ---
        payment501 = get_payment_fatca(row, dividends_col, "FATCA501", curr_code)
        payment502 = get_payment_fatca(row, interest_col, "FATCA502", curr_code)
        payment503 = get_payment_fatca(row, proceeds_col, "FATCA503", curr_code)
        payment504 = get_payment_fatca(row, other_col, "FATCA504", curr_code)
        payments = [payment501, payment502, payment503, payment504]
        
        individual_result = {
            "fatca:DocSpec": DocSpec,
            "fatca:AccountNumber": AccountNumber,
            "fatca:AccountClosed":ClosedAccount,
            "fatca:AccountHolder": {
                "fatca:Organisation": Organisation,
                "fatca:AcctHolderType": "FATCA104"
            },
            "fatca:AccountBalance": AccountBalance_dict,
            "fatca:Payment": payments,
            "ReportableCountry": transform_country_code(str(row.get("Tax residence of Active", "")).strip())
        }
        
        results.append({"fatca:AccountReport": individual_result})
    
    return results
