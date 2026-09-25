"""Routes for the registry of funds and share classes under mandate.

The registry is the organisation's own. Any signed-in user may read it — the
dashboard summarises it — but only a PRIIPs user may change it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from models.commonModel import ApiResponse, fail, ok, server_error
from models.fundsModel import FundsRequest
from routers.dependencies import current_user, require_module
from services import fundsService, workflowService
from services.authService import CurrentUser

fundsRouter = APIRouter(tags=["Funds"], dependencies=[Depends(current_user)])


@fundsRouter.get("/funds", summary="Every fund and share class under mandate", response_model=ApiResponse[list[dict[str, Any]]])
def funds_router():
    try:
        return ok(fundsService.funds_service())
    except Exception as exc:
        logging.exception("Reading the fund registry failed")
        return server_error(f"Could not read the registry: {exc}")


@fundsRouter.get("/funds/template", summary="Download the standardised ingestion workbook", dependencies=[Depends(require_module("priips"))])
def funds_template_router():
    try:
        filename, payload, media_type = fundsService.fund_template_service()
    except Exception as exc:
        logging.exception("Building the ingestion template failed")
        return server_error(f"Could not build the template: {exc}")
    return Response(content=payload, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@fundsRouter.post("/funds/parse", summary="Read a filled-in ingestion workbook", response_model=ApiResponse[dict[str, Any]],
                  dependencies=[Depends(require_module("priips"))])
async def funds_parse_router(file: UploadFile = File(...)):
    """Reads without committing: the rows and the problems are both returned
    so the preparer can see what would be added before the registry changes."""
    try:
        return ok(fundsService.fund_parse_service(await file.read()))
    except Exception as exc:
        logging.exception("Parsing the ingestion workbook failed")
        return server_error(f"Could not read this workbook: {exc}")


@fundsRouter.post("/funds", summary="Add or update registry records", response_model=ApiResponse[list[dict[str, Any]]],
                  dependencies=[Depends(require_module("priips"))])
def funds_add_router(request: FundsRequest):
    try:
        return ok(fundsService.fund_add_service(request.funds))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Updating the fund registry failed")
        return server_error(f"Could not update the registry: {exc}")


@fundsRouter.post("/funds/demo", summary="Load the fictitious demo dataset", response_model=ApiResponse[list[dict[str, Any]]],
                  dependencies=[Depends(require_module("priips"))])
def funds_demo_router():
    try:
        return ok(fundsService.fund_demo_service())
    except Exception as exc:
        logging.exception("Loading the demo dataset failed")
        return server_error(f"Could not load the demo dataset: {exc}")


@fundsRouter.delete("/funds", summary="Empty the registry", response_model=ApiResponse[list[dict[str, Any]]])
def funds_reset_router(user: CurrentUser = Depends(require_module("priips"))):
    try:
        result = fundsService.fund_reset_service()
        workflowService.log_audit_service("PRIIPS registry emptied", "funds", user.email)
        return ok(result)
    except Exception as exc:
        logging.exception("Emptying the fund registry failed")
        return server_error(f"Could not empty the registry: {exc}")


@fundsRouter.delete("/funds/{fund_id}", summary="Remove one share class", response_model=ApiResponse[list[dict[str, Any]]])
def funds_delete_router(fund_id: str, user: CurrentUser = Depends(require_module("priips"))):
    try:
        result = fundsService.fund_delete_service(fund_id)
        workflowService.log_audit_service("PRIIPS share class removed", fund_id, user.email)
        return ok(result)
    except Exception as exc:
        logging.exception("Removing %s from the fund registry failed", fund_id)
        return server_error(f"Could not remove this record: {exc}")
