#core_functions_data_notificationV2.py
import os
import sys
import re
import zipfile
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
try:
    from docx2pdf import convert
except Exception:
    def convert(*a, **k):
        raise RuntimeError('docx2pdf/MS Word not available on this server')
import pandas as pd
from .core_functions import *
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Determine current directory (for relative paths)
# -------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))

# -------------------------------------------------------------------
# Configuration – ne touchez pas aux chemins vers les fichiers DOCX !
# -------------------------------------------------------------------
template_individual_docx_path = os.path.join(current_dir, "DATA PROTECTION NOTIFICATION_Individual.docx")
template_active_docx_path = os.path.join(current_dir, "DATA PROTECTION NOTIFICATION_Active.docx")
template_controlling_docx_path = os.path.join(current_dir, "DATA PROTECTION NOTIFICATION_Controlling.docx")
template_passive_docx_path = os.path.join(current_dir, "DATA PROTECTION NOTIFICATION_Passive-CP.docx")
output_dir = os.path.join(current_dir, "Results")

# -------------------------------------------------------------------
# Namespaces utilisés dans le XML
# -------------------------------------------------------------------
ns = {
    "crs": "urn:oecd:ties:crs:v2",
    "aeoi_crs": "urn:lu:etat:acd:aeoi_crs:v2.0",
    "aeoi_lux": "urn:lu:etat:acd:aeoi_lux:v3.0",
    "aeoi_lux_fatca": "urn:lu:etat:acd:aeoi_fatca:v3.0",
    "commontypesfatcacrs": "urn:oecd:ties:commontypesfatcacrs:v2",
    "crsstf": "urn:oecd:ties:crsstf:v5",
    "fatca": "urn:lu:etat:acd:fatca:v2.0",
    "stffatcatypes": "urn:oecd:ties:stffatcatypes:v2"
}

# -------------------------------------------------------------------
# Fonction utilitaire : mise en forme de la période de reporting
# -------------------------------------------------------------------
def format_reporting_period(period_str):
    try:
        dt = datetime.strptime(period_str.rstrip("Z"), "%Y-%m-%d")
    except Exception:
        return period_str
    day = dt.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} of {dt.strftime('%B')}, {dt.year}"

# -------------------------------------------------------------------
# Extraction des informations globales pour CRS
# -------------------------------------------------------------------
def build_overall_info(root):
    overall = {}
    reportingFI = root.find(".//aeoi_crs:AEOI_ReportingFI", ns)
    if reportingFI is not None:
        overall["aeoi_lux:NameReportingFI"] = reportingFI.findtext("aeoi_lux:NameReportingFI", default="N/A", namespaces=ns)
        adr = reportingFI.find("aeoi_lux:AddressReportingFI", ns)
        if adr is not None:
            overall["AddressReportingFI"] = {
                "aeoi_lux:StreetPhysical": adr.findtext("aeoi_lux:StreetPhysical", default="", namespaces=ns),
                "aeoi_lux:NumberPhysical": adr.findtext("aeoi_lux:NumberPhysical", default="", namespaces=ns),
                "aeoi_lux:PostalCodePhysical": adr.findtext("aeoi_lux:PostalCodePhysical", default="", namespaces=ns),
                "aeoi_lux:CityPhysical": adr.findtext("aeoi_lux:CityPhysical", default="", namespaces=ns),
                "aeoi_lux:CountryPhysical": adr.findtext("aeoi_lux:CountryPhysical", default="", namespaces=ns)
            }
        else:
            overall["AddressReportingFI"] = {}
        overall["AddressFix"] = {
            "PostCode": overall["AddressReportingFI"].get("aeoi_lux:PostalCodePhysical", ""),
            "Country": overall["AddressReportingFI"].get("aeoi_lux:CountryPhysical", "")
        }
        poc = reportingFI.find("aeoi_lux:PointOfContactReportingFI", ns)
        if poc is not None:
            overall["PointOfContactReportingFI"] = {
                "aeoi_lux:FirstName": poc.findtext("aeoi_lux:FirstName", default="N/A", namespaces=ns),
                "aeoi_lux:Name": poc.findtext("aeoi_lux:Name", default="N/A", namespaces=ns),
                "aeoi_lux:TelephoneDirect": poc.findtext("aeoi_lux:TelephoneDirect", default="N/A", namespaces=ns),
                "aeoi_lux:EmailPersonal": poc.findtext("aeoi_lux:EmailPersonal", default="N/A", namespaces=ns)
            }
        else:
            overall["PointOfContactReportingFI"] = {}
    else:
        overall["aeoi_lux:NameReportingFI"] = "N/A"
        overall["AddressReportingFI"] = {}
        overall["AddressFix"] = {}
        overall["PointOfContactReportingFI"] = {}
    overall["ReportingPeriod"] = root.findtext(".//crs:MessageSpec/crs:ReportingPeriod", default="N/A", namespaces=ns)
    return overall

# -------------------------------------------------------------------
# Extraction des informations globales pour FATCA
# (Les données à remplir dans les templates Word sont les mêmes)
# -------------------------------------------------------------------
def build_overall_info_fatca(root):
    overall = {}
    # Dans votre FATCA, les infos globales se trouvent sous <aeoi_lux_fatca:AEOI_ReportingFI>
    reportingFI = root.find(".//aeoi_lux_fatca:AEOI_ReportingFI", ns)
    if reportingFI is not None:
        overall["fatca:NameReportingFI"] = reportingFI.findtext("aeoi_lux:NameReportingFI", default="N/A", namespaces=ns)
        adr = reportingFI.find("aeoi_lux:AddressReportingFI", ns)
        if adr is not None:
            overall["AddressReportingFI"] = {
                "aeoi_lux:StreetPhysical": adr.findtext("aeoi_lux:StreetPhysical", default="", namespaces=ns),
                "aeoi_lux:NumberPhysical": adr.findtext("aeoi_lux:NumberPhysical", default="", namespaces=ns),
                "aeoi_lux:PostalCodePhysical": adr.findtext("aeoi_lux:PostalCodePhysical", default="", namespaces=ns),
                "aeoi_lux:CityPhysical": adr.findtext("aeoi_lux:CityPhysical", default="", namespaces=ns),
                "aeoi_lux:CountryPhysical": adr.findtext("aeoi_lux:CountryPhysical", default="", namespaces=ns)
            }
        else:
            overall["AddressReportingFI"] = {}
        overall["AddressFix"] = {
            "PostCode": overall["AddressReportingFI"].get("aeoi_lux:PostalCodePhysical", ""),
            "Country": overall["AddressReportingFI"].get("aeoi_lux:CountryPhysical", "")
        }
        poc = reportingFI.find("aeoi_lux:PointOfContactReportingFI", ns)
        if poc is not None:
            overall["PointOfContactReportingFI"] = {
                "aeoi_lux:FirstName": poc.findtext("aeoi_lux:FirstName", default="N/A", namespaces=ns),
                "aeoi_lux:Name": poc.findtext("aeoi_lux:Name", default="N/A", namespaces=ns),
                "aeoi_lux:TelephoneDirect": poc.findtext("aeoi_lux:TelephoneDirect", default="N/A", namespaces=ns),
                "aeoi_lux:EmailPersonal": poc.findtext("aeoi_lux:EmailPersonal", default="N/A", namespaces=ns)
            }
        else:
            overall["PointOfContactReportingFI"] = {}
    else:
        overall["fatca:NameReportingFI"] = "N/A"
        overall["AddressReportingFI"] = {}
        overall["AddressFix"] = {}
        overall["PointOfContactReportingFI"] = {}
    overall["ReportingPeriod"] = root.findtext(".//aeoi_lux_fatca:ReportingPeriod", default="N/A", namespaces=ns)
    return overall

# -------------------------------------------------------------------
# Fonctions de parsing et mapping CRS (inchangées)
# -------------------------------------------------------------------
def parse_individual(ind_elem, ns):
    data = {}
    if ind_elem is None:
        return data
    first_name = ind_elem.findtext("crs:Name/crs:FirstName", default="", namespaces=ns).strip()
    last_name  = ind_elem.findtext("crs:Name/crs:LastName", default="", namespaces=ns).strip()
    data['Name_of_PP'] = first_name if first_name else "N/A"
    data['Surname_of_PP_'] = last_name if last_name else "N/A"
    addr_free = ind_elem.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
    data['Adress_of_PP'] = addr_free.text.strip() if addr_free is not None and addr_free.text else "N/A"
    country_elem = ind_elem.find("crs:Address/commontypesfatcacrs:CountryCode", ns)
    data['Country_of_residence_of_PP'] = country_code_to_name(country_elem.text.strip()) if country_elem is not None and country_elem.text else "N/A"
    data['TIN_PP'] = ind_elem.findtext("crs:TIN", default="N/A", namespaces=ns).strip()
    birth = ind_elem.find("crs:BirthInfo", ns)
    if birth is not None:
        data['Date_of_Birth'] = birth.findtext("crs:BirthDate", default="N/A", namespaces=ns).rstrip("Z").strip()
        data['Place_of_birth'] = birth.findtext("crs:City", default="N/A", namespaces=ns).strip()
    else:
        data['Date_of_Birth'] = "N/A"
        data['Place_of_birth'] = "N/A"
    tax_code = ind_elem.findtext("crs:ResCountryCode", default="", namespaces=ns).strip()
    data['Tax_residence_of_PP'] = country_code_to_name(tax_code) if tax_code else "N/A"
    return data

def parse_entity(org_elem, ns):
    data = {}
    if org_elem is None:
        return data
    data['Name_of_AH_'] = org_elem.findtext("crs:Name", default="N/A", namespaces=ns).strip()
    addr_free = org_elem.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
    data['Adress_of_passive__NFE_'] = addr_free.text.strip() if addr_free is not None and addr_free.text else "N/A"
    country_elem = org_elem.find("crs:Address/commontypesfatcacrs:ResCountryCode", ns)
    data['Tax_residence_of_AH'] = country_elem.text.strip() if country_elem is not None and country_elem.text else "N/A"
    data['TIN_passive_NFE'] = org_elem.findtext("crs:IN", default="N/A", namespaces=ns).strip()
    return data

def build_mapping_individual(account_report, overall):
    mapping = {}
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("aeoi_lux:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) if any(components) else "N/A"
    fix = overall.get("AddressFix", {})
    postal = fix.get("PostCode", "").strip()
    country = country_code_to_name(fix.get("Country", "").strip())
    mapping["code_Postal_and_country_of_RFI"] = f"{postal} {country}".strip() if postal or country else "N/A"
    
    # Reporting period    
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1)

    # Today’s date
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (poc.get("aeoi_lux:FirstName", "N/A") + " " + poc.get("aeoi_lux:Name", "N/A")).strip()
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")
    indiv = account_report.find("crs:AccountHolder/crs:Individual", ns)
    if indiv is None:
        logger.warning("Warning: No individual element found in AccountHolder; skipping this account.")
        return None
    ind_data = parse_individual(indiv, ns)
    mapping.update(ind_data)
    mapping["Account_Number_of_account_holder_"] = account_report.findtext("crs:AccountNumber", default="N/A", namespaces=ns).strip()
    accnum_elem = account_report.find("crs:AccountNumber", ns)
    mapping["Closed_account_in_2023_YESNO"] = accnum_elem.get("ClosedAccount", "N/A") if accnum_elem is not None else "N/A"
    pays = {"CRS501": "0.00", "CRS502": "0.00", "CRS503": "0.00", "CRS504": "0.00"}
    for pay in account_report.findall("crs:Payment", ns):
        typ = pay.findtext("crs:Type", default="", namespaces=ns)
        amt = pay.findtext("crs:PaymentAmnt", default="0.00", namespaces=ns)
        try:
            pays[typ] = "{:,.2f}".format(float(amt.strip()))
        except Exception:
            pays[typ] = "0.00"
    mapping["Distributions_dividends_during_2023"] = pays.get("CRS501", "0.00")
    mapping["Interest_paidaccrued_in_2023"] = pays.get("CRS502", "0.00")
    mapping["Proceeds_during_2023"] = pays.get("CRS503", "0.00")
    mapping["Other_paidaccrued_in_2023"] = pays.get("CRS504", "0.00")
    bal = account_report.find("crs:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "{:,.2f}".format(float(bal.text.strip()))
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"

    # — US TIN if tax residence is US —
    mapping["US_TIN_of_account_holder_if_applicable"] = (
        mapping.get("TIN_PP")
        if mapping.get("Tax_residence_of_PP") == "US"
        else "N/A"
    )

    for k, v in mapping.items():
        if v is None or str(v).strip() == "":
            mapping[k] = "N/A"
    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.
    return mapping

# ------------------------------------------------------------------------------
# Build mapping for controlling persons
# ------------------------------------------------------------------------------
def build_mapping_controlling(account_report, overall):
    mapping = {}
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("aeoi_lux:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) if any(components) else "N/A"
    fix = overall.get("AddressFix", {})
    postal = fix.get("PostCode", "").strip()
    country = country_code_to_name(fix.get("Country", "").strip())
    mapping["code_Postal_and_country_of_RFI"] = f"{postal} {country}".strip() if postal or country else "N/A"
    
    # Reporting period  
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1)

    # Today’s date
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (poc.get("aeoi_lux:FirstName", "N/A") + " " + poc.get("aeoi_lux:Name", "N/A")).strip()
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")
    cp = account_report.find("crs:ControllingPerson/crs:Individual", ns)
    if cp is not None:
        mapping["Surname_of_CP_"] = cp.findtext("crs:Name/crs:LastName", default="N/A", namespaces=ns).strip()
        mapping["Name_of_CP"] = cp.findtext("crs:Name/crs:FirstName", default="N/A", namespaces=ns).strip()
        addr_cp = cp.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
        mapping["Address_of_CP"] = addr_cp.text.strip() if addr_cp is not None and addr_cp.text else "N/A"
        mapping["Zip_code"] = postal if postal else "N/A"
        mapping["TIN_of_CP"] = cp.findtext("crs:TIN", default="N/A", namespaces=ns).strip()
        birth_cp = cp.find("crs:BirthInfo", ns)
        if birth_cp is not None:
            mapping["Date_of_Birth_CP"] = birth_cp.findtext("crs:BirthDate", default="N/A", namespaces=ns).rstrip("Z").strip()
            mapping["Place_of_birth_CP"] = birth_cp.findtext("crs:City", default="N/A", namespaces=ns).strip()
        else:
            mapping["Date_of_Birth_CP"] = "N/A"
            mapping["Place_of_birth_CP"] = "N/A"
        mapping["Account_Number_of_account_holder_CP"] = account_report.findtext("crs:AccountNumber", default="N/A", namespaces=ns).strip()
        mapping["Tax_residence_of_CP"] = country_code_to_name(cp.findtext("crs:ResCountryCode", default="N/A", namespaces=ns).strip())
        # — US TIN if tax residence is US —
        mapping["USTINCP"] = (
            mapping.get("TIN_of_CP")
            if cp.findtext("crs:ResCountryCode", default="N/A", namespaces=ns).strip() == "US"
            else "N/A"
        )
    else:
        mapping["Surname_of_CP_"] = "N/A"
        mapping["Name_of_CP"] = "N/A"
        mapping["Address_of_CP"] = "N/A"
        mapping["Zip_code"] = "N/A"
        mapping["TIN_of_CP"] = "N/A"
        mapping["Date_of_Birth_CP"] = "N/A"
        mapping["Place_of_birth_CP"] = "N/A"
        mapping["Account_Number_of_account_holder_CP"] = "N/A"
        mapping["Tax_residence_of_CP"] = "N/A"
        mapping["USTINCP"] = "N/A"
    org = account_report.find("crs:AccountHolder/crs:Organisation", ns)
    if org is not None:
        mapping["Name_of_AH_"] = org.findtext("crs:Name", default="N/A", namespaces=ns).strip()
        mapping["Adress_of_passive__NFE_"] = org.findtext("crs:Address/commontypesfatcacrs:AddressFree", default="N/A", namespaces=ns).strip()
        mapping["Tax_residence_of_AH"] = country_code_to_name(org.findtext("crs:Address/commontypesfatcacrs:CountryCode", default="N/A", namespaces=ns).strip())
        mapping["TIN_passive_NFE"] = org.findtext("crs:IN", default="N/A", namespaces=ns).strip()
    else:
        mapping["Name_of_AH_"] = "N/A"
        mapping["Adress_of_passive__NFE_"] = "N/A"
        mapping["Tax_residence_of_AH"] = "N/A"
        mapping["TIN_passive_NFE"] = "N/A"
    bal = account_report.find("crs:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "{:,.2f}".format(float(bal.text.strip()))
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"

    pays = {"CRS501": "0.00", "CRS502": "0.00", "CRS503": "0.00", "CRS504": "0.00"}
    for p in account_report.findall("crs:Payment", ns):
        typ = p.findtext("crs:Type", default="", namespaces=ns)
        amt = p.findtext("crs:PaymentAmnt", default="0.00", namespaces=ns)
        try:
            pays[typ] = "{:,.2f}".format(float(amt.strip()))
        except Exception:
            pays[typ] = "0.00"
    mapping["Distributions_dividends_during_2023"] = pays.get("CRS501", "0.00")
    mapping["Interest_paidaccrued_in_2023"] = pays.get("CRS502", "0.00")
    mapping["Proceeds_during_2023"] = pays.get("CRS503", "0.00")
    mapping["Other_paidaccrued_in_2023"] = pays.get("CRS504", "0.00")
    for k, v in mapping.items():
        if v is None or str(v).strip() == "":
            mapping[k] = "N/A"
    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.
    return mapping

# ------------------------------------------------------------------------------
# Build mapping for active entity account holders
# ------------------------------------------------------------------------------
def build_mapping_active(account_report, overall):
    mapping = {}
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("aeoi_lux:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) if any(components) else "N/A"
    fix = overall.get("AddressFix", {})
    postal = fix.get("PostCode", "").strip()
    country = country_code_to_name(fix.get("Country", "").strip())
    mapping["code_Postal_and_country_of_RFI"] = f"{postal} {country}".strip() if postal or country else "N/A"

    # Reporting period
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1)

    # Today’s date
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (poc.get("aeoi_lux:FirstName", "N/A") + " " + poc.get("aeoi_lux:Name", "N/A")).strip()
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")
    
    org = account_report.find("crs:AccountHolder/crs:Organisation", ns)
    if org is not None:
        # Utiliser parse_entity pour récupérer les infos de base de l'entité
        ent_data = parse_entity(org, ns)
        mapping.update(ent_data)
        mapping["Name_of_Active"] = mapping.get("Name_of_AH_", "N/A")
        # Pour l'adresse active, on cherche le contenu de AddressFree
        addr_free_active = org.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
        if addr_free_active is not None and addr_free_active.text:
            mapping["Adress_of_Active_NFE_"] = addr_free_active.text.strip()
        else:
            mapping["Adress_of_Active_NFE_"] = "N/A"
        # Pour Code_and_Country_of_Active_NFE, on peut réutiliser les données globales (postal et country)
        country_elem = org.find("crs:Address/commontypesfatcacrs:CountryCode", ns)
        mapping["Code_and_Country_of_Active_NFE"] = country_code_to_name(country_elem.text.strip()) if country_elem is not None and country_elem.text else "N/A"

        # Pour Tax_residence_of_Active_, tenter de récupérer le CountryCode dans l'adresse de l'entité
        active_country = org.find("crs:ResCountryCode", ns)
        if active_country is not None and active_country.text:
            mapping["Tax_residence_of_Active_"] = country_code_to_name(active_country.text.strip())
        else:
            mapping["Tax_residence_of_Active_"] = "N/A"
        # Pour TIN_active_NFE, utiliser l'élément IN
        mapping["TIN_active_NFE"] = org.findtext("crs:IN", default="N/A", namespaces=ns).strip()
    else:
        mapping["Name_of_Active"] = "N/A"
        mapping["Adress_of_Active_NFE_"] = "N/A"
        mapping["Code_and_Country_of_Active_NFE"] = "N/A"
        mapping["Tax_residence_of_Active_"] = "N/A"
        mapping["TIN_active_NFE"] = "N/A"

    # — US TIN if tax residence is US —
    mapping["US_TIN_of_account_holder_if_applicable"] = (
        mapping.get("TIN_active_NFE")
        if mapping.get("Tax_residence_of_Active_") == "US"
        else "N/A"
    )

    mapping["Account_Number_of_account_holder_"] = account_report.findtext("crs:AccountNumber", default="N/A", namespaces=ns).strip()
    accnum_elem = account_report.find("crs:AccountNumber", ns)
    mapping["Closed_account_in_2023_YESNO"] = accnum_elem.get("ClosedAccount", "N/A") if accnum_elem is not None else "N/A"
    pays = {"CRS501": "0.00", "CRS502": "0.00", "CRS503": "0.00", "CRS504": "0.00"}
    for p in account_report.findall("crs:Payment", ns):
        typ = p.findtext("crs:Type", default="", namespaces=ns)
        amt = p.findtext("crs:PaymentAmnt", default="0.00", namespaces=ns)
        try:
            pays[typ] = "{:,.2f}".format(float(amt.strip()))
        except Exception:
            pays[typ] = "0.00"
    mapping["Distributions_dividends_during_2023"] = pays.get("CRS501", "0.00")
    mapping["Interest_paidaccrued_in_2023"] = pays.get("CRS502", "0.00")
    mapping["Proceeds_during_2023"] = pays.get("CRS503", "0.00")
    mapping["Other_paidaccrued_in_2023"] = pays.get("CRS504", "0.00")
    bal = account_report.find("crs:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "{:,.2f}".format(float(bal.text.strip()))
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"
    
    for k, v in mapping.items():
        if v is None or str(v).strip() == "":
            mapping[k] = "N/A"
            
    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.
    return mapping

# -------------------------------------------------------------------
# Fonctions de mapping FATCA (elles reprennent la même structure que CRS)
# -------------------------------------------------------------------
def parse_fatca_individual(ind_elem, ns):
    data = {}
    if ind_elem is None:
        return data
    # On récupère les mêmes champs que pour CRS mais en remplaçant "crs:" par "fatca:"
    first_name = ind_elem.findtext("stffatcatypes:Name/stffatcatypes:FirstName", default="", namespaces=ns).strip()
    last_name  = ind_elem.findtext("stffatcatypes:Name/stffatcatypes:LastName",  default="", namespaces=ns).strip()
    data['Name_of_PP'] = first_name if first_name else "N/A"
    data['Surname_of_PP_'] = last_name if last_name else "N/A"
    addr_free   = ind_elem.find("stffatcatypes:Address/stffatcatypes:AddressFree", ns)
    data['Adress_of_PP'] = addr_free.text.strip() if addr_free is not None and addr_free.text else "N/A"
    country_elem = ind_elem.find("stffatcatypes:Address/stffatcatypes:CountryCode", ns)
    data['Country_of_residence_of_PP'] = country_code_to_name(country_elem.text.strip()) if country_elem is not None and country_elem.text else "N/A"
    data['TIN_PP'] = ind_elem.findtext("stffatcatypes:TIN", default="N/A", namespaces=ns).strip()

    birth = ind_elem.find("stffatcatypes:BirthInfo", ns)
    if birth is not None:
        data['Date_of_Birth']  = birth.findtext("stffatcatypes:BirthDate", default="N/A", namespaces=ns).rstrip("Z").strip()
        data['Place_of_birth'] = birth.findtext("stffatcatypes:City",      default="N/A", namespaces=ns).strip()
    else:
        data['Date_of_Birth'] = "N/A"
        data['Place_of_birth'] = "N/A"
    tax_code = ind_elem.findtext("stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
    data['Tax_residence_of_PP'] = country_code_to_name(tax_code) if tax_code else "N/A"
    return data

def build_mapping_fatca_individual(account_report, overall):
    mapping = {}
    # Récupérer l'info globale FATCA (extraction via build_overall_info_fatca)
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("fatca:NameReportingFI", "N/A")
    # Récupération de l'individual dans le compte
    indiv = account_report.find("fatca:AccountHolder/fatca:Individual", ns)
    if indiv is None:
        logger.warning("Warning: No FATCA individual element found; skipping this account.")
        return None
    ind_data = parse_fatca_individual(indiv, ns)
    mapping.update(ind_data)
    mapping["Account_Number_of_account_holder_"] = account_report.findtext("fatca:AccountNumber", default="N/A", namespaces=ns).strip()
    mapping["Closed_account_in_2023_YESNO"] = account_report.findtext(
        "fatca:AccountClosed",
        default="N/A",
        namespaces=ns
    ).strip()
    pays = {"FATCA501": "0.00", "FATCA502": "0.00", "FATCA503": "0.00", "FATCA504": "0.00"}
    for pay in account_report.findall("fatca:Payment", ns):
        typ = pay.findtext("fatca:Type", default="", namespaces=ns)
        amt = pay.findtext("fatca:PaymentAmnt", default="0.00", namespaces=ns)
        try:
            pays[typ] = "{:,.2f}".format(float(amt.strip()))
        except Exception:
            pays[typ] = "0.00"
    mapping["Distributions_dividends_during_2023"] = pays.get("FATCA501", "0.00")
    mapping["Interest_paidaccrued_in_2023"] = pays.get("FATCA502", "0.00")
    mapping["Proceeds_during_2023"] = pays.get("FATCA503", "0.00")
    mapping["Other_paidaccrued_in_2023"] = pays.get("FATCA504", "0.00")
    bal = account_report.find("fatca:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "{:,.2f}".format(float(bal.text.strip()))
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"

    # — US TIN if tax residence is US —
    mapping["US_TIN_of_account_holder_if_applicable"] = (
        mapping.get("TIN_PP")
        if mapping.get("Tax_residence_of_PP") == "US"
        else "N/A"
    )        

    # Ajout des données globales (date, point de contact, adresse) via overall FATCA
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]
    poc = overall.get("PointOfContactReportingFI", {})
    # Note : dans FATCA, on utilise toujours les mêmes balises que dans CRS pour le reporting FI
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (poc.get("aeoi_lux:FirstName", "N/A") + " " + poc.get("aeoi_lux:Name", "N/A")).strip()
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")
    # Extraction de l'adresse depuis l'overall FATCA (utilise les mêmes clés que CRS)
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) if any(components) else "N/A"
    fix = overall.get("AddressFix", {})
    postal = fix.get("PostCode", "").strip()
    country = country_code_to_name(fix.get("Country", "").strip())
    mapping["code_Postal_and_country_of_RFI"] = f"{postal} {country}".strip() if postal or country else "N/A"

    # Reporting period
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1)

    if "Tax_residence_of_PP" not in mapping:
        mapping["Tax_residence_of_PP"] = mapping.get("Country_of_residence_of_PP", "N/A")
    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.
    return mapping

def build_mapping_fatca_active(account_report, overall):
    mapping = {}
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("fatca:NameReportingFI","N/A")
    org = account_report.find("fatca:AccountHolder/fatca:Organisation",namespaces=ns)
    if org is None:
        logger.warning("Warning: No FATCA Organisation element found for active entity; skipping this account.")
        return None

    mapping["Name_of_Active"]              = org.findtext("stffatcatypes:Name","N/A",namespaces=ns).strip()
    addr = org.find("stffatcatypes:Address/stffatcatypes:AddressFree",namespaces=ns)
    mapping["Adress_of_Active_NFE_"]       = addr.text.strip() if addr is not None and addr.text else "N/A"
    country = org.findtext("stffatcatypes:Address/stffatcatypes:CountryCode","",namespaces=ns).strip()
    mapping["Code_and_Country_of_Active_NFE"] = country_code_to_name(country) or "N/A"
    tax_country = org.findtext("stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
    mapping["Tax_residence_of_Active_"]     = country_code_to_name(tax_country) if tax_country else "N/A"
    mapping["TIN_active_NFE"]               = org.findtext("stffatcatypes:TIN","N/A",namespaces=ns).strip()
    
    # — US TIN if tax residence is US —
    mapping["US_TIN_of_account_holder_if_applicable"] = (
        mapping.get("TIN_active_NFE")
        if country == "US"
        else "N/A"
    )

    mapping["Account_Number_of_account_holder_"] = account_report.findtext("fatca:AccountNumber", default="N/A", namespaces=ns).strip()
    mapping["Closed_account_in_2023_YESNO"] = account_report.findtext("fatca:AccountClosed", default="false", namespaces=ns)
    pays = {"FATCA501": "0.00", "FATCA502": "0.00", "FATCA503": "0.00", "FATCA504": "0.00"}
    for pay in account_report.findall("fatca:Payment", ns):
        typ = pay.findtext("fatca:Type", default="", namespaces=ns)
        amt = pay.findtext("fatca:PaymentAmnt", default="0.00", namespaces=ns)
        try:
            pays[typ] = "{:,.2f}".format(float(amt.strip()))
        except Exception:
            pays[typ] = "0.00"
    mapping["Distributions_dividends_during_2023"] = pays.get("FATCA501", "0.00")
    mapping["Interest_paidaccrued_in_2023"] = pays.get("FATCA502", "0.00")
    mapping["Proceeds_during_2023"] = pays.get("FATCA503", "0.00")
    mapping["Other_paidaccrued_in_2023"] = pays.get("FATCA504", "0.00")
    bal = account_report.find("fatca:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "{:,.2f}".format(float(bal.text.strip()))
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"
    # Ajout des données globales
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (poc.get("aeoi_lux:FirstName", "N/A") + " " + poc.get("aeoi_lux:Name", "N/A")).strip()
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) if any(components) else "N/A"
    fix = overall.get("AddressFix", {})
    postal = fix.get("PostCode", "").strip()
    country = country_code_to_name(fix.get("Country", "").strip())
    mapping["code_Postal_and_country_of_RFI"] = f"{postal} {country}".strip() if postal or country else "N/A"
    
    # Reporting period
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1)

    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.
    return mapping

def build_mapping_fatca_controlling(account_report, overall):
    """
    Build mapping dict for a FATCA controlling person (FATCA801).
    """
    from datetime import datetime

    mapping = {}
    # — RFI info —
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("fatca:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) or "N/A"
    fix = overall.get("AddressFix", {})
    post = fix.get("PostCode", "").strip()
    country_code = fix.get("Country", "").strip()
    mapping["code_Postal_and_country_of_RFI"] = f"{post} {country_code_to_name(country_code)}".strip() or "N/A"

    # — Reporting period & Today —
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Reporting_year"] = rp
    mapping["Year_following_reporting_period"] = str(int(rp) + 1) if rp != "N/A" else "N/A"
    dt = datetime.today()
    mapping["Today"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"
    mapping["Today_Date"] = mapping["Today"]

    # — Point of Contact —
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (
        f"{poc.get('aeoi_lux:FirstName','').strip()} {poc.get('aeoi_lux:Name','').strip()}".strip()
    ) or "N/A"
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")

    # — Controlling Person —
    cp = account_report.find("fatca:ControllingPerson/fatca:Individual", namespaces=ns)
    if cp is not None:
        mapping["Surname_of_CP_"] = cp.findtext("stffatcatypes:Name/stffatcatypes:LastName", default="N/A", namespaces=ns).strip()
        mapping["Name_of_CP"]     = cp.findtext("stffatcatypes:Name/stffatcatypes:FirstName", default="N/A", namespaces=ns).strip()

        addr_el = cp.find("stffatcatypes:Address/stffatcatypes:AddressFree", namespaces=ns)
        mapping["Address_of_CP"] = addr_el.text.strip() if addr_el is not None and addr_el.text else "N/A"

        # Zip code we reuse the RFI postal
        mapping["Zip_code"] = post or "N/A"

        mapping["TIN_of_CP"] = cp.findtext("stffatcatypes:TIN", default="N/A", namespaces=ns).strip()

        birth = cp.find("stffatcatypes:BirthInfo", namespaces=ns)
        if birth is not None:
            mapping["Date_of_Birth_CP"]   = birth.findtext("stffatcatypes:BirthDate", default="N/A", namespaces=ns).rstrip("Z").strip()
            mapping["Place_of_birth_CP"]  = birth.findtext("stffatcatypes:City", default="N/A", namespaces=ns).strip()
        else:
            mapping["Date_of_Birth_CP"]  = "N/A"
            mapping["Place_of_birth_CP"] = "N/A"

        mapping["Account_Number_of_account_holder_CP"] = account_report.findtext(
            "fatca:AccountNumber", default="N/A", namespaces=ns
        ).strip()

        tax_code = cp.findtext("stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
        mapping["Tax_residence_of_CP"] = country_code_to_name(tax_code) if tax_code else "N/A"

        mapping["USTINCP"] = (
            mapping["TIN_of_CP"] if tax_code == "US" else "N/A"
        )
    else:
        for key in [
            "Surname_of_CP_", "Name_of_CP", "Address_of_CP", "Zip_code",
            "TIN_of_CP", "Date_of_Birth_CP", "Place_of_birth_CP",
            "Account_Number_of_account_holder_CP", "Tax_residence_of_CP",
            "USTINCP"
        ]:
            mapping[key] = "N/A"

    # — Organisation (passive HH) for contact details —
    org = account_report.find("fatca:AccountHolder/fatca:Organisation", namespaces=ns)
    if org is not None:
        mapping["Name_of_AH_"] = org.findtext("stffatcatypes:Name", default="N/A", namespaces=ns).strip()
        addr_el = org.find("stffatcatypes:Address/stffatcatypes:AddressFree", namespaces=ns)
        mapping["Adress_of_passive__NFE_"] = addr_el.text.strip() if addr_el is not None and addr_el.text else "N/A"
        code_el = org.findtext("stffatcatypes:Address/stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
        mapping["Tax_residence_of_AH"] = code_el or "N/A"
        mapping["TIN_passive_NFE"]     = org.findtext("stffatcatypes:TIN", default="N/A", namespaces=ns).strip()
    else:
        for key in ["Name_of_AH_", "Adress_of_passive__NFE_", "Tax_residence_of_AH", "TIN_passive_NFE"]:
            mapping[key] = "N/A"

    # — Account balance & currency —
    bal = account_report.find("fatca:AccountBalance", namespaces=ns)
    if bal is not None and bal.text:
        try:
            mapping["Account_balance_ie_sum_of_equity_and_"] = f"{float(bal.text):,.2f}"
        except ValueError:
            mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"

    # — Payments FATCA501–504 —
    pays = {p.findtext("fatca:Type", namespaces=ns): p.findtext("fatca:PaymentAmnt", namespaces=ns)
            for p in account_report.findall("fatca:Payment", namespaces=ns)}
    mapping["Distributions_dividends_during_2023"] = f"{float(pays.get('FATCA501','0.00')):,.2f}"
    mapping["Interest_paidaccrued_in_2023"]       = f"{float(pays.get('FATCA502','0.00')):,.2f}"
    mapping["Proceeds_during_2023"]              = f"{float(pays.get('FATCA503','0.00')):,.2f}"
    mapping["Other_paidaccrued_in_2023"]         = f"{float(pays.get('FATCA504','0.00')):,.2f}"

    # — Ensure no empty strings —
    for k, v in mapping.items():
        if v is None or str(v).strip() == "":
            mapping[k] = "N/A"

    # The mapping holds the account holder's name, address and TIN.
    # It is deliberately not logged at any level.

    return mapping


# -------------------------------------------------------------------
# Fonction de remplacement dans le DOCX (inchangée)
# -------------------------------------------------------------------
def replace_in_docx(template_docx_path, output_docx_path, mapping):
    import os, re, zipfile, shutil
    from docx import Document

    # Nettoyage du mapping
    for k in mapping:
        val = mapping[k]
        if val is None or str(val).strip() == "" or str(val).lower() == "nan":
            mapping[k] = "N/A"
        else:
            mapping[k] = str(val)

    temp_dir = "temp_docx"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.mkdir(temp_dir)

    # ────── Dézipper le .docx ──────
    with zipfile.ZipFile(template_docx_path, "r") as z:
        z.extractall(temp_dir)

    doc_xml_path = os.path.join(temp_dir, "word", "document.xml")

    # ────── 1er passage : remplacement global brut via regex ──────
    with open(doc_xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    pattern = re.compile(r"«\s*([^»]+?)\s*»", re.DOTALL)

    def repl(match):
        key = match.group(1).strip()
        return mapping.get(key, match.group(0))

    xml_content = pattern.sub(repl, xml_content)
    xml_content = pattern.sub(repl, xml_content)  # deuxième passage pour sécurité

    with open(doc_xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    # ────── Repacker le .docx temporaire pour traitement python-docx ──────
    docx_path = os.path.join(temp_dir, "temp_modified.docx")
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as z:
        for foldername, _, filenames in os.walk(temp_dir):
            for filename in filenames:
                if filename == "temp_modified.docx":
                    continue
                file_path = os.path.join(foldername, filename)
                arcname = os.path.relpath(file_path, temp_dir)
                z.write(file_path, arcname)

    # ────── 2e passage : reprise avec python-docx sur les fragments restants ──────
    doc = Document(docx_path)
    placeholders = {f'«{k}»': v for k, v in mapping.items()}

    def replace_in_runs(runs, placeholder, value):
        full = "".join(r.text for r in runs)
        if placeholder in full:
            new_text = full.replace(placeholder, value)
            for r in runs:
                r.text = ""
            runs[0].text = new_text

    # Paragraphes
    for para in doc.paragraphs:
        for ph, val in placeholders.items():
            if ph in para.text:
                replace_in_runs(para.runs, ph, val)

    # Cellules de tableau
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for ph, val in placeholders.items():
                        if ph in para.text:
                            replace_in_runs(para.runs, ph, val)

    # Enregistrement final
    doc.save(output_docx_path)
    shutil.rmtree(temp_dir)

# -------------------------------------------------------------------
# Fonctions de génération pour rapports CRS
# -------------------------------------------------------------------
def generate_notifications_individual(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info(root)
    account_reports = root.findall(".//crs:CrsBody/crs:ReportingGroup/crs:AccountReport", ns)
    folder_created = False
    if not account_reports:
        logger.debug("No CRS individual accounts found.")
        return

    for acct in account_reports:
        mapping = build_mapping_individual(acct, overall)
        if mapping is None:
            continue
        # Creation of the Individual folder
        if not folder_created:
            os.makedirs(output_dir, exist_ok=True)
            folder_created = True

        surname = mapping.get("Surname_of_PP_", "").strip()
        given_name = mapping.get("Name_of_PP", "").strip()
        if surname == "N/A" or given_name == "N/A":
            filename = f"Account_{mapping.get('Account_Number_of_account_holder_', 'Unknown')}"
        else:
            filename = f"{surname}_{given_name}"
        filename = filename.replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("CRS Individual DOCX saved")
        except Exception as e:
            logger.warning("Error saving CRS Individual DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("CRS Individual PDF generated")
        except Exception as e:
            logger.warning("Error converting CRS Individual DOCX to PDF: %s", type(e).__name__)

def generate_active_notifications(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info(root)
    all_reports = root.findall(".//crs:CrsBody/crs:ReportingGroup/crs:AccountReport", ns)
    active_reports = []
    for acct in all_reports:
        acct_holder = acct.find("crs:AccountHolder", ns)
        if acct_holder is not None:
            acct_type = acct_holder.findtext("crs:AcctHolderType", default="", namespaces=ns)
            logger.debug("CRS Account found, type: %r", acct_type)
            if acct_type.strip() == "CRS102":
                active_reports.append(acct)
    if not active_reports:
        logger.debug("No CRS active accounts with CRS102 found.")
        return
    # Create output folder only if we have at least one report
    os.makedirs(output_dir, exist_ok=True)
    for acct in active_reports:
        mapping = build_mapping_active(acct, overall)
        if mapping.get("Name_of_Active", "N/A") == "N/A":
            continue
        filename = f"{mapping['Name_of_Active']}_{mapping['Account_Number_of_account_holder_']}".replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("CRS Active DOCX saved")
        except Exception as e:
            logger.warning("Error saving CRS Active DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("CRS Active PDF generated")
        except Exception as e:
            logger.warning("Error converting CRS Active DOCX to PDF: %s", type(e).__name__)

def generate_notifications_controlling(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info(root)
    controlling_reports = []
    all_reports = root.findall(".//crs:CrsBody/crs:ReportingGroup/crs:AccountReport", ns)
    for acct in all_reports:
        cp = acct.find("crs:ControllingPerson", ns)
        if cp is not None:
            controlling_reports.append(acct)
    if not controlling_reports:
        logger.debug("No CRS controlling persons found.")
        return
    # Create output folder only if we have at least one report
    os.makedirs(output_dir, exist_ok=True)
    for acct in controlling_reports:
        mapping = build_mapping_controlling(acct, overall)
        control_surname = mapping.get("Surname_of_CP_", "").strip()
        control_firstname = mapping.get("Name_of_CP", "").strip()
        if control_surname == "N/A" or control_surname == "":
            filename_part = control_firstname if control_firstname and control_firstname != "N/A" else "Unknown"
        else:
            filename_part = control_surname
        filename = f"{filename_part}_{mapping.get('Account_Number_of_account_holder_CP', 'Unknown')}".replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("CRS Controlling DOCX saved")
        except Exception as e:
            logger.warning("Error saving CRS Controlling DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("CRS Controlling PDF generated")
        except Exception as e:
            logger.warning("Error converting CRS Controlling DOCX to PDF: %s", type(e).__name__)

# -------------------------------------------------------------------
# Fonctions de génération pour rapports FATCA
# -------------------------------------------------------------------
def generate_fatca_notifications_individual(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info_fatca(root)
    account_reports = root.findall(".//fatca:AccountReport", ns)
    folder_created = False
    if not account_reports:
        logger.debug("No FATCA individual accounts found.")
        return

    for acct in account_reports:
        mapping = build_mapping_fatca_individual(acct, overall)
        if mapping is None:
            continue

        # Creation of the Individual folder
        if not folder_created:
            os.makedirs(output_dir, exist_ok=True)
            folder_created = True

        surname = mapping.get("Surname_of_PP_", "").strip()
        given_name = mapping.get("Name_of_PP", "").strip()
        if surname == "N/A" or given_name == "N/A":
            filename = f"Account_{mapping.get('Account_Number_of_account_holder_', 'Unknown')}"
        else:
            filename = f"{surname}_{given_name}"
        filename = filename.replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("FATCA Individual DOCX saved")
        except Exception as e:
            logger.warning("Error saving FATCA Individual DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("FATCA Individual PDF generated")
        except Exception as e:
            logger.warning("Error converting FATCA Individual DOCX to PDF: %s", type(e).__name__)

def generate_fatca_notifications_active(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info_fatca(root)
    account_reports = root.findall(".//fatca:AccountReport", ns)
    active_reports = []
    for acct in account_reports:
        holder = acct.find("fatca:AccountHolder", ns)
        if holder is not None:
            acct_type = holder.findtext("fatca:AcctHolderType", default="", namespaces=ns)
            logger.debug("FATCA Account found, type: %r", acct_type)
            if acct_type.strip() == "FATCA104":
                active_reports.append(acct)
    if not active_reports:
        logger.debug("No FATCA active accounts found.")
        return
    # Create output folder only if we have at least one report
    os.makedirs(output_dir, exist_ok=True)
    for acct in active_reports:
        mapping = build_mapping_fatca_active(acct, overall)
        if mapping is None or mapping.get("Name_of_Active", "N/A") == "N/A":
            continue
        filename = f"{mapping['Name_of_Active']}_{mapping['Account_Number_of_account_holder_']}".replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("FATCA Active DOCX saved")
        except Exception as e:
            logger.warning("Error saving FATCA Active DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("FATCA Active PDF generated")
        except Exception as e:
            logger.warning("Error converting FATCA Active DOCX to PDF: %s", type(e).__name__)

def generate_fatca_notifications_controlling(xml_content, template_docx_path, output_dir):
    root = ET.fromstring(xml_content)
    overall = build_overall_info_fatca(root)
    account_reports = root.findall(".//fatca:AccountReport", ns)
    controlling_reports = []
    for acct in account_reports:
        cp = acct.find("fatca:ControllingPerson", ns)
        if cp is not None:
            controlling_reports.append(acct)
    if not controlling_reports:
        logger.debug("No FATCA controlling persons found.")
        return
    # Create output folder only if we have at least one report
    os.makedirs(output_dir, exist_ok=True)
    for acct in controlling_reports:
        mapping = build_mapping_fatca_controlling(acct, overall)
        if mapping is None:
            continue
        control_surname = mapping.get("Surname_of_CP_", "").strip()
        control_firstname = mapping.get("Name_of_CP", "").strip()
        if control_surname == "N/A" or control_surname == "":
            filename_part = control_firstname if control_firstname and control_firstname != "N/A" else "Unknown"
        else:
            filename_part = control_surname
        filename = f"{filename_part}_{mapping.get('Account_Number_of_account_holder_CP', 'Unknown')}".replace(" ", "_")
        docx_out = os.path.join(output_dir, filename + ".docx")
        try:
            replace_in_docx(template_docx_path, docx_out, mapping)
            logger.debug("FATCA Controlling DOCX saved")
        except Exception as e:
            logger.warning("Error saving FATCA Controlling DOCX: %s", type(e).__name__)
            continue
        try:
            pdf_out = os.path.join(output_dir, filename + ".pdf")
            convert(docx_out, pdf_out)
            logger.debug("FATCA Controlling PDF generated")
        except Exception as e:
            logger.warning("Error converting FATCA Controlling DOCX to PDF: %s", type(e).__name__)

# -------------------------------------------------------------------
# Build mapping for CRS passive entities (CRS103),
# but only collecting controlling persons from AccountReport
# entries with the same AccountNumber AND the same Organisation Name
# -------------------------------------------------------------------
def build_mapping_passive(account_report, overall, all_reports):
    """
    Build dict for a passive‑entity (CRS103),
    including payments, entity info & all matching CPs.
    """
    mapping = {}

    # — RFI info (static per file) —
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("aeoi_lux:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI",{})
    mapping["Address_of_RFI"] = " ".join(filter(None,[
        adr.get("aeoi_lux:NumberPhysical","").strip(),
        adr.get("aeoi_lux:StreetPhysical","").strip(),
        adr.get("aeoi_lux:CityPhysical","").strip()
    ])) or "N/A"
    fix = overall.get("AddressFix",{})
    mapping["code_Postal_and_country_of_RFI"] = (
        f"{fix.get('PostCode','').strip()} {country_code_to_name(fix.get('Country','').strip())}".strip()
        or "N/A"
    )

    # — POC normalization —
    poc = overall.get("PointOfContactReportingFI",{})
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (
        f"{poc.get('aeoi_lux:FirstName','').strip()} {poc.get('aeoi_lux:Name','').strip()}".strip()
        or "N/A"
    )
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal","N/A")

    # — Reporting period & today —
    rp = overall.get("ReportingPeriod","N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp!="N/A" else "N/A"
    mapping["Year_following_reporting_period"] = str(int(rp)+1) if rp!="N/A" else "N/A"
    dt = datetime.today()
    mapping["Today_Date"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"

    # — Passive entity fields —
    org = account_report.find("crs:AccountHolder/crs:Organisation", ns)
    if org is not None:
        name = org.findtext("crs:Name", default="N/A", namespaces=ns).strip()
        addr = org.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
        tax_residence_code = org.findtext("crs:ResCountryCode", default="", namespaces=ns).strip()
        address_country_code = org.findtext("crs:Address/commontypesfatcacrs:CountryCode", default="", namespaces=ns).strip()
        tin = org.findtext("crs:IN", default="N/A", namespaces=ns).strip()

        mapping["Name_of_Passive"]          = name or "N/A"
        mapping["Adress_of_Passive_NFE_"]   = (addr.text.strip() if addr is not None and addr.text else "N/A")
        mapping["Code_and_Country_of_Passive_NFE"] = country_code_to_name(address_country_code) or "N/A"
        mapping["Tax_residence_of_Passive_"] = country_code_to_name(tax_residence_code) if tax_residence_code else "N/A"
        mapping["TIN_Passive_NFE"]          = tin or "N/A"
        # — US TIN if tax residence is US —
        mapping["US_TIN_of_account_holder_if_applicable"] = (
            tin
            if tax_residence_code == "US"
            else "N/A"
        )
        # same values for controlling‑section placeholders:
        mapping["Name_of_AH_"]              = name or "N/A"
        mapping["Adress_of_passive__NFE_"]  = mapping["Adress_of_Passive_NFE_"]
        mapping["Tax_residence_of_AH"]      = mapping["Tax_residence_of_Passive_"]
        mapping["TIN_passive_NFE"]          = tin or "N/A"

    else:
        for key in [
            "Name_of_Passive","Adress_of_Passive_NFE_","Code_and_Country_of_Passive_NFE",
            "Tax_residence_of_Passive_","TIN_Passive_NFE",
            "Name_of_AH_","Adress_of_passive__NFE_","Tax_residence_of_AH","TIN_passive_NFE"
        ]:
            mapping[key] = "N/A"

    # — Account number, balance & currency —
    acct_num = account_report.findtext("crs:AccountNumber", default="N/A", namespaces=ns).strip()
    mapping["Account_Number_of_account_holder_"] = acct_num or "N/A"
    acct_elem = account_report.find("crs:AccountNumber", ns)
    mapping["Closed_account_in_2023_YESNO"] = acct_elem.get("ClosedAccount", "N/A") if acct_elem is not None else "N/A"

    # — Solde et devise —
    bal = account_report.find("crs:AccountBalance", ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = f"{float(bal.text):,.2f}"
        mapping["Currency"] = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"] = "N/A"

    # — Payments CRS501–CRS504 —
    pays = { p.findtext("crs:Type", namespaces=ns): p.findtext("crs:PaymentAmnt", namespaces=ns)
             for p in account_report.findall("crs:Payment", ns) }
    mapping["Distributions_dividends_during_2023"] = f"{float(pays.get('CRS501','0.00')):,.2f}"
    mapping["Interest_paidaccrued_in_2023"]       = f"{float(pays.get('CRS502','0.00')):,.2f}"
    mapping["Other_paidaccrued_in_2023"]           = f"{float(pays.get('CRS504','0.00')):,.2f}"
    mapping["Proceeds_during_2023"]               = f"{float(pays.get('CRS503','0.00')):,.2f}"

    # — Collect all matching controlling persons & their slots —
    cps = []
    for oth in all_reports:
        if oth.findtext("crs:AccountNumber", namespaces=ns) == acct_num:
            oth_org = oth.find("crs:AccountHolder/crs:Organisation", ns)
            if oth_org is not None and oth_org.findtext("crs:Name", default="", namespaces=ns).strip() == mapping["Name_of_Passive"]:
                ind = oth.find("crs:ControllingPerson/crs:Individual", ns)
                if ind is not None:
                    cps.append(ind)

    # — Fill CP slots dynamically —
    for i, ind in enumerate(cps, start=1):
        # names
        mapping[f"Surname_of_CP{i}_"] = ind.findtext("crs:Name/crs:LastName", default="N/A", namespaces=ns).strip() or "N/A"
        mapping[f"Name_of_CP{i}"]     = ind.findtext("crs:Name/crs:FirstName", default="N/A", namespaces=ns).strip() or "N/A"
        # addr & zip
        addr_cp = ind.find("crs:Address/commontypesfatcacrs:AddressFree", ns)
        mapping[f"Address_of_CP{i}"]  = (addr_cp.text.strip() if addr_cp is not None and addr_cp.text else "N/A")
        mapping[f"Zip_code{i}"]       = mapping["code_Postal_and_country_of_RFI"].split()[0] or "N/A"
        # TIN, birth
        mapping[f"TIN_of_CP{i}"]      = ind.findtext("crs:TIN", default="N/A", namespaces=ns).strip() or "N/A"
        b = ind.find("crs:BirthInfo", ns)
        if b is not None:
            mapping[f"Date_of_Birth_CP{i}"]  = b.findtext("crs:BirthDate", default="N/A", namespaces=ns).rstrip("Z") or "N/A"
            mapping[f"Place_of_birth_CP{i}"] = b.findtext("crs:City", default="N/A", namespaces=ns).strip() or "N/A"
        else:
            mapping[f"Date_of_Birth_CP{i}"]  = "N/A"
            mapping[f"Place_of_birth_CP{i}"] = "N/A"
        # tax residence
        code = ind.findtext("crs:ResCountryCode","",namespaces=ns).strip()
        mapping[f"Tax_residence_of_CP{i}"] = country_code_to_name(code) if code else "N/A"
        mapping[f"US_TIN_of_account_holderCP{i}_if_applicable"] = (mapping[f"TIN_of_CP{i}"] if code == "US" else "N/A")
        
        # account #
        mapping[f"Account_Number_of_account_holder_CP{i}"] = acct_num

    # — Pad to exactly 2 slots (your template expects 1 & 2) —
    for j in range(len(cps)+1, 3):
        for key in [
            f"Surname_of_CP{j}_", f"Name_of_CP{j}", f"Address_of_CP{j}",
            f"Zip_code{j}", f"TIN_of_CP{j}", f"Date_of_Birth_CP{j}",
            f"Place_of_birth_CP{j}", f"Tax_residence_of_CP{j}",
            f"Account_Number_of_account_holder_CP{j}"
        ]:
            mapping[key] = "N/A"

    return mapping


def generate_notifications_passive(xml_content, template_docx_path, output_dir):
    """
    For each CRS103 (passive) account, generate a DOCX + PDF.
    This function no longer filters out reports without immediate <ControllingPerson>.
    It collects all controlling persons via build_mapping_passive logic.
    """
    root = ET.fromstring(xml_content)
    overall = build_overall_info(root)

    all_reports = root.findall(".//crs:CrsBody/crs:ReportingGroup/crs:AccountReport", ns)
    # select only passive entity reports
    passive_reports = [r for r in all_reports
                       if r.findtext("crs:AccountHolder/crs:AcctHolderType", 
                                     namespaces=ns) == "CRS103"]

    if not passive_reports:
        logger.debug("No CRS passive accounts found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    logger.debug("Generating CRS passive reports into: {output_dir}")
    
    def replace_in_docx_passive(template_path, out_path, mapping):
        from docx import Document
        import re

        placeholders = {f'«{k}»': v for k,v in mapping.items()}
        doc = Document(template_path)

        # 1) replace placeholders
        def replace_in_runs(runs, ph, val):
            full = "".join(r.text for r in runs)
            if ph in full:
                new = full.replace(ph, val)
                for r in runs: r.text = ""
                runs[0].text = new

        for p in doc.paragraphs:
            for ph,val in placeholders.items():
                if ph in p.text:
                    replace_in_runs(p.runs, ph, val)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for ph,val in placeholders.items():
                        if ph in cell.text:
                            replace_in_runs(cell.paragraphs[0].runs, ph, val)

        # 2) remove unused CP blocks
        cp_indices = [
            int(m.group(1))
            for k,v in mapping.items()
            if (m := re.match(r'Surname_of_CP(\d+)_', k)) and v != "N/A"
        ]
        max_cp = max(cp_indices) if cp_indices else 0
        for n in range(max_cp+1, 11):
            remove_block(doc, f'CP_BLOCK_START_{n}', f'CP_BLOCK_END_{n}')

        # 3) scrub any leftover markers
        for p in list(doc.paragraphs):
            if "CP_BLOCK_START_" in p.text or "CP_BLOCK_END_" in p.text:
                p._element.getparent().remove(p._element)

        doc.save(out_path)

    for acct in passive_reports:
        # --- build mapping ---
        mapping = build_mapping_passive(acct, overall, all_reports)

        # ─── DEBUG: dump complet du mapping ───
        logger.debug("––––––––––––––––––––––––––––––––––––")
        logger.debug("Passive entity:  / Account #")
        for k, v in mapping.items():
            logger.debug("  {k:35}: {v}")
        logger.debug("––––––––––––––––––––––––––––––––––––")

        # --- determine filename ---
        name = mapping.get("Name_of_Passive", "").replace(" ", "_") or mapping.get("Account_Number_of_account_holder_", "Unknown")
        out_docx = os.path.join(output_dir, f"{name}.docx")

        # replace placeholders in Word template
        try:
            replace_in_docx_passive(template_docx_path, out_docx, mapping)
            logger.debug("  → Saved DOCX: {out_docx}")
        except Exception as e:
            logger.warning("Error saving DOCX for {name}: %s", type(e).__name__)
            continue

        # convert to PDF
        try:
            pdf_out = out_docx.replace(".docx", ".pdf")
            convert(out_docx, pdf_out)
            logger.debug("  → Saved PDF")
        except Exception as e:
            logger.warning("Error converting to PDF for {name}: %s", type(e).__name__)

# -------------------------------------------------------------------
# Build mapping for FATCA passive entities (FATCA102) including controlling persons
# -------------------------------------------------------------------
def build_mapping_fatca_passive(account_report, overall, all_reports):
    """
    Build mapping dict for a FATCA passive entity (FATCA102),
    including all controlling persons.
    """
    from datetime import datetime

    mapping = {}
    # — RFI info —
    mapping["Name_of_Reporting_Financial_Institution_"] = overall.get("fatca:NameReportingFI", "N/A")
    adr = overall.get("AddressReportingFI", {})
    components = [
        adr.get("aeoi_lux:NumberPhysical", "").strip(),
        adr.get("aeoi_lux:StreetPhysical", "").strip(),
        adr.get("aeoi_lux:CityPhysical", "").strip()
    ]
    mapping["Address_of_RFI"] = " ".join(filter(None, components)) or "N/A"
    fix = overall.get("AddressFix", {})
    post = fix.get("PostCode", "").strip()
    country_code = fix.get("Country", "").strip()
    mapping["code_Postal_and_country_of_RFI"] = f"{post} {country_code_to_name(country_code)}".strip() or "N/A"

    # — Point of Contact —
    poc = overall.get("PointOfContactReportingFI", {})
    mapping["Phone_number_of_POC_of_RFI"] = (lambda ph: ph if ph.startswith('+') or ph.startswith('00') or ph == "N/A" else '+' + ph)(poc.get("aeoi_lux:TelephoneDirect", "N/A").strip())
    mapping["Name_of_point_of_contact_POC_of_RFI"] = (
        f"{poc.get('aeoi_lux:FirstName','').strip()} {poc.get('aeoi_lux:Name','').strip()}".strip()
    ) or "N/A"
    mapping["Email_of_POC_of_RFI"] = poc.get("aeoi_lux:EmailPersonal", "N/A")

    # — Reporting period & Today —
    rp = overall.get("ReportingPeriod", "N/A").rstrip("Z").split("-")[0]
    mapping["Reporting_period"] = format_reporting_period(rp) if rp != "N/A" else "N/A"
    mapping["Year_following_reporting_period"] = str(int(rp) + 1) if rp != "N/A" else "N/A"
    dt = datetime.today()
    mapping["Today_Date"] = f"{dt.day} {dt.strftime('%B')} {dt.year}"

    # — Passive entity info —
    org = account_report.find("fatca:AccountHolder/fatca:Organisation", namespaces=ns)
    if org is not None:
        name = org.findtext("stffatcatypes:Name", default="N/A", namespaces=ns).strip()
        addr_el = org.find("stffatcatypes:Address/stffatcatypes:AddressFree", namespaces=ns)
        code_el = org.findtext("stffatcatypes:Address/stffatcatypes:CountryCode", default="", namespaces=ns).strip()
        # ResCountryCode : fiscal residence
        rc_el = org.findtext("stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
        tin    = org.findtext("stffatcatypes:TIN", default="N/A", namespaces=ns).strip()

        mapping["Name_of_Passive"]                 = name or "N/A"
        mapping["Adress_of_Passive_NFE_"]         = addr_el.text.strip() if addr_el is not None and addr_el.text else "N/A"
        mapping["Code_and_Country_of_Passive_NFE"] = country_code_to_name(code_el) or "N/A"
        mapping["Tax_residence_of_Passive_"]       = country_code_to_name(rc_el) if rc_el else "N/A"
        mapping["TIN_Passive_NFE"]                 = tin or "N/A"
        mapping["US_TIN_of_account_holder_if_applicable"] = (tin if rc_el == "US" else "N/A")

        # mirror for AH placeholders
        mapping["Name_of_AH_"]             = mapping["Name_of_Passive"]
        mapping["Adress_of_passive__NFE_"] = mapping["Adress_of_Passive_NFE_"]
        mapping["Tax_residence_of_AH"]     = mapping["Tax_residence_of_Passive_"]
        mapping["TIN_passive_NFE"]         = mapping["TIN_Passive_NFE"]
    else:
        for key in [
            "Name_of_Passive","Adress_of_Passive_NFE_","Code_and_Country_of_Passive_NFE",
            "Tax_residence_of_Passive_","TIN_Passive_NFE",
            "Name_of_AH_","Adress_of_passive__NFE_","Tax_residence_of_AH","TIN_passive_NFE"
        ]:
            mapping[key] = "N/A"

    # — Account number & Closed flag —
    acct_elem = account_report.find("fatca:AccountNumber", namespaces=ns)
    acct_num = acct_elem.text.strip() if acct_elem is not None and acct_elem.text else "N/A"
    mapping["Account_Number_of_account_holder_"] = acct_num
    mapping[f"Closed_account_in_2023_YESNO"]      = account_report.findtext("fatca:AccountClosed", default="false", namespaces=ns)

    # — Balance & currency —
    bal = account_report.find("fatca:AccountBalance", namespaces=ns)
    if bal is not None and bal.text:
        mapping["Account_balance_ie_sum_of_equity_and_"] = f"{float(bal.text):,.2f}"
        mapping["Currency"]                             = bal.get("currCode", "N/A")
    else:
        mapping["Account_balance_ie_sum_of_equity_and_"] = "N/A"
        mapping["Currency"]                             = "N/A"

    # — Payments FATCA501–504 —
    pays = {
        p.findtext("fatca:Type", namespaces=ns): p.findtext("fatca:PaymentAmnt", namespaces=ns)
        for p in account_report.findall("fatca:Payment", namespaces=ns)
    }
    mapping["Distributions_dividends_during_2023"] = f"{float(pays.get('FATCA501','0.00')):,.2f}"
    mapping["Interest_paidaccrued_in_2023"]       = f"{float(pays.get('FATCA502','0.00')):,.2f}"
    mapping["Proceeds_during_2023"]              = f"{float(pays.get('FATCA503','0.00')):,.2f}"
    mapping["Other_paidaccrued_in_2023"]         = f"{float(pays.get('FATCA504','0.00')):,.2f}"

    # — All Controlling Persons —
    cps = [
        r.find("fatca:ControllingPerson", namespaces=ns)
        for r in all_reports
        if r.findtext("fatca:AccountNumber", namespaces=ns) == acct_num
           and r.find("fatca:ControllingPerson", namespaces=ns) is not None
    ]
    for i, cp in enumerate(cps, start=1):
        ind = cp.find("fatca:Individual", namespaces=ns)
        mapping[f"Surname_of_CP{i}_"]    = ind.findtext("stffatcatypes:Name/stffatcatypes:LastName",   default="N/A", namespaces=ns).strip()
        mapping[f"Name_of_CP{i}"]        = ind.findtext("stffatcatypes:Name/stffatcatypes:FirstName",  default="N/A", namespaces=ns).strip()
        addr_el = ind.find("stffatcatypes:Address/stffatcatypes:AddressFree", namespaces=ns)
        mapping[f"Address_of_CP{i}"]     = addr_el.text.strip() if addr_el is not None and addr_el.text else "N/A"
        mapping[f"Zip_code{i}"]          = post or "N/A"
        mapping[f"TIN_of_CP{i}"]         = ind.findtext("stffatcatypes:TIN", default="N/A", namespaces=ns).strip()
        birth = ind.find("stffatcatypes:BirthInfo", namespaces=ns)
        if birth is not None:
            mapping[f"Date_of_Birth_CP{i}"]  = birth.findtext("stffatcatypes:BirthDate", default="N/A", namespaces=ns).rstrip("Z")
            mapping[f"Place_of_birth_CP{i}"] = birth.findtext("stffatcatypes:City",      default="N/A", namespaces=ns).strip()
        else:
            mapping[f"Date_of_Birth_CP{i}"]  = "N/A"
            mapping[f"Place_of_birth_CP{i}"] = "N/A"
        res = ind.findtext("stffatcatypes:ResCountryCode", default="", namespaces=ns).strip()
        mapping[f"Tax_residence_of_CP{i}"] = country_code_to_name(res) if res else "N/A"
        mapping[f"US_TIN_of_account_holderCP{i}_if_applicable"] = (mapping[f"TIN_of_CP{i}"] if res == "US" else "N/A")
        mapping[f"Account_Number_of_account_holder_CP{i}"] = acct_num

    # — Pad to exactly 2 CP slots —
    for j in range(len(cps) + 1, 3):
        for key in [
            f"Surname_of_CP{j}_", f"Name_of_CP{j}", f"Address_of_CP{j}",
            f"Zip_code{j}", f"TIN_of_CP{j}", f"Date_of_Birth_CP{j}",
            f"Place_of_birth_CP{j}", f"Tax_residence_of_CP{j}",
            f"US_TIN_of_account_holderCP{j}_if_applicable",
            f"Account_Number_of_account_holder_CP{j}"
        ]:
            mapping[key] = "N/A"

    return mapping


# -------------------------------------------------------------------
# Generate DOCX/PDF for FATCA passive entities
# -------------------------------------------------------------------
def generate_fatca_notifications_passive(xml_content, template_docx_path, output_dir):
    """
    For each FATCA102 (passive) account, generate a DOCX + PDF by
    replacing «Placeholders» directly in the .docx without using replace_in_docx().
    """
    import os
    from docx import Document
    try:
        from docx2pdf import convert
    except Exception:
        def convert(*a, **k):
            raise RuntimeError('docx2pdf/MS Word not available on this server')

    root = ET.fromstring(xml_content)
    overall = build_overall_info_fatca(root)

    # collect only passive‑entity (FATCA102) reports
    reports = [
        acct for acct in root.findall(".//fatca:AccountReport", ns)
        if acct.findtext("fatca:AccountHolder/fatca:AcctHolderType", namespaces=ns) == "FATCA102"
    ]
    if not reports:
        logger.debug("No FATCA passive accounts found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    logger.debug("Generating FATCA passive reports into: {output_dir}")

    def replace_in_docx_passive(template_path, out_path, mapping):
        from docx import Document
        import re

        placeholders = {f'«{k}»': v for k,v in mapping.items()}
        doc = Document(template_path)

        # 1) replace placeholders
        def replace_in_runs(runs, ph, val):
            full = "".join(r.text for r in runs)
            if ph in full:
                new = full.replace(ph, val)
                for r in runs: r.text = ""
                runs[0].text = new

        for p in doc.paragraphs:
            for ph,val in placeholders.items():
                if ph in p.text:
                    replace_in_runs(p.runs, ph, val)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for ph,val in placeholders.items():
                        if ph in cell.text:
                            replace_in_runs(cell.paragraphs[0].runs, ph, val)

        # 2) remove unused CP blocks
        cp_indices = [
            int(m.group(1))
            for k,v in mapping.items()
            if (m := re.match(r'Surname_of_CP(\d+)_', k)) and v != "N/A"
        ]
        max_cp = max(cp_indices) if cp_indices else 0
        for n in range(max_cp+1, 11):
            remove_block(doc, f'CP_BLOCK_START_{n}', f'CP_BLOCK_END_{n}')

        # 3) scrub any leftover markers
        for p in list(doc.paragraphs):
            if "CP_BLOCK_START_" in p.text or "CP_BLOCK_END_" in p.text:
                p._element.getparent().remove(p._element)

        doc.save(out_path)



    for acct in reports:
        # build the mapping for this account
        mapping = build_mapping_fatca_passive(acct, overall, root.findall(".//fatca:AccountReport", namespaces=ns))

        # récupérer la liste des CPs pour déterminer combien de blocs conserver
        cps = [
            cp for cp in acct.findall("fatca:ControllingPerson", ns)
            if cp.find("fatca:Individual", ns) is not None
        ]

        # DEBUG: dump mapping
        logger.debug("––––––––––––––––––––––––––––––––––––")
        logger.debug("FATCA passive entity:  / "
              f"Account #")
        for k, v in mapping.items():
            logger.debug("  {k:35}: {v}")
        logger.debug("––––––––––––––––––––––––––––––––––––")

        # determine filename
        safe_name = mapping.get("Name_of_Passive", "").replace(" ", "_")
        if not safe_name:
            safe_name = mapping.get("Account_Number_of_account_holder_", "Unknown")
        out_docx = os.path.join(output_dir, f"{safe_name}.docx")

        # replace placeholders
        try:
            replace_in_docx_passive(template_docx_path, out_docx, mapping)
            logger.debug("  → Saved DOCX: {out_docx}")
        except Exception as e:
            logger.warning("Error saving DOCX for {safe_name}: %s", type(e).__name__)
            continue

        # convert to PDF
        try:
            pdf_out = out_docx.replace(".docx", ".pdf")
            convert(out_docx, pdf_out)
            logger.debug("  → Saved PDF")
        except Exception as e:
            logger.warning("Error converting to PDF for {safe_name}: %s", type(e).__name__)

# -------------------------------------------------------------------
# Helper function to remove a block of paragraphs between two markers for passive data notifications
# -------------------------------------------------------------------

def remove_block(doc: Document, start_marker: str, end_marker: str):
    """
    Supprime tous les paragraphes (et leurs contenus) 
    entre le paragraphe contenant start_marker et celui contenant end_marker inclus.
    """
    paras = list(doc.paragraphs)
    # trouver indices
    try:
        i_start = next(i for i, p in enumerate(paras) if start_marker in p.text)
        i_end   = next(i for i, p in enumerate(paras) if end_marker   in p.text)
    except StopIteration:
        return  # marqueurs non trouvés : rien à faire

    # supprimer du plus haut index au plus petit pour ne pas invalider la liste
    for idx in range(i_end, i_start - 1, -1):
        p = paras[idx]._element
        p.getparent().remove(p)

# -------------------------------------------------------------------
# Dispatcher function to detect the report type and generate data notifications
# -------------------------------------------------------------------
def generate_notifications(xml_content, template_individual_path, template_active_path, template_controlling_path, template_passive_path, output_base, do_individuals=True, do_active=True, do_controlling=True, do_passive=True):
    root = ET.fromstring(xml_content)
    if root.find('.//crs:AccountReport', ns) is not None:
        logger.debug("Detected CRS report.")

        individuals_output = os.path.join(output_base, "Individuals")
        active_output = os.path.join(output_base, "Active")
        controlling_output = os.path.join(output_base, "Controlling")
        passive_output = os.path.join(output_base, "Passive")

        # Generate the reports
        if do_individuals:
            generate_notifications_individual(xml_content, template_individual_path, individuals_output)
        if do_active:
            generate_active_notifications(xml_content, template_active_path, active_output)
        if do_controlling:
            generate_notifications_controlling(xml_content, template_controlling_path, controlling_output)
        if do_passive:
            generate_notifications_passive(xml_content, template_passive_path, passive_output)
    else:
        logger.debug("Detected FATCA report.")
        # Ici, on crée des sous-dossiers pour Individuals, Active et Controlling même pour FATCA
        fatca_individual = os.path.join(output_base, "Individuals")
        fatca_active = os.path.join(output_base, "Active")
        fatca_controlling = os.path.join(output_base, "Controlling")
        fatca_passive = os.path.join(output_base, "Passive")

        # Generate the reports
        if do_individuals:
            generate_fatca_notifications_individual(xml_content, template_individual_path, fatca_individual)
        if do_active:
            generate_fatca_notifications_active(xml_content, template_active_path, fatca_active)
        if do_controlling:
            generate_fatca_notifications_controlling(xml_content, template_controlling_path, fatca_controlling)
        if do_passive:
            generate_fatca_notifications_passive(xml_content, template_passive_path, fatca_passive)