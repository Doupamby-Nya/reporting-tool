"""BCL statistical reporting — the six reports a Luxembourg fund files.

This service is the thin layer between the API and the engines in
domain/bcl/: it turns a request model into the row dictionaries the engines
expect, runs the business rules of each report's own compendium of
verification rules, builds the XML, and validates that XML against the real
BCL XSD schemas before handing it back. A file is only ever returned once
both gates pass.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from domain.bcl import bcl_codes, bcl_parser, bcl_xsd
from domain.bcl import bcl_engine as be
from domain.bcl import bcl_s220_engine as s220e
from models.bclModel import (
    BclSubmissionRequest, LedgerRequest, S44Request, S220Request, TptobsRequest,
)
from models.commonModel import (
    GeneratedFile, GenerationResult, SchemaResult, ValidationResult, issues_to_payload,
)

LEDGER_KEYS = ("s13", "s213", "s16")
ALL_KEYS = ("s13", "s213", "s16", "s220", "s44", "tptobs")


# =============================================================================
# Metadata
# =============================================================================

def bcl_reports_service() -> dict[str, Any]:
    """Everything a client needs to render the six forms: each report's
    identity, its chart of accounts and which breakdowns it demands."""
    reports = []
    for key in ALL_KEYS:
        if key == "s220":
            reports.append({
                "key": "s220", "label": s220e.REPORT_LABEL, "root": s220e.ROOT,
                "namespace": s220e.TARGET_NAMESPACE, "layout": s220e.LAYOUT,
                "file_code": s220e.FILE_CODE, "frequency": "Quarterly",
                "description": "Quarterly financial information on a NAF and each of its unit/share classes.",
                "chart_of_accounts": [{"item": code, "label": label} for code, label in s220e.S220_SECTION_6],
            })
            continue
        spec = be.ALL_SPECS[key]
        reports.append({
            "key": key, "label": spec.label, "root": spec.root, "namespace": spec.namespace,
            "layout": spec.layout, "file_code": spec.file_code,
            "frequency": _FREQUENCY[key], "description": spec.description,
            "assets": spec.assets, "liabilities": spec.liabilities,
            "has_maturity": spec.has_maturity,
        })
    return {"reports": reports, "breakdown_marker": be.BREAK}


_FREQUENCY = {
    "s13": "Monthly", "s213": "Quarterly", "s16": "Monthly",
    "s44": "Annual", "tptobs": "Monthly",
}


def bcl_codes_service() -> dict[str, Any]:
    """The BCL 2015 code lists and the TPTOBS security-level enumerations."""
    return {
        "sectors": bcl_codes.BCL_SECTOR_CODES,
        "maturities": bcl_codes.BCL_MATURITY_CODES,
        # A breakdown by country draws on the ISO 3166 list *plus* BCL's own
        # special codes (international organisations and the like), and a
        # breakdown by currency on ISO 4217 — a capture screen cannot offer a
        # valid breakdown without them, so they are served here rather than
        # duplicated in the client.
        "countries": sorted(bcl_codes.ISO_3166_ALPHA2),
        "currencies": sorted(bcl_codes.ISO_4217),
        "special_countries": bcl_codes.BCL_SPECIAL_COUNTRY_CODES,
        "no_breakdown": bcl_codes.NO_BREAKDOWN,
        "security_code_types": bcl_codes.SECURITY_CODE_TYPES,
        "hold_security_types": bcl_codes.HOLD_SECURITY_TYPES,
        "hold_types_by_item": {k: list(v) for k, v in bcl_codes.HOLD_TYPES_BY_ITEM.items()},
        "esa2010_security_types": bcl_codes.ESA2010_SECURITY_TYPES,
        "security_types_by_item": {k: list(v) for k, v in bcl_codes.SECURITY_TYPES_BY_ITEM.items()},
        "coupon_types": bcl_codes.COUPON_TYPES,
        "coupon_frequencies": bcl_codes.COUPON_FREQUENCIES,
        "quotation_types": bcl_codes.QUOTATION_TYPES,
        "s220": {
            "reporting_statuses": s220e.REPORTING_STATUSES,
            "nav_frequencies": s220e.NAV_FREQUENCIES,
            "nav_redemption_frequencies": s220e.NAV_REDEMPTION_FREQUENCIES,
            "open_closed_end": s220e.OPEN_CLOSED_END,
            "reason_for_closing_uci": s220e.REASON_FOR_CLOSING_UCI,
            "reason_for_closing_share_class": s220e.REASON_FOR_CLOSING_SC,
            "investor_base": s220e.INVESTOR_BASE,
        },
        "schema_validation_available": bcl_xsd.available(),
    }


def bcl_reference_file_service(report_key: str, kind: str) -> tuple[str, bytes]:
    """One of a report's official files — its chart of accounts, its
    instructions or its compendium of verification rules."""
    reference = be.reference_file(report_key, kind)
    if reference is None:
        raise LookupError(f"No '{kind}' document is bundled for report '{report_key}'.")
    return reference


# =============================================================================
# Validation and generation
# =============================================================================

def _schema_result(xml: str, report_key: str) -> SchemaResult:
    result = bcl_xsd.validate(xml, report_key)
    return SchemaResult(available=result.available, valid=result.valid,
                        errors=result.errors, detail=result.detail or None)


def _ledger_rows(request: LedgerRequest) -> tuple[list[dict], list[dict]]:
    return ([line.to_row() for line in request.assets],
            [line.to_row() for line in request.liabilities])


def validate_ledger_service(report_key: str, request: LedgerRequest) -> ValidationResult:
    if report_key not in LEDGER_KEYS:
        raise LookupError(f"'{report_key}' is not a balance-sheet report; expected one of {', '.join(LEDGER_KEYS)}.")
    spec = be.LEDGER_SPECS[report_key]
    assets, liabilities = _ledger_rows(request)
    return issues_to_payload(be.validate_ledger(assets, liabilities, report_key, request.header.to_domain(spec.layout)))


def generate_ledger_service(report_key: str, request: LedgerRequest) -> GenerationResult:
    if report_key not in LEDGER_KEYS:
        raise LookupError(f"'{report_key}' is not a balance-sheet report; expected one of {', '.join(LEDGER_KEYS)}.")
    spec = be.LEDGER_SPECS[report_key]
    header = request.header.to_domain(spec.layout)
    assets, liabilities = _ledger_rows(request)

    validation = issues_to_payload(be.validate_ledger(assets, liabilities, report_key, header))
    if not validation.valid:
        return GenerationResult(generated=False, validation=validation)

    xml = be.build_ledger_xml(report_key, header, assets, liabilities)
    return _result(validation, report_key, spec.label, xml,
                   be.ledger_filename(report_key, header, request.creation_date, request.sequence))


def validate_s44_service(request: S44Request) -> ValidationResult:
    rows = [row.to_row() for row in request.marketing_countries]
    return issues_to_payload(be.validate_s44(rows, request.header.to_domain(be.S44_SPEC.layout)))


def generate_s44_service(request: S44Request) -> GenerationResult:
    header = request.header.to_domain(be.S44_SPEC.layout)
    rows = [row.to_row() for row in request.marketing_countries]

    validation = issues_to_payload(be.validate_s44(rows, header))
    if not validation.valid:
        return GenerationResult(generated=False, validation=validation)

    xml = be.build_s44_xml(header, rows)
    return _result(validation, "s44", be.S44_SPEC.label, xml,
                   be.s44_filename(header, request.creation_date, request.sequence))


def _tptobs_parts(request: TptobsRequest):
    """TPTOBS line totals are always the sum of the securities attached to
    them, so they are derived here rather than sent by the client."""
    securities = [security.to_row() for security in request.securities]
    assets = _tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_ASSETS)
    liabilities = _tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_LIABILITIES)
    return request.header.to_domain(be.TPTOBS_SPEC.layout), assets, liabilities, securities


def _tptobs_lines(securities: list[dict], specs: list[dict[str, str]]) -> list[dict]:
    lines = []
    for spec in specs:
        group = be.securities_of(securities, spec["item"])
        if group:
            lines.append({"item": spec["item"], "country": spec["country"], "currency": spec["currency"],
                          "sector": spec["sector"], "amount": float(be.line_total(group) or 0)})
    return lines


def validate_tptobs_service(request: TptobsRequest) -> ValidationResult:
    header, assets, liabilities, securities = _tptobs_parts(request)
    return issues_to_payload(be.validate_tptobs(assets, liabilities, securities, header))


def generate_tptobs_service(request: TptobsRequest) -> GenerationResult:
    header, assets, liabilities, securities = _tptobs_parts(request)

    validation = issues_to_payload(be.validate_tptobs(assets, liabilities, securities, header))
    if not validation.valid:
        return GenerationResult(generated=False, validation=validation)

    xml = be.build_tptobs_xml(header, assets, liabilities, securities)
    return _result(validation, "tptobs", be.TPTOBS_SPEC.label, xml,
                   be.tptobs_filename(header, request.creation_date, request.sequence))


def _s220_submission(request: S220Request) -> s220e.S220Submission:
    data = request.model_dump(exclude={"creation_date", "sequence", "sender_employees", "share_classes"})
    return s220e.S220Submission(
        **data,
        sender_employees=[contact.model_dump() for contact in request.sender_employees],
        share_classes=[s220e.ShareClass(**share_class.model_dump()) for share_class in request.share_classes],
    )


def validate_s220_service(request: S220Request) -> ValidationResult:
    return issues_to_payload(s220e.validation_issues(_s220_submission(request)))


def generate_s220_service(request: S220Request) -> GenerationResult:
    submission = _s220_submission(request)

    validation = issues_to_payload(s220e.validation_issues(submission))
    if not validation.valid:
        return GenerationResult(generated=False, validation=validation)

    xml = s220e.build_s220_xml(submission)
    return _result(validation, "s220", s220e.REPORT_LABEL, xml,
                   submission.filename(request.creation_date, request.sequence))


def _result(validation: ValidationResult, key: str, label: str, xml: str, filename: str) -> GenerationResult:
    return GenerationResult(
        generated=True, validation=validation,
        files=[GeneratedFile(key=key, label=label, filename=filename, content=xml,
                             schema_validation=_schema_result(xml, key))],
    )


# =============================================================================
# Dispatch, cross-checks and uploads
# =============================================================================

_VALIDATORS = {
    "s44": (S44Request, validate_s44_service),
    "tptobs": (TptobsRequest, validate_tptobs_service),
    "s220": (S220Request, validate_s220_service),
}
_GENERATORS = {
    "s44": (S44Request, generate_s44_service),
    "tptobs": (TptobsRequest, generate_tptobs_service),
    "s220": (S220Request, generate_s220_service),
}


def validate_report_service(report_key: str, payload: dict[str, Any]) -> ValidationResult:
    """Validates any of the six reports from a raw payload."""
    if report_key in LEDGER_KEYS:
        return validate_ledger_service(report_key, LedgerRequest(**payload))
    if report_key not in _VALIDATORS:
        raise LookupError(f"Unknown BCL report '{report_key}'; expected one of {', '.join(ALL_KEYS)}.")
    model, service = _VALIDATORS[report_key]
    return service(model(**payload))


def generate_report_service(report_key: str, payload: dict[str, Any]) -> GenerationResult:
    """Generates any of the six reports from a raw payload."""
    if report_key in LEDGER_KEYS:
        return generate_ledger_service(report_key, LedgerRequest(**payload))
    if report_key not in _GENERATORS:
        raise LookupError(f"Unknown BCL report '{report_key}'; expected one of {', '.join(ALL_KEYS)}.")
    model, service = _GENERATORS[report_key]
    return service(model(**payload))


def cross_checks_service(submission: BclSubmissionRequest) -> ValidationResult:
    """The checks BCL runs after reception: the five security-by-security
    lines must agree between the balance sheet and TPTOBS, and the shares
    issued must equal the S 2.20 total net asset value (item 3020)."""
    from domain.shared.xml_common import Issue as DomainIssue

    issues: list[DomainIssue] = []
    securities = [security.to_row() for security in submission.tptobs.securities] if submission.tptobs else []
    tptobs_assets = _tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_ASSETS)
    tptobs_liabilities = _tptobs_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_LIABILITIES)
    nav_ref_month = submission.s220.nav_ref_month if submission.s220 else None

    for key in ("s13", "s213"):
        ledger = getattr(submission, key)
        if ledger is None or not (ledger.assets or ledger.liabilities):
            continue
        label = be.LEDGER_SPECS[key].label
        assets, liabilities = _ledger_rows(ledger)
        for issue in be.cross_check_ledger_vs_tptobs(assets, liabilities, tptobs_assets,
                                                     tptobs_liabilities, securities):
            issues.append(DomainIssue(issue.level, issue.code, f"{label} vs TPTOBS: {issue.message}"))
        for issue in be.cross_check_ledger_vs_s220(liabilities, nav_ref_month):
            issues.append(DomainIssue(issue.level, issue.code, f"{label} vs S 2.20: {issue.message}"))

    if submission.s220 is not None and securities:
        for issue in s220e.cross_check_s220_vs_tptobs(_s220_submission(submission.s220), securities):
            issues.append(DomainIssue(issue.level, issue.code, f"S 2.20 vs TPTOBS: {issue.message}"))

    return issues_to_payload(issues)


def inspect_upload_service(content: bytes, filename: str | None = None) -> dict[str, Any]:
    """Identifies an uploaded XML as one of the six BCL reports and validates
    it against that report's own schema."""
    report_key = bcl_xsd.detect_report(content)
    if report_key is None:
        return {
            "recognised": False, "report_key": None, "label": None, "filename": filename,
            "schema_validation": SchemaResult(
                available=bcl_xsd.available(), valid=False,
                errors=["The file could not be identified as one of the six BCL reports. Its root element must "
                        "be S13, S213, S16, S220, S44 or SBS."]),
        }
    label = s220e.REPORT_LABEL if report_key == "s220" else be.REPORT_LABELS.get(report_key, report_key)
    result = bcl_xsd.validate(content, report_key)

    # The filing is read back into the form that would produce it, so an
    # upload re-opens the work rather than only reporting on it. A document
    # that fails its schema is still parsed: the point of re-opening it is
    # usually to correct exactly what the schema objected to.
    _, captured = bcl_parser.parse(content)

    return {
        "recognised": True, "report_key": report_key, "label": label, "filename": filename,
        "schema_validation": SchemaResult(available=result.available, valid=result.valid,
                                          errors=result.errors, detail=result.detail or None),
        "data": captured,
    }
