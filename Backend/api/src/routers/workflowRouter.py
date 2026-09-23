"""Routes for the document lifecycle, the audit trail and saved drafts."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

from models.commonModel import ApiResponse, fail, not_found, ok, server_error
from services import draftService, workflowService

workflowRouter = APIRouter(tags=["Workflow"])


class RecordGeneratedRequest(BaseModel):
    document_id: str = Field(description="The file name the filing was produced under")
    label: str = ""
    user: str = ""


class TransitionRequest(BaseModel):
    status: str = Field(description=f"One of: {', '.join(workflowService.STATUSES)}")
    user: str = ""
    comment: str = ""


class SaveDraftRequest(BaseModel):
    name: str
    data: dict[str, Any] = {}
    user: str = ""


# --- documents ---------------------------------------------------------------

@workflowRouter.get("/documents/{module_key}", summary="Every filing generated for a module",
    response_model=ApiResponse[dict[str, Any]])
def documents_list_router(module_key: str):
    try:
        return ok(workflowService.list_documents_service(module_key))
    except Exception as exc:
        logging.exception("Listing the documents of %s failed", module_key)
        return server_error(f"Could not list the documents: {exc}")


@workflowRouter.post("/documents/{module_key}", summary="Register a generated filing",
    response_model=ApiResponse[dict[str, Any]])
def documents_record_router(module_key: str, request: RecordGeneratedRequest):
    try:
        return ok(workflowService.record_generated_service(
            module_key, request.document_id, request.label, request.user))
    except Exception as exc:
        logging.exception("Recording a generated document failed")
        return server_error(f"Could not register this filing: {exc}")


@workflowRouter.post("/documents/{module_key}/{document_id}/status", summary="Move a filing through the review",
    response_model=ApiResponse[dict[str, Any]])
def documents_transition_router(module_key: str, document_id: str, request: TransitionRequest):
    try:
        return ok(workflowService.transition_document_service(
            module_key, document_id, request.status, request.user, request.comment))
    except (LookupError, ValueError) as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Transitioning a document failed")
        return server_error(f"Could not change the status of this filing: {exc}")


@workflowRouter.get("/audit", summary="The audit trail across every module",
    response_model=ApiResponse[list[dict[str, Any]]])
def audit_router(limit: int = Query(default=100, ge=1, le=500), module_key: str | None = None):
    try:
        return ok(workflowService.audit_log_service(limit, module_key))
    except Exception as exc:
        logging.exception("Reading the audit trail failed")
        return server_error(f"Could not read the audit trail: {exc}")


# --- drafts -------------------------------------------------------------------

@workflowRouter.get("/drafts/{module_key}", summary="Saved drafts of a module",
    response_model=ApiResponse[list[dict[str, Any]]])
def drafts_list_router(module_key: str):
    try:
        return ok(draftService.list_drafts_service(module_key))
    except Exception as exc:
        logging.exception("Listing the drafts of %s failed", module_key)
        return server_error(f"Could not list the drafts: {exc}")


@workflowRouter.post("/drafts/{module_key}", summary="Save the current state of a form",
    response_model=ApiResponse[dict[str, Any]])
def drafts_save_router(module_key: str, request: SaveDraftRequest):
    try:
        return ok(draftService.save_draft_service(module_key, request.name, request.data, request.user))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Saving a draft failed")
        return server_error(f"Could not save this draft: {exc}")


@workflowRouter.get("/drafts/{module_key}/{name}", summary="Load a saved draft",
    response_model=ApiResponse[dict[str, Any]])
def drafts_load_router(module_key: str, name: str):
    try:
        return ok(draftService.load_draft_service(module_key, name))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Loading a draft failed")
        return server_error(f"Could not load this draft: {exc}")


@workflowRouter.delete("/drafts/{module_key}/{name}", summary="Delete a saved draft",
    response_model=ApiResponse[dict[str, Any]])
def drafts_delete_router(module_key: str, name: str):
    try:
        draftService.delete_draft_service(module_key, name)
        return ok({"deleted": name})
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Deleting a draft failed")
        return server_error(f"Could not delete this draft: {exc}")
