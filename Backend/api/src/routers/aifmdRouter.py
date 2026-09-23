"""Routes for AIFMD Annex IV reporting."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import Response

from models.commonModel import fail, ok, server_error
from services import aifmdReportingService as service, formsService

aifmdRouter = APIRouter(prefix="/aifmd", tags=["AIFMD"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@aifmdRouter.get("/form", summary="The capture form of the two AIFMD files")
def aifmd_form_router():
    """The form as data, derived from the generator itself.

    AIFMD is not one of the workbook-driven regimes, so it needs its own
    route rather than the shared one: the four of those bind a generic
    handler, and splitting them out left this one behind — which is exactly
    the kind of gap the split was meant to make visible.
    """
    try:
        return ok(formsService.filing_form_service("aifmd"))
    except Exception as exc:
        logging.exception("Building the AIFMD capture form failed")
        return server_error(f"Could not build the capture form: {exc}")


@aifmdRouter.get("/metadata", summary="Code lists and structural rules of the two AIFMD files")
def aifmd_metadata_router():
    try:
        return ok(service.aifmd_metadata_service())
    except Exception as exc:
        logging.exception("Reading the AIFMD metadata failed")
        return server_error(f"Could not read the AIFMD metadata: {exc}")


@aifmdRouter.post("/validate", summary="Run the CSSF controls on a filing")
def aifmd_validate_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.aifmd_validate_service(payload))
    except (TypeError, ValueError) as exc:
        return fail(f"Could not read this submission: {exc}")
    except Exception as exc:
        logging.exception("Validating the AIFMD filing failed")
        return server_error(f"Could not validate this filing: {exc}")


@aifmdRouter.post("/generate", summary="Build the DATMAN and DATAIF files")
def aifmd_generate_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(service.aifmd_generate_service(payload))
    except (TypeError, ValueError) as exc:
        return fail(f"Could not read this submission: {exc}")
    except Exception as exc:
        logging.exception("Generating the AIFMD filing failed")
        return server_error(f"Could not generate this filing: {exc}")


@aifmdRouter.post("/inspect", summary="Identify and schema-validate an uploaded AIFMD filing")
async def aifmd_inspect_router(file: UploadFile = File(...)):
    try:
        return ok(service.inspect_upload_service(await file.read(), file.filename))
    except Exception as exc:
        logging.exception("Inspecting the uploaded AIFMD file failed")
        return server_error(f"Could not read this file: {exc}")


@aifmdRouter.get("/template", summary="Download ESMA's consolidated reporting template")
def aifmd_template_router():
    try:
        filename, payload = service.aifmd_template_service()
    except Exception as exc:
        logging.exception("Serving the AIFMD template failed")
        return server_error(f"Could not read the consolidated template: {exc}")
    return Response(content=payload, media_type=XLSX_MEDIA_TYPE,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@aifmdRouter.post("/template/parse", summary="Read a filled-in consolidated template")
async def aifmd_parse_template_router(file: UploadFile = File(...)):
    try:
        return ok(service.aifmd_parse_workbook_service(await file.read()))
    except Exception as exc:
        logging.exception("Parsing the AIFMD workbook failed")
        return server_error(f"Could not read this workbook: {exc}")
