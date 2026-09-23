"""AIFMD Annex IV reporting — the two files an AIFM submits to the CSSF.

A filing is one AIFM-level file (DATMAN) plus one AIF-level file (DATAIF).
This service turns a request into the engine's submission object, runs the
CSSF controls of the Technical Guidance, builds both documents, validates
them against the official ESMA schemas and checks each carries exactly one
reporting record (control FOR-010). Nothing is returned unless all of that
passes.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from domain.aifmd import aifmd_engine as ae
from domain.aifmd import aifmd_xsd
from models.commonModel import (
    GeneratedFile, GenerationResult, SchemaResult, ValidationResult, issues_to_payload,
)

FILES = (
    ("datman", "DATMAN — AIFM-level file", ae.build_datman_xml, ae.build_datman_filename),
    ("dataif", "DATAIF — AIF-level file", ae.build_dataif_xml, ae.build_dataif_filename),
)


def aifmd_metadata_service() -> dict[str, Any]:
    """The code lists and structural rules a client needs to render the form."""
    from domain.aifmd.aifmd_xml import (
        N_AIFM_INSTRUMENTS, N_AIFM_MARKETS, N_AIF_MARKETS, N_BORROWING_SOURCES,
        N_COUNTERPARTY_EXPOSURES, N_MAIN_INSTRUMENTS, N_PORTFOLIO_CONCENTRATIONS,
        N_PRINCIPAL_EXPOSURES,
    )

    return {
        "filing_types": ae.FILING_TYPES,
        "aifm_content_types": ae.AIFM_CONTENT_TYPES,
        "aif_content_types": ae.AIF_CONTENT_TYPES,
        "aifm_reporting_codes": ae.AIFM_REPORTING_CODES,
        "aif_reporting_codes": ae.AIF_REPORTING_CODES,
        "reporting_period_types": ae.REPORTING_PERIOD_TYPES,
        "aif_legal_forms": ae.AIF_LEGAL_FORM_CODES,
        "sender_entity_types": ae.SENDER_ENTITY_TYPES,
        "master_feeder_status": ae.MASTER_FEEDER_STATUS,
        "predominant_aif_types": ae.PREDOMINANT_AIF_TYPES,
        "strategy_groups": [
            {"group": group, "title": title, "codes": [{"code": c, "label": l} for c, l in codes]}
            for group, title, codes in ae.STRATEGY_GROUPS
        ],
        "sub_asset_types": ae.SUB_ASSET_TYPE_LABELS,
        "asset_types": ae.ASSET_TYPES_CONCENTRATION,
        "asset_macro_types": ae.ASSET_MACRO_TYPES,
        "turnover_sub_asset_types": ae.TURNOVER_SUB_ASSET_TYPE_LABELS,
        "instrument_code_types": ae.INSTRUMENT_CODE_TYPES,
        "market_code_types": ae.MARKET_CODE_TYPES,
        "market_code_types_with_not": ae.MARKET_CODE_TYPES_WITH_NOT,
        "position_types": ae.POSITION_TYPES,
        "aii_derivative_types": ae.AII_DERIVATIVE_TYPES,
        "aii_put_call_types": ae.AII_PUT_CALL_TYPES,
        "typical_position_sizes": ae.TYPICAL_POSITION_SIZES,
        "redemption_frequencies": ae.REDEMPTION_FREQUENCIES,
        "investor_group_types": ae.INVESTOR_GROUP_TYPES,
        "transaction_types": ae.TRANSACTION_TYPES,
        "market_risk_measures": [
            {"code": code, "label": label, "mandatory_under_24_2": mandatory}
            for code, label, mandatory in ae.MARKET_RISK_MEASURE_TYPES
        ],
        "var_calculation_methods": ae.VAR_CALC_METHODS,
        "geographical_regions": [{"key": key, "nav_tag": nav, "aum_tag": aum}
                                 for key, nav, aum in ae.GEO_REGIONS],
        "liquidity_buckets": [{"key": key, "label": label} for key, label in ae.LIQUIDITY_BUCKETS],
        "months": list(ae.MONTHS),
        "article_24_2_codes": sorted(ae.ARTICLE_24_2_CODES),
        "article_24_2_and_24_4_codes": sorted(ae.ARTICLE_24_2_AND_24_4_CODES),
        "fixed_cardinalities": {
            "aifm_principal_markets": N_AIFM_MARKETS,
            "aifm_principal_instruments": N_AIFM_INSTRUMENTS,
            "main_instruments": N_MAIN_INSTRUMENTS,
            "ten_principal_exposures": N_PRINCIPAL_EXPOSURES,
            "portfolio_concentrations": N_PORTFOLIO_CONCENTRATIONS,
            "aif_principal_markets": N_AIF_MARKETS,
            "counterparty_exposures": N_COUNTERPARTY_EXPOSURES,
            "borrowing_sources": N_BORROWING_SOURCES,
        },
        "schema_validation_available": aifmd_xsd.available(),
    }


def _submission(payload: dict[str, Any]) -> ae.AifmdSubmission:
    """Builds the engine's submission from the same two dictionaries the form
    produces, so the API and the engine agree on one set of field names.

    JSON has no date type, so a client sends every date as an ISO string.
    The engine expects real ``date`` objects and ignores anything else, which
    would silently drop a date rather than reject it — so the conversion
    happens here, at the boundary between the wire format and the domain."""
    aifm_info = _coerce_dates(payload.get("aifm_info") or {})
    aif_info = _coerce_dates(payload.get("aif_info") or {})
    period_start = _as_date(payload.get("period_start")) or date(date.today().year - 1, 1, 1)
    period_end = _as_date(payload.get("period_end")) or date(date.today().year - 1, 12, 31)
    return ae.submission_from_dicts(aifm_info, aif_info, period_start, period_end)


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _coerce_dates(value: Any) -> Any:
    """Turns every ISO date string held under a ``*_date`` key into a real
    ``date``, at any depth — the nested tables carry dates too."""
    if isinstance(value, dict):
        return {key: (_as_date(item) if _is_date_key(key) and isinstance(item, str) else _coerce_dates(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_coerce_dates(item) for item in value]
    return value


def _is_date_key(key: str) -> bool:
    return key.endswith("_date") or key.endswith("_dates")


def aifmd_validate_service(payload: dict[str, Any]) -> ValidationResult:
    return issues_to_payload(_submission(payload).validation_issues())


def aifmd_generate_service(payload: dict[str, Any]) -> GenerationResult:
    submission = _submission(payload)

    validation = issues_to_payload(submission.validation_issues())
    if not validation.valid:
        return GenerationResult(generated=False, validation=validation)

    files: list[GeneratedFile] = []
    for key, label, build_xml, build_filename in FILES:
        xml = build_xml(submission)
        result = aifmd_xsd.validate(xml, key)
        files.append(GeneratedFile(
            key=key, label=label, filename=build_filename(submission), content=xml,
            record_count=aifmd_xsd.record_count(xml),
            schema_validation=SchemaResult(available=result.available, valid=result.valid,
                                           errors=result.errors, detail=result.detail or None),
        ))

    # A schema failure is a defect of this service, not of the data, and a
    # file carrying more than one record is refused by the CSSF (FOR-010).
    blocked = [f for f in files
               if (f.schema_validation.available and not f.schema_validation.valid) or f.record_count != 1]
    if blocked:
        return GenerationResult(generated=False, validation=validation, files=files)
    return GenerationResult(generated=True, validation=validation, files=files)


def inspect_upload_service(content: bytes, filename: str | None = None) -> dict[str, Any]:
    """Identifies an uploaded XML as the AIFM or the AIF file and validates it
    against the matching ESMA schema."""
    file_key = aifmd_xsd.detect_file(content)
    if file_key is None:
        return {
            "recognised": False, "file_key": None, "label": None, "filename": filename,
            "record_count": 0,
            "schema_validation": SchemaResult(
                available=aifmd_xsd.available(), valid=False,
                errors=["The file could not be identified as an AIFMD Annex IV filing. Its root element must be "
                        "AIFMReportingInfo (AIFM file) or AIFReportingInfo (AIF file)."]),
        }
    result = aifmd_xsd.validate(content, file_key)
    return {
        "recognised": True, "file_key": file_key, "label": aifmd_xsd.FILE_LABELS[file_key],
        "filename": filename, "record_count": aifmd_xsd.record_count(content),
        "schema_validation": SchemaResult(available=result.available, valid=result.valid,
                                          errors=result.errors, detail=result.detail or None),
    }


def aifmd_template_service() -> tuple[str, bytes]:
    """ESMA's consolidated reporting template, which Auto mode parses."""
    return ("2013-1359_consolidated_aifmd_reporting_template-v1.1_revised.xlsx",
            ae.load_official_template_bytes())


def aifmd_parse_workbook_service(content: bytes) -> dict[str, Any]:
    """Reads a filled-in copy of ESMA's consolidated template back into the
    two dictionaries the form and the engine share."""
    aifm_info, aif_info, errors = ae.parse_aifmd_workbook(content)
    return {"aifm_info": aifm_info, "aif_info": aif_info, "errors": errors}
