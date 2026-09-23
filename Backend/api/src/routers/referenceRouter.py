"""Routes for the reference data shared across the regimes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response

from models.commonModel import ApiResponse, not_found, ok, server_error
from services import filingsService, referenceService as service

referenceRouter = APIRouter(prefix="/reference", tags=["Reference"])


@referenceRouter.get("/modules", summary="The regulatory modules the platform supports",
    response_model=ApiResponse[list[dict[str, Any]]])
def reference_modules_router():
    try:
        return ok(service.modules_service())
    except Exception as exc:
        logging.exception("Listing the modules failed")
        return server_error(f"Could not list the regulatory modules: {exc}")


@referenceRouter.get("/regulations/{module_key}", summary="Regulator documents bundled for a module",
    response_model=ApiResponse[list[dict[str, Any]]])
def reference_regulations_router(module_key: str):
    try:
        return ok(service.regulations_service(module_key))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Listing the regulatory library of %s failed", module_key)
        return server_error(f"Could not list the regulatory library: {exc}")


@referenceRouter.get("/regulations/{module_key}/{index}/download", summary="Download a regulator document")
def reference_regulation_download_router(
    module_key: str, index: int,
    download: bool = Query(default=False,
                           description="True saves the file; the default shows it in the page"),
):
    """Serves the document inline by default.

    It used to be sent as an attachment unconditionally, which is exactly why
    the preview never appeared: a browser does not render an attachment
    inside a frame, it saves it. The reference screen exists to *show* the
    text, so the caller asks for an attachment only when it wants the file
    on disk.
    """
    try:
        filename, payload = service.regulation_document_service(module_key, index)
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Serving a regulatory document failed")
        return server_error(f"Could not read this document: {exc}")

    disposition = "attachment" if download else "inline"
    return Response(
        content=payload, media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'})


@referenceRouter.get("/regimes", summary="The regimes driven by a workbook template",
    response_model=ApiResponse[list[dict[str, Any]]])
def reference_regimes_router():
    """One catalogue, not one per regime: this is reference data about the
    regimes, so it belongs beside the module list rather than inside any one
    regime's router."""
    try:
        return ok(filingsService.filing_regimes_service())
    except Exception as exc:
        logging.exception("Listing the filing regimes failed")
        return server_error(f"Could not list the regimes: {exc}")


@referenceRouter.get("/clients", summary="The client records a filing can be prepared for",
    response_model=ApiResponse[list[dict[str, Any]]])
def reference_clients_router():
    try:
        return ok(service.clients_service())
    except Exception as exc:
        logging.exception("Listing the clients failed")
        return server_error(f"Could not list the clients: {exc}")
