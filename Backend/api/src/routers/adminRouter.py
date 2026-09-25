"""Organisations, subscriptions and accounts — platform administrators only.

Payment happens outside the platform; recording a subscription here is what
opens a module to an organisation. Every change is written to the audit trail
of the organisation it concerns.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from database.db import get_session
from database.tables import OrganisationKind, Role
from models.commonModel import ApiResponse, fail, not_found, ok
from routers.dependencies import require_platform_admin
from services import authService, workflowService
from services.authService import CurrentUser

adminRouter = APIRouter(prefix="/admin", tags=["Administration"])


class OrganisationRequest(BaseModel):
    name: str
    kind: OrganisationKind = OrganisationKind.external
    email_domain: str | None = None


class SubscriptionRequest(BaseModel):
    organisation_id: int
    module: str
    valid_from: date
    valid_until: date


class UserRequest(BaseModel):
    organisation_id: int
    email: str
    name: str
    password: str = Field(min_length=12)
    role: Role = Role.user
    modules: list[str] = []


class ModulesRequest(BaseModel):
    modules: list[str]


class ActiveRequest(BaseModel):
    active: bool


@adminRouter.get("/organisations", summary="Every organisation and its subscriptions",
                 response_model=ApiResponse[list[dict[str, Any]]])
def organisations_router(db: Session = Depends(get_session), _: CurrentUser = Depends(require_platform_admin)):
    return ok(authService.describe_organisations(db))


@adminRouter.post("/organisations", summary="Create an organisation", response_model=ApiResponse[dict[str, Any]])
def create_organisation_router(request: OrganisationRequest, db: Session = Depends(get_session),
                               admin: CurrentUser = Depends(require_platform_admin)):
    try:
        organisation = authService.create_organisation(db, request.name, request.kind, request.email_domain)
    except ValueError as exc:
        return fail(str(exc))
    workflowService.log_audit_service("ADMIN organisation created", organisation.name, admin.email,
                                      organisation_id=organisation.id)
    return ok({"id": organisation.id, "name": organisation.name})


@adminRouter.post("/subscriptions", summary="Record a subscription: opens a module to an organisation",
                  response_model=ApiResponse[dict[str, Any]])
def create_subscription_router(request: SubscriptionRequest, db: Session = Depends(get_session),
                               admin: CurrentUser = Depends(require_platform_admin)):
    try:
        subscription = authService.add_subscription(
            db, request.organisation_id, request.module, request.valid_from, request.valid_until)
    except LookupError as exc:
        return not_found(str(exc))
    except ValueError as exc:
        return fail(str(exc))
    workflowService.log_audit_service(
        "ADMIN subscription recorded", request.module, admin.email,
        f"{request.valid_from} → {request.valid_until}", organisation_id=request.organisation_id)
    return ok({"id": subscription.id})


@adminRouter.get("/users", summary="Every account", response_model=ApiResponse[list[dict[str, Any]]])
def users_router(organisation_id: int | None = None, db: Session = Depends(get_session),
                 _: CurrentUser = Depends(require_platform_admin)):
    return ok(authService.describe_users(db, organisation_id))


@adminRouter.post("/users", summary="Create an account", response_model=ApiResponse[dict[str, Any]])
def create_user_router(request: UserRequest, db: Session = Depends(get_session),
                       admin: CurrentUser = Depends(require_platform_admin)):
    try:
        user = authService.create_user(db, request.organisation_id, request.email, request.name,
                                       request.password, request.role, request.modules)
    except LookupError as exc:
        return not_found(str(exc))
    except ValueError as exc:
        return fail(str(exc))
    workflowService.log_audit_service("ADMIN user created", user.email, admin.email,
                                      f"role {user.role.value}; modules {', '.join(request.modules) or 'none'}",
                                      organisation_id=user.organisation_id)
    return ok({"id": user.id, "email": user.email})


@adminRouter.put("/users/{user_id}/modules", summary="Choose which subscribed modules a user may use",
                 response_model=ApiResponse[dict[str, Any]])
def user_modules_router(user_id: int, request: ModulesRequest, db: Session = Depends(get_session),
                        admin: CurrentUser = Depends(require_platform_admin)):
    try:
        modules = authService.set_user_modules(db, user_id, request.modules)
    except LookupError as exc:
        return not_found(str(exc))
    except ValueError as exc:
        return fail(str(exc))
    target = next(u for u in authService.describe_users(db) if u["id"] == user_id)
    workflowService.log_audit_service("ADMIN modules assigned", target["email"], admin.email,
                                      ", ".join(modules) or "none", organisation_id=target["organisation_id"])
    return ok({"id": user_id, "modules": modules})


@adminRouter.put("/users/{user_id}/active", summary="Enable or disable an account",
                 response_model=ApiResponse[dict[str, Any]])
def user_active_router(user_id: int, request: ActiveRequest, db: Session = Depends(get_session),
                       admin: CurrentUser = Depends(require_platform_admin)):
    try:
        user = authService.set_user_active(db, user_id, request.active)
    except LookupError as exc:
        return not_found(str(exc))
    workflowService.log_audit_service("ADMIN user " + ("enabled" if user.active else "disabled"),
                                      user.email, admin.email, organisation_id=user.organisation_id)
    return ok({"id": user.id, "active": user.active})
