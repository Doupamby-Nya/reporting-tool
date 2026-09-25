"""Who may use which module.

A module is sold to an organisation (a Subscription, with its dates) and
opened to some of that organisation's users (ModuleAccess). A user reaches a
module when both hold — or when they are a platform administrator.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel, UniqueConstraint


class OrganisationKind(str, Enum):
    internal = "internal"
    external = "external"


class Role(str, Enum):
    platform_admin = "platform_admin"
    org_admin = "org_admin"
    user = "user"


class AuthMethod(str, Enum):
    local = "local"
    sso = "sso"


class Organisation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    kind: OrganisationKind = OrganisationKind.external
    email_domain: str | None = None
    sso_tenant_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Subscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    organisation_id: int = Field(foreign_key="organisation.id", index=True)
    module: str = Field(index=True)
    valid_from: date
    valid_until: date


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    organisation_id: int = Field(foreign_key="organisation.id", index=True)
    email: str = Field(unique=True, index=True)
    name: str
    auth_method: AuthMethod = AuthMethod.local
    password_hash: str | None = None
    role: Role = Role.user
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModuleAccess(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "module"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    module: str


class UserSession(SQLModel, table=True):
    """A signed-in browser. Only a hash of the cookie's token is kept, so a
    copy of the database does not hand out live sessions."""

    token_hash: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime


class ActivityEvent(SQLModel, table=True):
    """One thing a user did on the platform: a filing generated, a review
    decision, a workbook ingested, a draft saved, a text consulted.

    Written by the activity middleware after a request succeeds, so every
    module is covered without each route having to remember to log. The
    audit trail stays the record of *what happened to a filing*; this is
    the record of *who worked, where, and when* that the usage dashboards
    are drawn from.
    """

    id: int | None = Field(default=None, primary_key=True)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    organisation_id: int = Field(foreign_key="organisation.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    #: A module key, or "funds" / "platform" for what belongs to none.
    module: str = Field(index=True)
    #: One of activityService.ACTIONS.
    action: str = Field(index=True)
    #: What it was done to, where known: a filing, a draft, a report.
    subject: str | None = None
    method: str
    path: str
