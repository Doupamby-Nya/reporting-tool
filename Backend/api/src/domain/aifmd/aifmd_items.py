"""ESMA item numbers and wording, for the AIFMD capture form.

Taken from the regulator's own reporting workbook, where every item
carries its number and its official name. Matching to the engine's keys
is exact on a normalised form of the two names — never fuzzy, because a
field labelled with the wrong item number would be checked against the
wrong rule, which is worse than one labelled from its key.

A key absent here keeps a label derived from its name. That is visible,
and safe.
"""

from __future__ import annotations

#: engine key -> (ESMA item number, ESMA wording)
AIFMD_ITEMS: dict[str, tuple[int, str]] = {
    "aifm_version": (2, "Version"),
    "aif_version": (2, "Version"),
    "aifm_filing_type": (4, "Filing type"),
    "aif_filing_type": (4, "Filing type"),
    "aif_content_type": (5, "AIF content type"),
    "reporting_period_type": (8, "Reporting period type"),
    "reporting_period_year": (9, "Reporting period year"),
    "aifm_last_reporting_flag": (13, "Last reporting flag"),
    "aif_last_reporting_flag": (13, "Last reporting flag"),
    "aifm_national_code": (16, "AIFM National Code"),
    "aif_name": (18, "AIF Name"),
    "aif_eea_flag": (19, "AIF EEA flag"),
    "aif_reporting_code": (20, "AIF reporting code"),
    "aif_inception_date": (22, "Inception Date"),
    "aif_no_reporting_flag": (23, "AIF no reporting flag"),
    "aif_ecb_code": (30, "AIF ECB  code"),
    "aif_share_class_flag": (33, "AIF share class flag"),
    "aif_master_feeder_status": (41, "Master feeder status"),
    "predominant_aif_type": (57, "Predominant AIF Type"),
    "other_arrangement_type": (200, "Other Arrangement Type"),
    "investor_preferential_treatment_flag": (203, "Investor preferential treatment Flag"),
    "rehypothecation_flag": (281, "Rehypothecation flag"),
    "unsecured_borrowing_amount": (283, "Unsecured borrowing amount"),
    "short_position_borrowed_securities_value": (289, "Short position borrowed securities value"),
}
