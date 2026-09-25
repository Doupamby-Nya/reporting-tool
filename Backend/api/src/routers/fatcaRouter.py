"""Routes for FATCA and CRS reporting."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response

from models.commonModel import ApiResponse, fail, not_found, ok, server_error
from models.fatcaModel import NotificationsRequest, PreparersRequest
from services import fatcaReportingService as service, inspectService

fatcaRouter = APIRouter(prefix="/fatca", tags=["FATCA & CRS"])


@fatcaRouter.get("/preparers", summary="The preparer records a return can be filed under", response_model=ApiResponse[dict[str, Any]])
def fatca_preparers_router():
    try:
        return ok(service.fatca_preparers_service())
    except Exception as exc:
        logging.exception("Reading the FATCA preparers failed")
        return server_error(f"Could not read the preparers: {exc}")


@fatcaRouter.put("/preparers", summary="Replace the preparer records", response_model=ApiResponse[dict[str, Any]])
def fatca_save_preparers_router(preparers: PreparersRequest):
    try:
        return ok(service.fatca_save_preparers_service(preparers.root))
    except Exception as exc:
        logging.exception("Saving the FATCA preparers failed")
        return server_error(f"Could not save the preparers: {exc}")


@fatcaRouter.get("/template", summary="Download the blank reporting workbook")
def fatca_template_router(reporting_year: int | None = Query(default=None)):
    try:
        filename, payload, media_type = service.fatca_template_service(reporting_year)
    except Exception as exc:
        logging.exception("Building the FATCA template failed")
        return server_error(f"Could not build the template: {exc}")
    return Response(content=payload, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@fatcaRouter.post("/classify", summary="Classify the accounts of a filled-in workbook", response_model=ApiResponse[dict[str, Any]])
async def fatca_classify_router(file: UploadFile = File(...), parameters: str = Form(default="{}")):
    try:
        return ok(service.fatca_classify_service(await file.read(), json.loads(parameters or "{}")))
    except json.JSONDecodeError as exc:
        return fail(f"The 'parameters' field is not valid JSON: {exc}")
    except Exception as exc:
        logging.exception("Classifying the FATCA workbook failed")
        return server_error(f"Could not classify this workbook: {exc}")


@fatcaRouter.post("/generate", summary="Build the FATCA and CRS XML returns", response_model=ApiResponse[dict[str, Any]])
async def fatca_generate_router(file: UploadFile = File(...), parameters: str = Form(default="{}"),
                                preparer: str = Form(default="")):
    """The preparer is named, not described: the record itself is looked up
    from the configured preparers, so a return cannot be filed under one that
    is not on file."""
    try:
        return ok(service.fatca_generate_service(
            await file.read(), json.loads(parameters or "{}"), preparer or None))
    except json.JSONDecodeError as exc:
        return fail(f"The 'parameters' field is not valid JSON: {exc}")
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Generating the FATCA return failed")
        return server_error(f"Could not generate the return: {exc}")


@fatcaRouter.get("/filer-categories", summary="The FATCA FI filer categories",
                response_model=ApiResponse[list[str]])
def fatca_filer_categories_router():
    try:
        return ok(service.fatca_filer_categories_service())
    except Exception as exc:
        logging.exception("Reading the filer categories failed")
        return server_error(f"Could not read the filer categories: {exc}")


@fatcaRouter.post("/inspect", summary="Identify and check a return produced earlier", response_model=ApiResponse[dict[str, Any]])
async def fatca_inspect_router(file: UploadFile = File(...)):
    """The AEOI schemas are not bundled, so the return is read and identified
    but not validated — and the answer says exactly that."""
    try:
        return ok(inspectService.inspect_service("fatca", await file.read()))
    except Exception as exc:
        logging.exception("Inspecting the FATCA return failed")
        return server_error(f"Could not read this return: {exc}")


@fatcaRouter.post("/notifications", summary="The GDPR notification letters owed to reported holders")
def fatca_notifications_router(request: NotificationsRequest):
    """Answers with the ZIP of letters itself rather than the envelope: the
    archive carries account holders' personal data, so it is streamed once to
    the preparer and not held anywhere on the way.

    The counts are returned in headers so the client can say how many letters
    were produced, and how many of them MS Word was available to convert.
    """
    xml_content = request.xml
    if not xml_content.strip():
        return fail("There is no filing to notify from; generate one first.")
    try:
        archive, letters, pdfs = service.fatca_notifications_service(
            xml_content, request.categories)
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Generating the notification letters failed")
        return server_error(f"Could not generate the letters: {exc}")

    if not letters:
        return fail("No reportable account holder matched the selected categories in this filing.")

    return Response(
        content=archive, media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="fatca_crs_data_notifications.zip"',
            "X-Letter-Count": str(letters),
            "X-Pdf-Count": str(pdfs),
            # The browser cannot read a custom header on a cross-origin
            # response unless the server says it may.
            "Access-Control-Expose-Headers": "X-Letter-Count, X-Pdf-Count, Content-Disposition",
        },
    )
