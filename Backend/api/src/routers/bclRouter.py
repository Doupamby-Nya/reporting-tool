"""Routes for the BCL statistical reports."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import Response

from models.bclModel import BclSubmissionRequest
from models.commonModel import fail, not_found, ok, server_error
from services import bclReportingService as service

bclRouter = APIRouter(prefix="/bcl", tags=["BCL"])

REFERENCE_KINDS = ("report", "instructions", "rules")
MEDIA_TYPES = {"pdf": "application/pdf", "xls": "application/vnd.ms-excel",
               "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@bclRouter.get("/reports", summary="The six BCL reports and their charts of accounts")
def bcl_reports_router():
    try:
        return ok(service.bcl_reports_service())
    except Exception as exc:
        logging.exception("Listing the BCL reports failed")
        return server_error(f"Could not list the BCL reports: {exc}")


@bclRouter.get("/codes", summary="The BCL 2015 code lists and TPTOBS enumerations")
def bcl_codes_router():
    try:
        return ok(service.bcl_codes_service())
    except Exception as exc:
        logging.exception("Listing the BCL code lists failed")
        return server_error(f"Could not list the BCL code lists: {exc}")


@bclRouter.post("/{report_key}/validate", summary="Run a report's verification rules")
def bcl_validate_router(report_key: str, payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.validate_report_service(report_key, payload))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Validating BCL report %s failed", report_key)
        return server_error(f"Could not validate this {report_key} submission: {exc}")


@bclRouter.post("/{report_key}/generate", summary="Build a report's XML filing")
def bcl_generate_router(report_key: str, payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.generate_report_service(report_key, payload))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Generating BCL report %s failed", report_key)
        return server_error(f"Could not generate this {report_key} filing: {exc}")


@bclRouter.post("/cross-checks", summary="Consistency between the balance sheet, TPTOBS and S 2.20")
def bcl_cross_checks_router(submission: BclSubmissionRequest):
    try:
        return ok(service.cross_checks_service(submission))
    except Exception as exc:
        logging.exception("Running the BCL cross-checks failed")
        return server_error(f"Could not run the cross-report checks: {exc}")


@bclRouter.post("/inspect", summary="Identify and schema-validate an uploaded BCL filing")
async def bcl_inspect_router(file: UploadFile = File(...)):
    try:
        return ok(service.inspect_upload_service(await file.read(), file.filename))
    except Exception as exc:
        logging.exception("Inspecting the uploaded BCL file failed")
        return server_error(f"Could not read this file: {exc}")


@bclRouter.get("/{report_key}/reference/{kind}", summary="Download a report's official BCL document")
def bcl_reference_router(report_key: str, kind: str):
    if kind not in REFERENCE_KINDS:
        return fail(f"Unknown document kind '{kind}'; expected one of {', '.join(REFERENCE_KINDS)}.")
    try:
        filename, payload = service.bcl_reference_file_service(report_key, kind)
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Serving the BCL reference file failed")
        return server_error(f"Could not read this document: {exc}")
    extension = filename.rsplit(".", 1)[-1].lower()
    return Response(
        content=payload, media_type=MEDIA_TYPES.get(extension, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
