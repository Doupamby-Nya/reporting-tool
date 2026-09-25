"""Creates accounts from the command line, from Backend/api/src.

    poetry run python seed.py admin --email you@forvismazars.com --name "Your Name" --password "..."
    poetry run python seed.py demo --password "..."

``admin`` creates a platform administrator, in the internal organisation
"Forvis Mazars" (created if needed). ``demo`` builds a demonstration set:
three organisations with different subscriptions, one of them expired, and
a user for each situation. Both are idempotent: what exists is left alone.
Every demo account gets the one password given, so keep it to demo databases.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta

from sqlmodel import Session, select

from database.db import engine, init_db
from database.tables import Organisation, OrganisationKind, Role, Subscription, User
from domain.fatca import fatca_pipeline
from services import authService
from utils.paths import RESOURCES_DIR, org_config_dir

INTERNAL = "Forvis Mazars"

TODAY = date.today()
IN_A_YEAR = TODAY + timedelta(days=365)

# name, kind, email domain, {module: (valid_from, valid_until)}
DEMO_ORGANISATIONS = [
    (INTERNAL, OrganisationKind.internal, "forvismazars.com",
     {key: (TODAY, IN_A_YEAR) for key in authService.MODULE_KEYS}),
    ("Forvis Mazars - Audit (demo)", OrganisationKind.internal, None,
     {"priips": (TODAY, IN_A_YEAR), "esef": (TODAY, IN_A_YEAR)}),
    ("Demo ManCo S.A.", OrganisationKind.external, "demo-manco.example",
     {"bcl": (TODAY, IN_A_YEAR), "urr": (TODAY, IN_A_YEAR), "fatca": (TODAY, IN_A_YEAR),
      "aifmd": (TODAY - timedelta(days=400), TODAY - timedelta(days=35))}),
]

# email, name, organisation, role, modules
DEMO_USERS = [
    ("admin@demo.example", "Platform Admin", INTERNAL, Role.platform_admin, []),
    ("preparer@demo.example", "Regulatory Preparer", INTERNAL, Role.user, list(authService.MODULE_KEYS)),
    ("reviewer@demo.example", "Regulatory Reviewer", INTERNAL, Role.user, list(authService.MODULE_KEYS)),
    ("auditor@demo.example", "Audit Department", "Forvis Mazars - Audit (demo)", Role.user, ["priips", "esef"]),
    ("manco-admin@demo-manco.example", "ManCo Admin", "Demo ManCo S.A.", Role.org_admin, []),
    ("manco-bcl@demo-manco.example", "ManCo BCL Preparer", "Demo ManCo S.A.", Role.user, ["bcl"]),
    ("visitor@demo.example", "No Subscription", "Forvis Mazars - Audit (demo)", Role.user, []),
]


def _organisation(db: Session, name: str, kind: OrganisationKind, domain: str | None) -> Organisation:
    existing = db.exec(select(Organisation).where(Organisation.name == name)).first()
    return existing or authService.create_organisation(db, name, kind, domain)


def _seed_internal_configuration(organisation_id: int) -> None:
    """The internal organisation starts with the configuration the platform
    shipped with: the default FATCA preparer, the PRIIPs settings and logo,
    the client records."""
    config = org_config_dir(organisation_id)
    config.mkdir(parents=True, exist_ok=True)
    copies = [
        (fatca_pipeline.PREPARERS_DEFAULT_FILE, config / "fatca_preparers.json"),
        (RESOURCES_DIR / "config" / "app_settings.json", config / "app_settings.json"),
        (RESOURCES_DIR / "config" / "logo.jpg", config / "logo.jpg"),
    ]
    for source, target in copies:
        if source.exists() and not target.exists():
            shutil.copy(source, target)
    clients = RESOURCES_DIR / "clients_info"
    if clients.exists() and not (config / "clients_info").exists():
        shutil.copytree(clients, config / "clients_info")


def _user(db: Session, email: str, name: str, organisation_id: int, password: str,
          role: Role, modules: list[str]) -> str:
    if db.exec(select(User).where(User.email == email)).first():
        return "exists"
    authService.create_user(db, organisation_id, email, name, password, role, modules)
    return "created"


def create_admin(email: str, name: str, password: str) -> None:
    with Session(engine) as db:
        organisation = _organisation(db, INTERNAL, OrganisationKind.internal, "forvismazars.com")
        _seed_internal_configuration(organisation.id)
        print(f"{email}: {_user(db, email, name, organisation.id, password, Role.platform_admin, [])}")


def create_demo(password: str) -> None:
    with Session(engine) as db:
        ids = {}
        for name, kind, domain, subscriptions in DEMO_ORGANISATIONS:
            organisation = _organisation(db, name, kind, domain)
            ids[name] = organisation.id
            if not db.exec(select(Subscription).where(Subscription.organisation_id == organisation.id)).first():
                for module, (start, end) in subscriptions.items():
                    authService.add_subscription(db, organisation.id, module, start, end)
        _seed_internal_configuration(ids[INTERNAL])

        print(f"{'account':<34} {'organisation':<30} {'role':<15} modules it can use")
        for email, name, organisation, role, modules in DEMO_USERS:
            _user(db, email, name, ids[organisation], password, role, modules)
            user = db.exec(select(User).where(User.email == email)).first()
            usable = ", ".join(sorted(authService.modules_for(db, user))) or "none (home page and guide only)"
            print(f"{email:<34} {organisation:<30} {role.value:<15} {usable}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("admin", help="create a platform administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password", required=True)
    demo = commands.add_parser("demo", help="create the demonstration organisations and accounts")
    demo.add_argument("--password", required=True, help="given to every demo account (12 characters or more)")
    args = parser.parse_args()

    init_db()
    if args.command == "admin":
        create_admin(args.email, args.name, args.password)
    else:
        create_demo(args.password)


if __name__ == "__main__":
    main()
