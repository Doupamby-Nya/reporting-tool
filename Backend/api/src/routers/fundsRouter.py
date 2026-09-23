"""Routes for the registry of funds and share classes under mandate."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, File, UploadFile
from fastapi.responses import Response

from models.commonModel import fail, ok, server_error
from services import fundsService

fundsRouter = APIRouter(tags=["Funds"])


@fundsRouter.get("/funds", summary="Every fund and share class under mandate")
def funds_router():
    try:
        return ok(fundsService.funds_service())
    except Exception as exc:
        logging.exception("Reading the fund registry failed")
        return server_error(f"Could not read the registry: {exc}")


@fundsRouter.get("/funds/template", summary="Download the standardised ingestion workbook")
def funds_template_router():
    try:
        filename, payload, media_type = fundsService.fund_template_service()
    except Exception as exc:
        logging.exception("Building the ingestion template failed")
        return server_error(f"Could not build the template: {exc}")
    return Response(content=payload, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@fundsRouter.post("/funds/parse", summary="Read a filled-in ingestion workbook")
async def funds_parse_router(file: UploadFile = File(...)):
    """Reads without committing: the rows and the problems are both returned
    so the preparer can see what would be added before the registry changes."""
    try:
        return ok(fundsService.fund_parse_service(await file.read()))
    except Exception as exc:
        logging.exception("Parsing the ingestion workbook failed")
        return server_error(f"Could not read this workbook: {exc}")


@fundsRouter.post("/funds", summary="Add or update registry records")
def funds_add_router(payload: dict = Body(default_factory=dict)):
    try:
        return ok(fundsService.fund_add_service(payload.get("funds") or []))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Updating the fund registry failed")
        return server_error(f"Could not update the registry: {exc}")


@fundsRouter.post("/funds/demo", summary="Load the fictitious demo dataset")
def funds_demo_router():
    try:
        return ok(fundsService.fund_demo_service())
    except Exception as exc:
        logging.exception("Loading the demo dataset failed")
        return server_error(f"Could not load the demo dataset: {exc}")


@fundsRouter.delete("/funds", summary="Empty the registry")
def funds_reset_router():
    try:
        return ok(fundsService.fund_reset_service())
    except Exception as exc:
        logging.exception("Emptying the fund registry failed")
        return server_error(f"Could not empty the registry: {exc}")


@fundsRouter.delete("/funds/{fund_id}", summary="Remove one share class")
def funds_delete_router(fund_id: str):
    try:
        return ok(fundsService.fund_delete_service(fund_id))
    except Exception as exc:
        logging.exception("Removing %s from the fund registry failed", fund_id)
        return server_error(f"Could not remove this record: {exc}")
