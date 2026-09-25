# core_functions_begin.py
import pandas as pd
import re
from datetime import datetime
import difflib
from .core_functions import create_RefId

def get_info_CPS(CPS, postal_code_path, message_type, version, report_type, selection):
    """
    Extracts key reporting information from the CPS DataFrame and a postal code file,
    and sets additional fields based on the message type (CRS or FATCA).

    Parameters:
      CPS (DataFrame): The CPS DataFrame containing reporting information.
      postal_code_path (str): Path to an XLSX file with columns: "LOCALITE", "RUE", "CODE_POSTAL".
      message_type (str): "CRS" or "FATCA".
      version (str): Version string provided by the user.
      report_type (str): "Zero Report" or "Data Report".
      selection (str): "Initial" or "Correction".

    Returns:
      dict: A dictionary containing keys such as:
         "NameReportingFI", "IdentificationNumber", "AddressReportingFI",
         "PointOfContactReportingFI", "MessageRefId", etc.
         PLUS a new key "ReportableCountry" – set to the first non-"LU" value
         found in one of these columns: "Tax residence of Active",
         "Tax residence of PP", "Tax residence of CP", "Tax residence of AH".
         (If none are found, "ReportableCountry" is left as None.)
    """
    if CPS.empty:
        raise ValueError("La feuille CPS est vide.")

    # Vérifier si la première ligne est totalement vide
    if CPS.iloc[0].isnull().all():
        raise ValueError("La première ligne de la feuille CPS est entièrement vide.")
    # Use the first row of CPS.
    row = CPS.iloc[0]

    # Shape and column names only: the rows themselves are account holders'
    # personal data and must not reach the logs.
    logger.debug("CPS shape: %s", CPS.shape)
    logger.debug("Available columns: %s", list(CPS.columns))
    
    # 1. NameReportingFI
    NameReportingFI = str(row["Name of Reporting Financial Institution (RFI)"]).strip()
    
    # 2. IdentificationNumber (from "Luxembourg TIN of RFI")
    IdentificationNumber = str(row["Luxembourg TIN of RFI"]).strip()
    
    # 3. IdentificationNumberExtension is always:
    IdentificationNumberExtension = "M00000000"

    # 4. AddressReportingFI: process the "code Postal and country of RFI" column 
    AddressReportingFI = get_address_RFI_new(CPS.iloc[0], postal_code_path)

    # 5. PointOfContactReportingFI
    if "First Name of point of contact (POC) of RFI" in row:
        FirstName = str(row["First Name of point of contact (POC) of RFI"]).strip()
        NamePOC = str(row["Name of point of contact (POC) of RFI"]).strip()
    else:
        full_name_poc = str(row["Name of point of contact (POC) of RFI"]).strip()
        parts = full_name_poc.split()
        if len(parts) >= 2:
            FirstName = " ".join(parts[:-1])
            NamePOC = parts[-1]
        else:
            FirstName = full_name_poc
            NamePOC = ""
    
    email = str(row["E-mail of POC of RFI"]).strip()
    TelephoneDirect = str(row["Phone number of POC of RFI"]).strip()
    PointOfContactReportingFI = {
        "Name": NamePOC,
        "FirstName": FirstName,
        "EmailPersonal": email,
        "EmailOrganisation": email,
        "TelephoneDirect": TelephoneDirect
    }
    
    # 6. Determine the reporting year from "Reporting period"
    year_values = CPS["Reporting period"].dropna().unique()
    try:
        year_int = int(float(year_values[0]))
        year_str = str(year_int)
    except Exception as e:
        raise ValueError("Cannot convert 'Year following reporting period' to a valid integer.") from e

    # 7. Determine ReportableCountry from tax-residence columns (if any non-LU value exists)
    reportable_country = None
    for col in ["Tax residence of Active", "Tax residence of PP", "Tax residence of CP", "Tax residence of AH"]:
        if col in row and pd.notna(row[col]):
            rc = str(row[col]).strip()
            if rc.upper() != "LU" and rc != "":
                reportable_country = rc
                break

    # 8. Assemble and return the result dictionary.
    result = {
        "NameReportingFI": NameReportingFI,
        "IdentificationNumber": IdentificationNumber,
        "IdentificationNumberExtension": IdentificationNumberExtension,
        "RFI_Identifier": IdentificationNumber + IdentificationNumberExtension,
        "AddressReportingFI": AddressReportingFI,
        "PointOfContactReportingFI": PointOfContactReportingFI,
        "SendingCompanyIN": IdentificationNumber,
        "TransmittingCountry": "LU",
        "MessageType": message_type,
        "ReceivingCountry": "LU" if message_type.upper() == "CRS" else "US",
        "AEOI_RefId": create_RefId(CPS, message_type, version, tag="HL"),
        "MessageRefId": create_RefId(CPS, message_type, version, tag="HC"),
        "ReportingPeriod": f"{year_str}-12-31Z",
        "Timestamp": datetime.utcnow().isoformat(timespec='milliseconds') + "Z",
        "ResCountryCode": "LU",
        "IN": IdentificationNumber,
        "issuedBy": "LU",
        "Name": NameReportingFI,
        "CountryCode": "LU",
        "AddressFix": {
            "Street": AddressReportingFI.get("aeoi_lux:StreetPhysical", ""),
            "BuildingIdentifier": AddressReportingFI.get("aeoi_lux:NumberPhysical", ""),
            "PostCode": AddressReportingFI.get("aeoi_lux:PostalCodePhysical", ""),
            "City": AddressReportingFI.get("aeoi_lux:CityPhysical", "")
        },
        "SuiteIdentifier": "",
        "DocTypeIndic": (
            "OECD1" if (report_type == "Zero Report" or selection == "Initial") else "OECD2"
        ) if message_type.upper() == "CRS" else (
            "FATCA1" if selection == "Initial" else "FATCA2"
        ),
        "ReportableCountry": reportable_country  # new key
    }
    
    if message_type.upper() == "CRS":
        if report_type == "Zero Report":
            result["MessageTypeIndic"] = "CRS703"
        else:
            result["MessageTypeIndic"] = "CRS701" if selection == "Initial" else "CRS702"
    # 9. For FATCA: Import "GIIN of RFI"
    try:
        GIINofRFI = str(row["GIIN of RFI"]).strip()
    except (KeyError, TypeError, AttributeError) as e:
        GIINofRFI = None  # ou une autre valeur par défaut
        logger.debug("Erreur lors de l'extraction de 'GIIN of RFI' : %s", type(e).__name__)

    # Save the original CPS DataFrame for later use.
    result["RawData"] = CPS
    result["BeaconVersion"] = version
    result["GIINofRFI"] = GIINofRFI
    
    return result

_postal_df_cache = {}
def get_address_RFI(row, postal_code_path):
    """
    Extracts and returns a structured address of the Reporting Financial Institution (RFI)
    from the CPS row and a postal code reference file.

    Handles:
    - Inconsistent street naming (e.g., apostrophes, accents, case)
    - Address with comma for building number or digits in the street name
    - Multiple matches for postal codes using best-fit logic
    - Missing or malformed data with safe fallbacks

    Returns:
        dict: {
            "aeoi_lux:StreetPhysical": ...,
            "aeoi_lux:NumberPhysical": ...,
            "aeoi_lux:PostalCodePhysical": ...,
            "aeoi_lux:CityPhysical": ...,
            "aeoi_lux:CountryPhysical": "LU"
        }
    """
    import pandas as pd
    import difflib
    import re
    import unicodedata

    def normalize(s):
        """Lowercase, remove accents, apostrophes, commas and extra spaces."""
        s = str(s).lower().replace("'", "").replace(",", " ")
        s = ''.join(
            c for c in unicodedata.normalize('NFKD', s)
            if not unicodedata.combining(c)
        )
        # Retire les espaces multiples
        s = ' '.join(s.split())
        return s.strip()

    global _postal_df_cache

    # --- Step 1: Extract postal code ---
    postal_raw = str(row.get("code Postal and country of RFI", "")).strip()
    match_code = re.search(r'(\d{3,5})', postal_raw)
    code_digits = match_code.group(1) if match_code else ""
    PostalCodePhysical = f"L-{code_digits}" if code_digits else ""
    CountryPhysical = "LU"

    # --- Step 2: Load (cached) postal code file ---
    if postal_code_path in _postal_df_cache:
        postal_df = _postal_df_cache[postal_code_path]
    else:
        try:
            postal_df = pd.read_excel(postal_code_path)
            postal_df["CODE_POSTAL"] = postal_df["CODE_POSTAL"].astype(str).str.strip()
            _postal_df_cache[postal_code_path] = postal_df
        except Exception as e:
            raise ValueError(f"Error reading postal code file: {e}")

    filtered = postal_df[postal_df["CODE_POSTAL"] == PostalCodePhysical]
    street_value, city_value, number = "", "", ""

    # --- Step 3: Find best street match (fuzzy) & city ---
    address_full = str(row.get("Address of RFI", "")).strip()
    address_norm = normalize(address_full)

    if not filtered.empty:
        # On récupère la liste de rues candidates
        candidate_streets = filtered["RUE"].astype(str).tolist()
        norm_candidates = [normalize(r) for r in candidate_streets]

        # Fuzzy matching : cherche la meilleure rue
        best_matches = difflib.get_close_matches(address_norm, norm_candidates, n=1, cutoff=0.3)
        if best_matches:
            best_match_norm = best_matches[0]
            # Récupère l'index et donc la ligne correspondante
            idx = norm_candidates.index(best_match_norm)
            best_row = filtered.iloc[idx]
        else:
            # Si pas de match, on prend la première comme fallback
            best_row = filtered.iloc[0]

        # Récupère la rue "propre" et la ville
        street_value = str(best_row["RUE"]).replace("'", " ").strip()
        city_value = str(best_row["LOCALITE"]).strip()

        # --- Step 4: Soustraire la portion "rue" de l'adresse pour isoler le numéro ---
        # On enlève la rue normalisée de l'adresse normalisée
        address_no_street = address_norm.replace(best_match_norm, "", 1)
        # Nettoyage basique des espaces/doubles espaces
        address_no_street = ' '.join(address_no_street.split())

        # On peut également supprimer les virgules résiduelles si besoin
        address_no_street = address_no_street.replace(",", " ")
        address_no_street = ' '.join(address_no_street.split())

        # Recherche d'un numéro de type 123, 123B, 42bis, etc.
        match_number = re.search(r'(\d+[A-Za-z]{0,3})', address_no_street)
        number = match_number.group(1) if match_number else ""
    else:
        logger.debug("Postal code %r not found in reference.", PostalCodePhysical)

    # --- Step 5: Return result ---
    return {
        "aeoi_lux:StreetPhysical": street_value,
        "aeoi_lux:NumberPhysical": number,
        "aeoi_lux:PostalCodePhysical": PostalCodePhysical,
        "aeoi_lux:CityPhysical": city_value,
        "aeoi_lux:CountryPhysical": CountryPhysical
    }


import pandas as pd
import logging
import re
import unicodedata
from rapidfuzz import process

# Global cache for the postal code reference file
_postal_df_cache = {}
# Logger for tracking errors and warnings
logger = logging.getLogger(__name__)

def get_address_RFI_new(row, postal_code_path):
    """
    Extracts and returns a structured address of the Reporting Financial Institution (RFI)
    from a CPS row and a postal code reference file.

    Args:
        row: A mapping containing keys "Address of RFI" and
             "code Postal and country of RFI".
        postal_code_path: Path to the Excel or CSV file of postal codes.

    Returns:
        dict with keys:
            "aeoi_lux:StreetPhysical", "aeoi_lux:NumberPhysical",
            "aeoi_lux:PostalCodePhysical", "aeoi_lux:CityPhysical",
            "aeoi_lux:CountryPhysical"
    """
    def normalize(text: str) -> str:
        text = unicodedata.normalize('NFKD', str(text)).lower()
        text = re.sub(r"['’]", "", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def extract_number(text: str) -> str:
        match = re.search(r"\b(\d{1,4}(?:bis|ter)?[A-Za-z°\-]*)\b", text)
        return match.group(1) if match else ""

    def normalize_postal(s: str) -> str:
        # Match 3 to 5 digits with optional spaces around dash
        m = re.search(r"\b(\d{3,5})\b", str(s))
        return f"L-{m.group(1)}" if m else ""

    # Step 1: Extract postal code
    postal_raw = str(row.get("code Postal and country of RFI", "")).strip()
    postal_code = normalize_postal(postal_raw)
    country = "LU"

    # Extract municipality: remove any 'L - 1234' or 'L-1234' pattern, keep hyphens
    raw_municipality = re.sub(r"\bL\s*-\s*\d{3,5}\b", "", postal_raw, flags=re.IGNORECASE)
    raw_municipality = raw_municipality.strip(" ,-\t").title()

    # Step 2: Load and cache postal reference
    if postal_code_path in _postal_df_cache:
        df = _postal_df_cache[postal_code_path]
    else:
        if postal_code_path.lower().endswith(".csv"):
            df = pd.read_csv(postal_code_path, dtype=str)
        else:
            df = pd.read_excel(postal_code_path, dtype=str)
        df["CODE_POSTAL"] = df["CODE_POSTAL"].astype(str).str.upper().str.strip()
        _postal_df_cache[postal_code_path] = df
    df_filtered = df[df["CODE_POSTAL"] == postal_code]

    # Fallback if postal code not found
    if df_filtered.empty:
        street_fallback = str(row.get("Address of RFI", "")).strip()
        number_fallback = extract_number(street_fallback)
        # remove leading punctuation
        street_fallback = re.sub(r"^[^\w]+", "", street_fallback)
        return {
            "aeoi_lux:StreetPhysical": street_fallback.strip(','),
            "aeoi_lux:NumberPhysical": number_fallback,
            "aeoi_lux:PostalCodePhysical": postal_code,
            "aeoi_lux:CityPhysical": raw_municipality,
            "aeoi_lux:CountryPhysical": country
        }

    # Step 3: Extract number and prepare street guess
    raw_address = str(row.get("Address of RFI", ""))
    number_value = extract_number(raw_address)
    street_guess = raw_address
    if number_value:
        # remove only first occurrence to preserve street names with numbers
        street_guess = street_guess.replace(number_value, "", 1)
    street_guess_norm = normalize(street_guess)

    # Step 4: Fuzzy match street
    reference_streets = df_filtered["RUE"].astype(str).tolist()
    match = process.extractOne(street_guess_norm, reference_streets, score_cutoff=60)
    if match:
        street_value = match[0]
    else:
        # fallback to raw guess without leading punctuation
        street_value = re.sub(r"^[^\w]+", "", street_guess.strip())

    # Step 5: Determine city without postal code
    reference_city = df_filtered["LOCALITE"].astype(str).iloc[0]
    # choose the longest non-empty: raw_municipality or reference_city
    city_candidate = raw_municipality if len(raw_municipality) > len(reference_city) else reference_city
    # ensure no digits or stray dashes at ends
    city_value = re.sub(r"\d", "", city_candidate).strip(" ,-")

    # Return structured address
    return {
        "aeoi_lux:StreetPhysical": street_value.strip(','),
        "aeoi_lux:NumberPhysical": number_value,
        "aeoi_lux:PostalCodePhysical": postal_code,
        "aeoi_lux:CityPhysical": city_value,
        "aeoi_lux:CountryPhysical": country
    }