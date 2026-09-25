"""Signing in and out, and who the browser is signed in as."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlmodel import Session

from database.db import get_session
from models.commonModel import ApiResponse, fail, ok
from routers.dependencies import COOKIE_SECURE, SESSION_COOKIE, current_user
from services import authService
from services.authService import CurrentUser

authRouter = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class ModuleGrant(BaseModel):
    key: str
    valid_until: date | None


class Me(BaseModel):
    email: str
    name: str
    role: str
    organisation: str
    modules: list[ModuleGrant]


def describe(user: CurrentUser) -> dict[str, Any]:
    return {
        "email": user.email, "name": user.name, "role": user.role.value,
        "organisation": user.organisation_name,
        "modules": [{"key": key, "valid_until": end} for key, end in user.modules.items()],
    }


@authRouter.post("/login", summary="Sign in with an email and a password", response_model=ApiResponse[Me])
def login_router(request: LoginRequest, response: Response, http: Request, db: Session = Depends(get_session)):
    try:
        token, user = authService.login(db, request.email, request.password)
    except PermissionError as exc:
        return fail(str(exc), status_code=401)
    # Nobody was signed in when the request arrived; the sign-in is theirs.
    http.state.user = user
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=COOKIE_SECURE,
                        max_age=authService.SESSION_HOURS * 3600, path="/")
    return ok(describe(user))


@authRouter.post("/logout", summary="Sign out", response_model=ApiResponse[dict[str, Any]])
def logout_router(request: Request, response: Response, db: Session = Depends(get_session)):
    authService.logout(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return ok({"signed_out": True})


@authRouter.get("/me", summary="The signed-in user and the modules they can use", response_model=ApiResponse[Me])
def me_router(user: CurrentUser = Depends(current_user)):
    return ok(describe(user))
