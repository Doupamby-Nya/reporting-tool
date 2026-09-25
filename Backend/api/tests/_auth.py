"""Signed-in test clients.

Every protected route answers 401 without a session, so the suites talk to
the API as real accounts of a test organisation subscribed to all eight
modules. The organisation is given the configuration the reference outputs
were produced with — the default FATCA preparer, the PRIIPs settings and
logo — so the non-regression cases still compare like with like.
"""

from __future__ import annotations

import shutil
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database.db import engine
from database.tables import Organisation, OrganisationKind, Role, User
from domain.fatca import fatca_pipeline
from main import app
from services import authService
from utils.paths import RESOURCES_DIR, org_config_dir

PASSWORD = "test-password-long-enough"
PREPARER = "preparer@test.lu"
REVIEWER = "reviewer@test.lu"
ADMIN = "admin@test.lu"
TEST_ORG = "Test organisation"


def ensure_org(name: str = TEST_ORG, modules: tuple[str, ...] = authService.MODULE_KEYS,
               valid_until: date = date(2999, 12, 31)) -> int:
    with Session(engine) as db:
        organisation = db.exec(select(Organisation).where(Organisation.name == name)).first()
        if organisation is not None:
            return organisation.id
        organisation = authService.create_organisation(db, name, OrganisationKind.internal)
        for module in modules:
            authService.add_subscription(db, organisation.id, module, date(2000, 1, 1), valid_until)
        config = org_config_dir(organisation.id)
        config.mkdir(parents=True, exist_ok=True)
        shutil.copy(fatca_pipeline.PREPARERS_DEFAULT_FILE, config / "fatca_preparers.json")
        shutil.copy(RESOURCES_DIR / "config" / "app_settings.json", config / "app_settings.json")
        shutil.copy(RESOURCES_DIR / "config" / "logo.jpg", config / "logo.jpg")
        return organisation.id


def ensure_user(email: str, organisation_id: int, role: Role = Role.user,
                modules: tuple[str, ...] = authService.MODULE_KEYS) -> None:
    with Session(engine) as db:
        if db.exec(select(User).where(User.email == email)).first() is None:
            authService.create_user(db, organisation_id, email, email.split("@")[0], PASSWORD, role, list(modules))


def login_as(email: str = PREPARER, organisation_id: int | None = None, role: Role = Role.user,
             modules: tuple[str, ...] = authService.MODULE_KEYS) -> TestClient:
    """A client signed in as ``email`` — created when it does not exist yet,
    by default in the test organisation with every module."""
    ensure_user(email, organisation_id if organisation_id is not None else ensure_org(), role, modules)
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client
