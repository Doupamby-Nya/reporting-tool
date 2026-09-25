"""The access checks every protected route declares.

They are ``async`` on purpose. ``current_user`` binds the request to the
user's organisation in a context variable (see ``utils.paths``); an async
dependency runs in the request's own task, so the binding is visible to the
route that follows, whereas a sync one would run in a worker thread and the
binding would be lost with it.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from database.db import engine
from services import authService
from services.authService import CurrentUser
from utils.paths import set_current_org

SESSION_COOKIE = "rr_session"
# Off for local http development; on behind https, where it belongs.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


async def current_user(request: Request) -> CurrentUser:
    with Session(engine) as db:
        user = authService.resolve_session(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    set_current_org(user.organisation_id)
    return user


def _refuse(module: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=f"Your account has no active access to the '{module}' module. "
               "Ask your administrator to open it for you.")


def require_module(module: str) -> Callable[..., Coroutine[Any, Any, CurrentUser]]:
    """For a router that belongs to one module."""

    async def check(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not user.can_use(module):
            raise _refuse(module)
        return user

    return check


async def require_module_param(module_key: str, user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """For a shared route that names its module in the path, e.g. /drafts/{module_key}."""
    if not user.can_use(module_key):
        raise _refuse(module_key)
    return user


async def require_platform_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform administrators only.")
    return user
