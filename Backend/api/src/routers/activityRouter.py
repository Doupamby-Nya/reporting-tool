"""Usage dashboards: each user's own activity, and an organisation's for its
administrators.

A user sees only themselves. An organisation administrator sees their own
organisation, user by user. A platform administrator sees any organisation,
or all of them together.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from database.db import get_session
from database.tables import Role, User
from models.commonModel import ApiResponse, ok
from routers.dependencies import current_user
from services import activityService
from services.authService import CurrentUser

activityRouter = APIRouter(prefix="/activity", tags=["Activity"])

ACTIONS = tuple(activityService.ACTIONS)


def _filters(
    year: int | None = Query(default=None, ge=2000, le=2100, description="A calendar year; the last 12 months when absent"),
    day: date | None = Query(default=None, description="Narrows everything under the calendar to one day"),
    module: str | None = Query(default=None, description="A module key, 'funds' or 'platform'"),
    action: str | None = Query(default=None, description=f"One of {', '.join(ACTIONS)}"),
    tz: str | None = Query(default=None, description="The viewer's IANA time zone, e.g. Europe/Luxembourg"),
) -> dict[str, Any]:
    return {"year": year, "day": day, "module": module or None,
            "action": action if action in ACTIONS else None, "tz_name": tz}


async def require_administrator(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if user.role not in (Role.platform_admin, Role.org_admin):
        raise HTTPException(status_code=403, detail="Organisation administrators only.")
    return user


@activityRouter.get("/me", summary="The signed-in user's own activity", response_model=ApiResponse[dict[str, Any]])
def my_activity_router(filters: dict[str, Any] = Depends(_filters), db: Session = Depends(get_session),
                       user: CurrentUser = Depends(current_user)):
    return ok(activityService.summary(db, organisation_id=user.organisation_id, user_id=user.id, **filters))


@activityRouter.get("/scopes", summary="The organisations and users an administrator may look at",
                    response_model=ApiResponse[list[dict[str, Any]]])
def scopes_router(db: Session = Depends(get_session), viewer: CurrentUser = Depends(require_administrator)):
    return ok(activityService.organisations_in_scope(db, viewer))


@activityRouter.get("/organisations", summary="An organisation's activity, user by user",
                    response_model=ApiResponse[dict[str, Any]])
def organisation_activity_router(
    organisation_id: int | None = Query(default=None, description="Every organisation when absent (platform administrators)"),
    user_id: int | None = Query(default=None, description="One user of that organisation"),
    filters: dict[str, Any] = Depends(_filters),
    db: Session = Depends(get_session),
    viewer: CurrentUser = Depends(require_administrator),
):
    # An organisation administrator is kept to their own organisation,
    # whatever the query asks for.
    if not viewer.is_platform_admin:
        if organisation_id not in (None, viewer.organisation_id):
            raise HTTPException(status_code=403, detail="You can only see your own organisation's activity.")
        organisation_id = viewer.organisation_id
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None or (organisation_id is not None and user.organisation_id != organisation_id):
            raise HTTPException(status_code=404, detail="No such user in this organisation.")
    return ok(activityService.summary(db, organisation_id=organisation_id, user_id=user_id,
                                      with_users=True, **filters))
