"""Routes for the document lifecycle, the audit trail and saved drafts.

The acting user is always the signed-in account, never a name sent in the
body: that is what makes the four-eyes check and the audit trail mean
something. A route naming a module in its path is refused unless the user can
use that module.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from models.commonModel import ApiResponse, fail, not_found, ok, server_error
from routers.dependencies import current_user, require_module_param
from services import draftService, workflowService
from services.authService import CurrentUser

workflowRouter = APIRouter(tags=["Workflow"])


class RecordGeneratedRequest(BaseModel):
    document_id: str = Field(description="The file name the filing was produced under")
    label: str = ""


class TransitionRequest(BaseModel):
    status: str = Field(description=f"One of: {', '.join(workflowService.STATUSES)}")
    comment: str = ""


class SaveDraftRequest(BaseModel):
    name: str
    data: dict[str, Any] = {}


# --- documents ---------------------------------------------------------------

@workflowRouter.get("/documents/{module_key}", summary="Every filing generated for a module",
    response_model=ApiResponse[dict[str, Any]])
def documents_list_router(module_key: str, _: CurrentUser = Depends(require_module_param)):
    try:
        return ok(workflowService.list_documents_service(module_key))
    except Exception as exc:
        logging.exception("Listing the documents of %s failed", module_key)
        return server_error(f"Could not list the documents: {exc}")


@workflowRouter.post("/documents/{module_key}", summary="Register a generated filing",
    response_model=ApiResponse[dict[str, Any]])
def documents_record_router(module_key: str, request: RecordGeneratedRequest, http: Request,
                            user: CurrentUser = Depends(require_module_param)):
    http.state.activity_subject = request.document_id
    try:
        return ok(workflowService.record_generated_service(
            module_key, request.document_id, request.label, user.email))
    except Exception as exc:
        logging.exception("Recording a generated document failed")
        return server_error(f"Could not register this filing: {exc}")


@workflowRouter.post("/documents/{module_key}/{document_id}/status", summary="Move a filing through the review",
    response_model=ApiResponse[dict[str, Any]])
def documents_transition_router(module_key: str, document_id: str, request: TransitionRequest, http: Request,
                                user: CurrentUser = Depends(require_module_param)):
    # The decision is what a reviewer's timeline shows, beside the filing.
    http.state.activity_subject = f"{document_id} · {request.status}"
    try:
        return ok(workflowService.transition_document_service(
            module_key, document_id, request.status, user.email, request.comment))
    except (LookupError, ValueError) as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Transitioning a document failed")
        return server_error(f"Could not change the status of this filing: {exc}")


@workflowRouter.get("/audit", summary="The audit trail across every module",
    response_model=ApiResponse[list[dict[str, Any]]])
def audit_router(limit: int = Query(default=100, ge=1, le=500), module_key: str | None = None,
                 user: CurrentUser = Depends(current_user)):
    try:
        visible = None if user.is_platform_admin else set(user.modules)
        return ok(workflowService.audit_log_service(limit, module_key, visible))
    except Exception as exc:
        logging.exception("Reading the audit trail failed")
        return server_error(f"Could not read the audit trail: {exc}")


# --- drafts -------------------------------------------------------------------

@workflowRouter.get("/drafts/{module_key}", summary="Saved drafts of a module",
    response_model=ApiResponse[list[dict[str, Any]]])
def drafts_list_router(module_key: str, _: CurrentUser = Depends(require_module_param)):
    try:
        return ok(draftService.list_drafts_service(module_key))
    except Exception as exc:
        logging.exception("Listing the drafts of %s failed", module_key)
        return server_error(f"Could not list the drafts: {exc}")


@workflowRouter.post("/drafts/{module_key}", summary="Save the current state of a form",
    response_model=ApiResponse[dict[str, Any]])
def drafts_save_router(module_key: str, request: SaveDraftRequest, http: Request,
                       user: CurrentUser = Depends(require_module_param)):
    http.state.activity_subject = request.name
    try:
        return ok(draftService.save_draft_service(module_key, request.name, request.data, user.email))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:
        logging.exception("Saving a draft failed")
        return server_error(f"Could not save this draft: {exc}")


@workflowRouter.get("/drafts/{module_key}/{name}", summary="Load a saved draft",
    response_model=ApiResponse[dict[str, Any]])
def drafts_load_router(module_key: str, name: str, _: CurrentUser = Depends(require_module_param)):
    try:
        return ok(draftService.load_draft_service(module_key, name))
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Loading a draft failed")
        return server_error(f"Could not load this draft: {exc}")


@workflowRouter.delete("/drafts/{module_key}/{name}", summary="Delete a saved draft",
    response_model=ApiResponse[dict[str, Any]])
def drafts_delete_router(module_key: str, name: str, user: CurrentUser = Depends(require_module_param)):
    try:
        draftService.delete_draft_service(module_key, name)
        workflowService.log_audit_service(f"{module_key.upper()} draft deleted", name, user.email)
        return ok({"deleted": name})
    except LookupError as exc:
        return not_found(str(exc))
    except Exception as exc:
        logging.exception("Deleting a draft failed")
        return server_error(f"Could not delete this draft: {exc}")
