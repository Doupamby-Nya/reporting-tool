"""Accounts, sessions and the rule deciding who reaches which module.

access(user, module) = platform admin
                       OR (the organisation holds a subscription covering today
                           AND (the user is an org admin OR is assigned the module))
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, select

from database.tables import (
    AuthMethod, ModuleAccess, Organisation, OrganisationKind, Role, Subscription, User, UserSession,
)
from services.referenceService import MODULES

MODULE_KEYS: tuple[str, ...] = tuple(module["key"] for module in MODULES)
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))

_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}


@dataclass(frozen=True)
class CurrentUser:
    """The signed-in user, detached from the database session that loaded it."""

    id: int
    email: str
    name: str
    role: Role
    organisation_id: int
    organisation_name: str
    modules: dict[str, date | None] = field(default_factory=dict)

    @property
    def is_platform_admin(self) -> bool:
        return self.role == Role.platform_admin

    def can_use(self, module: str) -> bool:
        return module in self.modules


# --- passwords ----------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt, digest = stored.split("$")
    candidate = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), **_SCRYPT)
    return hmac.compare_digest(candidate, base64.b64decode(digest))


# Checked against when the email is unknown, so a wrong email and a wrong
# password take the same time to refuse.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def _normalise_email(email: str) -> str:
    return email.strip().casefold()


def _validate_modules(modules: list[str]) -> list[str]:
    unknown = sorted(set(modules) - set(MODULE_KEYS))
    if unknown:
        raise ValueError(f"Unknown module(s): {', '.join(unknown)}. Known: {', '.join(MODULE_KEYS)}.")
    return sorted(set(modules))


# --- access -------------------------------------------------------------------

def active_subscriptions(db: Session, organisation_id: int, today: date | None = None) -> dict[str, date]:
    """Module → the latest end date among the subscriptions covering today."""
    today = today or date.today()
    rows = db.exec(select(Subscription).where(
        Subscription.organisation_id == organisation_id,
        Subscription.valid_from <= today, Subscription.valid_until >= today)).all()
    ends: dict[str, date] = {}
    for row in rows:
        ends[row.module] = max(ends.get(row.module, row.valid_until), row.valid_until)
    return ends


def modules_for(db: Session, user: User, today: date | None = None) -> dict[str, date | None]:
    if user.role == Role.platform_admin:
        return {key: None for key in MODULE_KEYS}
    subscribed = active_subscriptions(db, user.organisation_id, today)
    if user.role == Role.org_admin:
        return dict(subscribed)
    assigned = set(db.exec(select(ModuleAccess.module).where(ModuleAccess.user_id == user.id)).all())
    return {key: end for key, end in subscribed.items() if key in assigned}


def _snapshot(db: Session, user: User) -> CurrentUser:
    organisation = db.get(Organisation, user.organisation_id)
    return CurrentUser(
        id=user.id, email=user.email, name=user.name, role=user.role,
        organisation_id=user.organisation_id, organisation_name=organisation.name if organisation else "",
        modules=modules_for(db, user))


# --- sessions -----------------------------------------------------------------

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(db: Session, email: str, password: str) -> tuple[str, CurrentUser]:
    """A new session token for valid local credentials. The refusal never says
    which of the two was wrong."""
    user = db.exec(select(User).where(User.email == _normalise_email(email))).first()
    if user is None or user.auth_method != AuthMethod.local:
        verify_password(password, _DUMMY_HASH)
        raise PermissionError("Unknown email or wrong password.")
    if not verify_password(password, user.password_hash) or not user.active:
        raise PermissionError("Unknown email or wrong password.")
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=_token_hash(token), user_id=user.id,
                       expires_at=datetime.now(UTC) + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return token, _snapshot(db, user)


def resolve_session(db: Session, token: str | None) -> CurrentUser | None:
    if not token:
        return None
    row = db.get(UserSession, _token_hash(token))
    if row is None:
        return None
    if row.expires_at < datetime.now(UTC):
        db.delete(row)
        db.commit()
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        return None
    return _snapshot(db, user)


def logout(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.get(UserSession, _token_hash(token))
    if row is not None:
        db.delete(row)
        db.commit()


# --- administration -----------------------------------------------------------

def create_organisation(db: Session, name: str, kind: OrganisationKind,
                        email_domain: str | None = None) -> Organisation:
    if db.exec(select(Organisation).where(Organisation.name == name.strip())).first():
        raise ValueError(f"An organisation named '{name}' already exists.")
    organisation = Organisation(name=name.strip(), kind=kind,
                                email_domain=_normalise_email(email_domain) if email_domain else None)
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


def add_subscription(db: Session, organisation_id: int, module: str,
                     valid_from: date, valid_until: date) -> Subscription:
    _validate_modules([module])
    if db.get(Organisation, organisation_id) is None:
        raise LookupError(f"No organisation with id {organisation_id}.")
    if valid_until < valid_from:
        raise ValueError("A subscription cannot end before it starts.")
    subscription = Subscription(organisation_id=organisation_id, module=module,
                                valid_from=valid_from, valid_until=valid_until)
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def create_user(db: Session, organisation_id: int, email: str, name: str, password: str,
                role: Role = Role.user, modules: list[str] | None = None) -> User:
    if db.get(Organisation, organisation_id) is None:
        raise LookupError(f"No organisation with id {organisation_id}.")
    email = _normalise_email(email)
    if db.exec(select(User).where(User.email == email)).first():
        raise ValueError(f"A user with the email '{email}' already exists.")
    if len(password) < 12:
        raise ValueError("A password must be at least 12 characters long.")
    user = User(organisation_id=organisation_id, email=email, name=name.strip(),
                auth_method=AuthMethod.local, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    set_user_modules(db, user.id, modules or [])
    return user


def set_user_modules(db: Session, user_id: int, modules: list[str]) -> list[str]:
    modules = _validate_modules(modules)
    if db.get(User, user_id) is None:
        raise LookupError(f"No user with id {user_id}.")
    for row in db.exec(select(ModuleAccess).where(ModuleAccess.user_id == user_id)).all():
        db.delete(row)
    for module in modules:
        db.add(ModuleAccess(user_id=user_id, module=module))
    db.commit()
    return modules


def set_user_active(db: Session, user_id: int, active: bool) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise LookupError(f"No user with id {user_id}.")
    user.active = active
    db.add(user)
    if not active:
        for row in db.exec(select(UserSession).where(UserSession.user_id == user_id)).all():
            db.delete(row)
    db.commit()
    db.refresh(user)
    return user


def describe_organisations(db: Session) -> list[dict]:
    today = date.today()
    result = []
    for organisation in db.exec(select(Organisation).order_by(Organisation.name)).all():
        subscriptions = db.exec(select(Subscription).where(
            Subscription.organisation_id == organisation.id).order_by(Subscription.module)).all()
        result.append({
            "id": organisation.id, "name": organisation.name, "kind": organisation.kind,
            "email_domain": organisation.email_domain,
            "subscriptions": [{"id": s.id, "module": s.module, "valid_from": s.valid_from,
                               "valid_until": s.valid_until,
                               "active": s.valid_from <= today <= s.valid_until} for s in subscriptions],
        })
    return result


def describe_users(db: Session, organisation_id: int | None = None) -> list[dict]:
    query = select(User).order_by(User.email)
    if organisation_id is not None:
        query = query.where(User.organisation_id == organisation_id)
    result = []
    for user in db.exec(query).all():
        assigned = sorted(db.exec(select(ModuleAccess.module).where(ModuleAccess.user_id == user.id)).all())
        result.append({
            "id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "organisation_id": user.organisation_id, "auth_method": user.auth_method,
            "active": user.active, "assigned_modules": assigned,
            "usable_modules": sorted(modules_for(db, user)),
        })
    return result
