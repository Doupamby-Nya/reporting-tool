"""Routes for the BCL statistical reports.

Each of the six reports has its own validate and generate routes, typed with
its own request model, so the OpenAPI page documents what each one takes and
a malformed body is refused with 422 before it reaches an engine. The module
does not use ``from __future__ import annotations``: those routes are built in
a loop, and FastAPI must see the model itself rather than its name.
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import Response

from models.bclModel import BclSubmissionRequest, LedgerRequest, S44Request, S220Request, TptobsRequest
from models.commonModel import (
    ApiResponse, GenerationResult, ValidationResult, fail, not_found, ok, server_error,
)
from services import bclReportingService as service

bclRouter = APIRouter(prefix="/bcl", tags=["BCL"])

REFERENCE_KINDS = ("report", "instructions", "rules")
MEDIA_TYPES = {"pdf": "application/pdf", "xls": "application/vnd.ms-excel",
               "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@bclRouter.get("/reports", summary="The six BCL reports and their charts of accounts",
               response_model=ApiResponse[dict[str, Any]])
def bcl_reports_router():
    try:
        return ok(service.bcl_reports_service())
    except Exception as exc:
        logging.exception("Listing the BCL reports failed")
        return server_error(f"Could not list the BCL reports: {exc}")


@bclRouter.get("/codes", summary="The BCL 2015 code lists and TPTOBS enumerations",
               response_model=ApiResponse[dict[str, Any]])
def bcl_codes_router():
    try:
        return ok(service.bcl_codes_service())
    except Exception as exc:
        logging.exception("Listing the BCL code lists failed")
        return server_error(f"Could not list the BCL code lists: {exc}")


REPORT_MODELS = {
    "s13": LedgerRequest, "s213": LedgerRequest, "s16": LedgerRequest,
    "s44": S44Request, "tptobs": TptobsRequest, "s220": S220Request,
}


def _report_routes(report_key: str, model: type) -> None:
    @bclRouter.post(f"/{report_key}/validate", summary=f"Run the {report_key.upper()} verification rules",
                    response_model=ApiResponse[ValidationResult], name=f"bcl_{report_key}_validate")
    def validate_route(request: model):
        return bcl_validate_router(report_key, request.model_dump())

    @bclRouter.post(f"/{report_key}/generate", summary=f"Build the {report_key.upper()} XML filing",
                    response_model=ApiResponse[GenerationResult], name=f"bcl_{report_key}_generate")
    def generate_route(request: model):
        return bcl_generate_router(report_key, request.model_dump())


for _key, _model in REPORT_MODELS.items():
    _report_routes(_key, _model)


# Any other report key: answered 404 by the service, which names the six.
@bclRouter.post("/{report_key}/validate", summary="Run a report's verification rules", include_in_schema=False)
def bcl_validate_router(report_key: str, payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.validate_report_service(report_key, payload))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Validating BCL report %s failed", report_key)
        return server_error(f"Could not validate this {report_key} submission: {exc}")


@bclRouter.post("/{report_key}/generate", summary="Build a report's XML filing", include_in_schema=False)
def bcl_generate_router(report_key: str, payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.generate_report_service(report_key, payload))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Generating BCL report %s failed", report_key)
        return server_error(f"Could not generate this {report_key} filing: {exc}")


@bclRouter.post("/cross-checks", summary="Consistency between the balance sheet, TPTOBS and S 2.20",
                response_model=ApiResponse[ValidationResult])
def bcl_cross_checks_router(submission: BclSubmissionRequest):
    try:
        return ok(service.cross_checks_service(submission))
    except Exception as exc:
        logging.exception("Running the BCL cross-checks failed")
        return server_error(f"Could not run the cross-report checks: {exc}")


@bclRouter.post("/inspect", summary="Identify and schema-validate an uploaded BCL filing",
                response_model=ApiResponse[dict[str, Any]])
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
