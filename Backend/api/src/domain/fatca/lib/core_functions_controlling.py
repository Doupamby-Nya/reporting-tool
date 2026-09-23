# core_functions_controlling.py
import pandas as pd
import re
import numpy as np
from datetime import datetime
from .core_functions import create_RefId, transform_country_code, get_payment, get_payment_fatca, process_tin

def get_info_controlling(cps_df, report_type, selection, crs_fatca="CRS"):
    """
    Processes all rows from the CPS DataFrame that pertain to controlling persons and returns a list 
    of dictionaries, one for each account, structured as a complete <crs:AccountReport> for the controlling section.

    Expected structure per account:
    {
      "crs:DocSpec": {
          "crsstf:DocTypeIndic": <"OECD0" if Zero Report, "OECD1" if Data Report + Initial, "OECD2" if Correction>,
          "crsstf:DocRefId": <create_RefId(...) using tin="TIN of CP">
      },
      "crs:AccountNumber": {
          "@AcctNumberType": <derived from "Type of account">,
          "@UndocumentedAccount": <value from "Undocumented Account" (default "FALSE")>,
          "@ClosedAccount": <value from dynamic closed column or "FALSE">,
          "@DormantAccount": <value from "Dormant Account" (default "FALSE")>,
          "#text": <Account number from "Account Number of account holder /CP">
      },
      "crs:AccountHolder": {
          "crs:Organisation": {
              "crs:ResCountryCode": <Tax residence of AH>,
              "crs:IN": {
                  "@issuedBy": <Tax residence of AH>,
                  "#text": <TIN passive NFE>
              },
              "crs:Name": <Name of AH>,
              "crs:Address": {
                  "commontypesfatcacrs:CountryCode": <Tax residence of AH>,
                  "commontypesfatcacrs:AddressFree": <Adress of passive NFE>
              }
          },
          "crs:AcctHolderType": "CRS101"
      },
      "crs:ControllingPerson": {
          "crs:Individual": {
              "crs:ResCountryCode": <Tax residence of CP>,
              "crs:TIN": {
                  "@issuedBy": <Tax residence of CP>,
                  "#text": <TIN of CP>
              },
              "crs:Name": {
                  "crs:FirstName": <Name of CP>,
                  "crs:LastName": <First Name of CP>
              },
              "crs:Address": {
                  "commontypesfatcacrs:CountryCode": <Tax residence of CP>,
                  "commontypesfatcacrs:AddressFree": <Address of CP; Zip code; Country of residence of CP>
              },
              "crs:BirthInfo": {
                  "crs:BirthDate": <Date of Birth CP (formatted as YYYY-MM-DDZ)>,
                  "crs:City": <Place of birth CP>
              }
          },
          "crs:CtrlgPersonType": <Type of control exercised by CP>
      },
      "crs:AccountBalance": {
          "@currCode": <Currency>,
          "#text": <Account balance (rounded)>
      },
      "crs:Payment": [
          {
              "crs:Type": "CRS501",
              "crs:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <dividends as int string>
              }
          },
          {
              "crs:Type": "CRS502",
              "crs:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <interest as int string>
              }
          },
          {
              "crs:Type": "CRS503",
              "crs:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <proceeds as int string>
              }
          },
          {
              "crs:Type": "CRS504",
              "crs:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <other payments as int string>
              }
          }
      ],
      "ReportableCountry": <derived from "Tax residence of CP", or None if LU or empty>
    }

    Notes:
      - Payment amounts are converted to float, rounded, then to string ("0.00" if missing).
      - The reporting year (rep_year) is extracted from "Reporting period" or "Year following reporting period" (subtract 1).
      - Dynamic column names for payment fields are built based on rep_year.
    """
    results = []
    # --- 1) Determine the reporting year dynamically ---
    rep_year = None
    if "Reporting period" in cps_df.columns and not cps_df["Reporting period"].dropna().empty:
        try:
            rep_year = str(int(float(cps_df["Reporting period"].dropna().iloc[0])))
        except Exception:
            rep_year = None
    if rep_year is None and "Year following reporting period" in cps_df.columns and not cps_df["Year following reporting period"].dropna().empty:
        try:
            rep_year = str(int(float(cps_df["Year following reporting period"].dropna().iloc[0])) - 1)
        except Exception:
            rep_year = "2024"
    if rep_year is None:
        rep_year = "2024"

    # --- 2) Build dynamic column names based on rep_year ---
    dynamic_balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    dynamic_dividends_col = f"Distributions (dividends) during {rep_year}"
    dynamic_interest_col  = f"Interest paid/accrued in {rep_year}"
    dynamic_proceeds_col  = f"Proceeds during {rep_year}"
    dynamic_other_col     = f"Other paid/accrued in {rep_year}"
    closed_col            = f"Closed account in {rep_year}"

    # --- 3) Filter rows: keep only rows where "Reporting period" exists and is not empty ---
    if "Reporting period" in cps_df.columns:
        cps_df = cps_df[cps_df["Reporting period"].notna() & (cps_df["Reporting period"].astype(str).str.strip() != "")]
    else:
        raise ValueError("Controlling section: 'Reporting period' column is missing.")

    # Dictionary to count CP for each (account, AH) pair
    ah_cp_counts = {}

    for idx, row in cps_df.iterrows():
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"]

        # A) DocSpec block
        doc_type_indic = "OECD0" if report_type == "Zero Report" else ("OECD1" if selection == "Initial" else "OECD2")
        dest_code = transform_country_code(str(row.get("Country of residence of CP", "")).strip()) or "LU"
        raw_account = (lambda s: ("0" + s) if len(s) == 1 else s)((lambda s: s[:-2] if s.endswith(".0") else s)(str(row.get("Account Number of account holder /CP", "")).strip()))

        # Normalize AH name: remove spaces and convert to lowercase
        name_ah = str(row.get("Name of AH", "")).strip()
        normalized_name_ah = re.sub(r'\s+', '', name_ah).lower()
        # Create a key composed of the account number and normalized AH name
        ah_key = (raw_account, normalized_name_ah)
        
        # Adjusted section: increment the CP counter for each occurrence
        if ah_key not in ah_cp_counts:
            ah_cp_counts[ah_key] = 1
        else:
            ah_cp_counts[ah_key] += 1
        cp_counter = ah_cp_counts[ah_key]
        
        # Create doc_ref_id by appending "CP" followed by the counter
        doc_ref_id = create_RefId(row_df, crs_fatca, raw_account, tag="AR", DestCode=dest_code, tin="Luxembourg TIN of RFI") + "CP" + str(cp_counter)
        doc_spec = {
            "crsstf:DocTypeIndic": doc_type_indic,
            "crsstf:DocRefId": doc_ref_id
        }

        # B) AccountNumber block
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
        account_number = (lambda s: ("0" + s) if len(s) == 1 else s)((lambda s: s[:-2] if s.endswith(".0") else s)(str(row.get("Account Number of account holder /CP", "")).strip()))
        account_number_dict = {
            "@AcctNumberType": acct_num_type,
            "@UndocumentedAccount": undocumented,
            "@ClosedAccount": closed,
            "@DormantAccount": dormant,
            "#text": account_number
        }

        # C) AccountHolder block (Organisation)
        tax_res_ah  = transform_country_code(str(row.get("Tax residence of AH", "")).strip())
        tin_passive = str(row.get("TIN passive NFE", "")).strip()
        address_ah  = str(row.get("Adress of passive NFE", "")).strip()
        organisation = {
            "crs:ResCountryCode": tax_res_ah,
            "crs:IN": {
                "@issuedBy": tax_res_ah,
                "#text": tin_passive
            },
            "crs:Name": name_ah,
            "crs:Address": {
                "commontypesfatcacrs:CountryCode": tax_res_ah,
                "commontypesfatcacrs:AddressFree": address_ah
            }
        }
        account_holder = {
            "crs:Organisation": organisation,
            "crs:AcctHolderType": "CRS101"
        }

        # D) ControllingPerson block
        country_cp = str(row.get("Country of residence of CP", "")).strip()
        tax_res_cp = transform_country_code(str(row.get("Tax residence of CP", "")).strip())
        tin_cp = process_tin(str(row.get("TIN of CP", "")).strip())
        name_cp = str(row.get("Name of CP", "")).strip()
        surname_cp = str(row.get("First Name of CP", "")).strip()
        address_cp = str(row.get("Address of CP", "")).strip()
        zip_cp = str(row.get("Zip code", "")).strip()
        place_birth = str(row.get("Place of birth CP", "")).strip()
        dob_cp = str(row.get("Date of Birth CP", "")).strip()
        ctrlgpersontype = f"CRS{m.group(0)}" if (m := re.search(r"\d{3}", str(row.get("Type of control exercised by CP", "")))) else ""

        try:
            dt = pd.to_datetime(dob_cp)
            dob_cp = dt.strftime('%Y-%m-%dZ')
        except Exception:
            pass
        address_free_cp = f"{address_cp};{zip_cp};{country_cp}".strip(";")
        country_cp = transform_country_code(country_cp)
        controlling_person = {
            "crs:Individual": {
                "crs:ResCountryCode": tax_res_cp,
                "crs:TIN": {
                    "@issuedBy": tax_res_cp,
                    "#text": tin_cp
                },
                "crs:Name": {
                    "crs:FirstName": surname_cp,
                    "crs:LastName": name_cp
                },
                "crs:Address": {
                    "commontypesfatcacrs:CountryCode": country_cp,
                    "commontypesfatcacrs:AddressFree": address_free_cp
                },
                "crs:BirthInfo": {
                    "crs:BirthDate": dob_cp,
                    "crs:City": place_birth
                }
            },
            "crs:CtrlgPersonType": ctrlgpersontype
        }

        # E) AccountBalance block
        try:
            # Retrieve the raw balance; default to 0 if the column is missing
            balance_val = float(row.get(dynamic_balance_col, 0))

            # Reset negative balances to zero
            balance_val = np.maximum(0.0, balance_val)

            # Round to the nearest whole unit and convert to string
            account_balance_str = f"{balance_val:.2f}"
        except Exception:  # Handles KeyError, ValueError, TypeError, etc.
            account_balance_str = "0.00"

        account_balance = {
            "@currCode": str(row.get("Currency", "EUR")).strip(),
            "#text": account_balance_str
        }

        # F) Payment blocks
        curr_code = str(row.get("Currency", "EUR")).strip()
        payment501 = get_payment(row, dynamic_dividends_col, "CRS501", curr_code)
        payment502 = get_payment(row, dynamic_interest_col, "CRS502", curr_code)
        payment503 = get_payment(row, dynamic_proceeds_col, "CRS503", curr_code)
        payment504 = get_payment(row, dynamic_other_col, "CRS504", curr_code)
        payments = [payment501, payment502, payment503, payment504]

        # Build final dictionary for the controlling account report.
        controlling_result = {
            "crs:DocSpec": doc_spec,
            "crs:AccountNumber": account_number_dict,
            "crs:AccountHolder": account_holder,
            "crs:ControllingPerson": controlling_person,
            "crs:AccountBalance": account_balance,
            "crs:Payment": payments,
            "ReportableCountry": tax_res_cp
        }
        
        results.append({"crs:AccountReport": controlling_result})
    
    return results


def get_info_controlling_fatca(cps_df, report_type, selection, crs_fatca="FATCA"):
    """
    Processes all rows from the CPS DataFrame that pertain to controlling persons and returns a list 
    of dictionaries, one for each account, structured as a complete <fatca:AccountReport> for the controlling section.

    Expected structure per account:
    {
      "fatca:DocSpec": {
          "fatca:DocTypeIndic": <"FATCA0" if Zero Report, "FATCA1" if Data Report + Initial, "FATCA2" if Correction>,
          "fatca:DocRefId": <create_RefId(...) using tin="TIN of CP">
      },
      "fatca:AccountNumber": <Account number from "Account Number of account holder /CP">
      "fatca:AccountClosed": <"Closed account in YYYY" (default "false")>,
      "fatca:AccountHolder": {
          "fatca:Organisation": {
              "stffatcatypes:ResCountryCode": <Tax residence of AH>,
              "stffatcatypes:TIN": {
                  "@issuedBy": <Tax residence of AH>,
                  "#text": <TIN passive NFE>
              },
              "stffatcatypes:Name": <Name of AH>,
              "stffatcatypes:Address": {
                  "stffatcatypes:CountryCode": <Tax residence of AH>,
                  "stffatcatypes:AddressFree": <Adress of passive NFE>
              }
          },
          "fatca:AcctHolderType": "FATCA101"
      },
      "fatca:SubstantialOwner": {
          "fatca:Individual": {
              "stffatcatypes:ResCountryCode": <Tax residence of CP>,
              "stffatcatypes:TIN": {
                  "@issuedBy": <Tax residence of CP>,
                  "#text": <TIN of CP>
              },
              "stffatcatypes:Name": {
                  "stffatcatypes:FirstName": <Name of CP>,
                  "stffatcatypes:LastName": <Firstname of CP>
              },
              "stffatcatypes:Address": {
                  "stffatcatypes:CountryCode": <Country of residence of CP>,
                  "stffatcatypes:AddressFree": <Address of CP; Zip code; Country of residence of CP>
              },
              "stffatcatypes:BirthInfo": {
                  "stffatcatypes:BirthDate": <Date of Birth CP (formatted as YYYY-MM-DDZ)>,
                  "stffatcatypes:City": <Place of birth CP>
              }
          }
      },
      "fatca:AccountBalance": {
          "@currCode": <Currency>,
          "#text": <Account balance (rounded)>
      },
      "fatca:Payment": [
          {
              "fatca:Type": "FATCA501",
              "fatca:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <dividends as int string>
              }
          },
          {
              "fatca:Type": "FATCA502",
              "fatca:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <interest as int string>
              }
          },
          {
              "fatca:Type": "FATCA503",
              "fatca:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <proceeds as int string>
              }
          },
          {
              "fatca:Type": "FATCA504",
              "fatca:PaymentAmnt": {
                  "@currCode": <Currency>,
                  "#text": <other payments as int string>
              }
          }
      ],
      "ReportableCountry": <derived from "Tax residence of CP", or None if LU or empty>
    }

    Notes:
      - Payment amounts are converted to float, rounded, then to string ("0.00" if missing).
      - The reporting year (rep_year) is extracted from "Reporting period" or "Year following reporting period" (subtract 1).
      - Dynamic column names for payment fields are built based on rep_year.
    """
    import pandas as pd
    import re
    from .core_functions import create_RefId, transform_country_code

    results = []
    # --- 1) Determine the reporting year dynamically ---
    rep_year = None
    if "Reporting period" in cps_df.columns and not cps_df["Reporting period"].dropna().empty:
        try:
            rep_year = str(int(float(cps_df["Reporting period"].dropna().iloc[0])))
        except Exception:
            rep_year = None
    if rep_year is None and "Year following reporting period" in cps_df.columns and not cps_df["Year following reporting period"].dropna().empty:
        try:
            rep_year = str(int(float(cps_df["Year following reporting period"].dropna().iloc[0])) - 1)
        except Exception:
            rep_year = "2024"
    if rep_year is None:
        rep_year = "2024"

    # --- 2) Build dynamic column names based on rep_year ---
    dynamic_balance_col   = f"Account balance, i.e. sum of equity and debt interest as at 31.12.{rep_year}"
    dynamic_dividends_col = f"Distributions (dividends) during {rep_year}"
    dynamic_interest_col  = f"Interest paid/accrued in {rep_year}"
    dynamic_proceeds_col  = f"Proceeds during {rep_year}"
    dynamic_other_col     = f"Other paid/accrued in {rep_year}"
    closed_col            = f"Closed account in {rep_year} (YES/NO)"

    # --- 3) Filter rows: keep only rows where "Reporting period" exists and is not empty ---
    if "Reporting period" in cps_df.columns:
        cps_df = cps_df[cps_df["Reporting period"].notna() & (cps_df["Reporting period"].astype(str).str.strip() != "")]
    else:
        raise ValueError("Controlling section: 'Reporting period' column is missing.")

    # Dictionary to count CP for each (account, AH) pair
    ah_cp_counts = {}

    for idx, row in cps_df.iterrows():
        row_df = pd.DataFrame([row])
        if "Year following reporting period" not in row_df.columns and "Reporting period" in row_df.columns:
            row_df["Year following reporting period"] = row_df["Reporting period"]

        # A) DocSpec block
        doc_type_indic = "FATCA0" if report_type == "Zero Report" else ("FATCA1" if selection == "Initial" else "FATCA2")
        dest_code = transform_country_code(str(row.get("Tax residence of AH", "")).strip())
        raw_account = (lambda s: ("0" + s) if len(s) == 1 else s)((lambda s: s[:-2] if s.endswith(".0") else s)(str(row.get("Account Number of account holder /CP", "")).strip()))
        
        # Normalize AH name: remove spaces and convert to lowercase
        name_ah = str(row.get("Name of AH", "")).strip()
        normalized_name_ah = re.sub(r'\s+', '', name_ah).lower()
        # Create a key composed of the account number and normalized AH name
        ah_key = (raw_account, normalized_name_ah)
        
        # Increment the CP counter for each occurrence
        if ah_key not in ah_cp_counts:
            ah_cp_counts[ah_key] = 1
        else:
            ah_cp_counts[ah_key] += 1
        cp_counter = ah_cp_counts[ah_key]
        
        # Create doc_ref_id by appending "CP" followed by the counter
        doc_ref_id = create_RefId(row_df, crs_fatca, raw_account, tag="AR", DestCode=dest_code, tin="Luxembourg TIN of RFI") + "CP" + str(cp_counter)
        doc_spec = {
            "fatca:DocTypeIndic": doc_type_indic,
            "fatca:DocRefId": doc_ref_id
        }

        # B) AccountNumber block
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
        account_number = (lambda s: ("0" + s) if len(s) == 1 else s)((lambda s: s[:-2] if s.endswith(".0") else s)(str(row.get("Account Number of account holder /CP", "")).strip()))

        # C) AccountHolder block (Organisation)
        tax_res_ah  = transform_country_code(str(row.get("Tax residence of AH", "")).strip())
        tin_passive = str(row.get("TIN passive NFE", "")).strip()
        address_ah  = str(row.get("Adress of passive NFE", "")).strip()
        organisation = {
            "stffatcatypes:ResCountryCode": tax_res_ah,
            "stffatcatypes:TIN": {
                "@issuedBy": tax_res_ah,
                "#text": tin_passive
            },
            "stffatcatypes:Name": name_ah,
            "stffatcatypes:Address": {
                "stffatcatypes:CountryCode": dest_code,
                "stffatcatypes:AddressFree": address_ah
            }
        }
        account_holder = {
            "fatca:Organisation": organisation,
            "fatca:AcctHolderType": "FATCA102"
        }

        # D) SubstantialOwner block
        country_cp = str(row.get("Country of residence of CP", "")).strip()
        tax_res_cp = transform_country_code(str(row.get("Tax residence of CP", "")).strip())
        tin_cp = process_tin(str(row.get("TIN of CP", "")).strip())
        name_cp = str(row.get("Name of CP", "")).strip()
        surname_cp = str(row.get("First Name of CP") or row.get("Surname of CP") or "").strip()
        address_cp = str(row.get("Address of CP", "")).strip()
        zip_cp = str(row.get("Zip code", "")).strip()
        place_birth = str(row.get("Place of birth CP", "")).strip()
        dob_cp = str(row.get("Date of Birth CP", "")).strip()
        try:
            dt = pd.to_datetime(dob_cp)
            dob_cp = dt.strftime('%Y-%m-%dZ')
        except Exception:
            pass
        address_free_cp = f"{address_cp};{zip_cp};{country_cp}".strip(";")
        country_cp = transform_country_code(country_cp)
        controlling_person = {
            "fatca:Individual": {
                "stffatcatypes:ResCountryCode": tax_res_cp,
                "stffatcatypes:TIN": {
                    "@issuedBy": tax_res_cp,
                    "#text": tin_cp
                },
                "stffatcatypes:Name": {
                    "stffatcatypes:FirstName": surname_cp,
                    "stffatcatypes:LastName": name_cp
                },
                "stffatcatypes:Address": {
                    "stffatcatypes:CountryCode": country_cp,
                    "stffatcatypes:AddressFree": address_free_cp
                },
                "stffatcatypes:BirthInfo": {
                    "stffatcatypes:BirthDate": dob_cp,
                    "stffatcatypes:City": place_birth
                }
            }
        }

        # E) AccountBalance block
        try:
            # Retrieve the raw balance; default to 0 if the column is missing
            balance_val = float(row.get(dynamic_balance_col, 0))

            # Ensure negative balances are reset to zero
            balance_val = np.maximum(0.0, balance_val)

            # Round to the nearest whole unit and convert to string
            account_balance_str = f"{balance_val:.2f}"
        except Exception:  # Handles KeyError, ValueError, TypeError, etc.
            account_balance_str = "0.00"

        account_balance = {
            "@currCode": str(row.get("Currency", "EUR")).strip(),
            "#text": account_balance_str
        }

        # F) Payment blocks
        curr_code = str(row.get("Currency", "EUR")).strip()
        payment501 = get_payment_fatca(row, dynamic_dividends_col, "FATCA501", curr_code)
        payment502 = get_payment_fatca(row, dynamic_interest_col, "FATCA502", curr_code)
        payment503 = get_payment_fatca(row, dynamic_proceeds_col, "FATCA503", curr_code)
        payment504 = get_payment_fatca(row, dynamic_other_col, "FATCA504", curr_code)
        payments = [payment501, payment502, payment503, payment504]

        # Build final dictionary for the controlling account report.
        controlling_result = {
            "fatca:DocSpec": doc_spec,
            "fatca:AccountNumber": account_number,
            "fatca:AccountClosed": closed,
            "fatca:AccountHolder": account_holder,
            "fatca:SubstantialOwner": controlling_person,
            "fatca:AccountBalance": account_balance,
            "fatca:Payment": payments,
            "ReportableCountry": tax_res_cp
        }
        
        results.append({"fatca:AccountReport": controlling_result})
    
    return results
