"""Creates accounts from the command line, from Backend/api/src.

    poetry run python seed.py admin --email you@forvismazars.com --name "Your Name" --password "..."
    poetry run python seed.py demo --password "..."
    poetry run python seed.py demo-activity [--reset]
    poetry run python seed.py user --email ... --name "..." --password "..." --modules bcl,fatca [--organisation "..."]

``admin`` creates a platform administrator, in the internal organisation
"Forvis Mazars" (created if needed). ``demo`` builds a demonstration set:
three organisations with different subscriptions, one of them expired, and
a user for each situation. Both are idempotent: what exists is left alone.
Every demo account gets the one password given, so keep it to demo databases.

``user`` adds one account to an existing organisation ("Forvis Mazars" by
default) with the modules given, so a colleague can work against the same
API and data — e.g. a second person to test the four-eyes review.

``demo-activity`` gives the demo accounts a plausible year of activity, so
the usage dashboards have something to show at a presentation: busier around
the reporting deadlines, quiet at weekends. Those events are marked as demo
(path "demo") and ``--reset`` removes them, and only them.
"""

from __future__ import annotations

import argparse
import random
import shutil
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session, select

from database.db import engine, init_db
from database.tables import ActivityEvent, Organisation, OrganisationKind, Role, Subscription, User
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


def create_user(email: str, name: str, password: str, modules: list[str], organisation_name: str) -> None:
    with Session(engine) as db:
        organisation = db.exec(select(Organisation).where(Organisation.name == organisation_name)).first()
        if organisation is None:
            known = ", ".join(o.name for o in db.exec(select(Organisation)).all()) or "none"
            raise SystemExit(f"No organisation named '{organisation_name}'. Known: {known}.")
        print(f"{email}: {_user(db, email, name, organisation.id, password, Role.user, modules)}"
              f" in {organisation.name}, modules {', '.join(modules) or 'none'}")


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


#: What a working day is made of, weighted: most of it is controls and drafts.
_DEMO_MIX = [("validated", 30), ("drafted", 18), ("ingested", 14), ("consulted", 12), ("generated", 10),
             ("reviewed", 7), ("downloaded", 6), ("configured", 2)]

#: Filing names per module, for the timeline to show real-looking subjects.
_DEMO_SUBJECTS = {
    "bcl": ["S0103_{d}_001.xml", "S0404_{d}_001.xml", "TPTOBS_{d}_001.xml", "S0220_{d}_001.xml"],
    "fatca": ["FATCA_{d}.xml", "CRS_{d}.xml"],
    "urr": ["U11_{d}.xml"], "o41": ["O41_{d}.edi"], "esef": ["ESEF_{d}.zip"],
    "aifmd": ["AIFM_{d}.xml", "AIF_{d}.xml"], "saq": ["SAQ_{d}.xml"], "priips": ["KID_{d}.pdf"],
}


def create_demo_activity(reset: bool) -> None:
    with Session(engine) as db:
        for event in db.exec(select(ActivityEvent).where(ActivityEvent.path == "demo")).all():
            db.delete(event)
        db.commit()
        if reset:
            print("Demo activity removed.")
            return

        today = date.today()
        written = 0
        for email, _name, _organisation, _role, _modules in DEMO_USERS:
            user = db.exec(select(User).where(User.email == email)).first()
            modules = sorted(authService.modules_for(db, user)) if user else []
            if not modules:
                continue
            chance = random.Random(email)
            appetite = chance.uniform(0.55, 0.9)  # how often this person works on a weekday
            for offset in range(365, -1, -1):
                day = today - timedelta(days=offset)
                if day.weekday() >= 5 and chance.random() > 0.05:
                    continue
                # Reporting deadlines: the first ten days of a month, more so after a quarter.
                deadline = day.day <= 10
                quarter = deadline and day.month in (1, 4, 7, 10)
                if chance.random() > appetite * (1.3 if deadline else 0.8):
                    continue
                count = int(chance.expovariate(1 / (7 if quarter else 4 if deadline else 2))) + 1
                for _ in range(min(count, 24)):
                    module = chance.choice(modules)
                    action = chance.choices([a for a, _ in _DEMO_MIX], [w for _, w in _DEMO_MIX])[0]
                    subject = None
                    if action in ("generated", "reviewed", "drafted"):
                        stamp = day.strftime("%Y%m%d")
                        subject = chance.choice(_DEMO_SUBJECTS[module]).format(d=stamp)
                        if action == "reviewed":
                            subject += " · " + chance.choice(["Under review", "Approved", "Approved", "Rejected"])
                    moment = datetime.combine(day, time(chance.randint(7, 18), chance.randint(0, 59)), UTC)
                    db.add(ActivityEvent(occurred_at=moment, organisation_id=user.organisation_id,
                                         user_id=user.id, module=module, action=action, subject=subject,
                                         method="DEMO", path="demo"))
                    written += 1
        db.commit()
        print(f"{written} demo activity events written. Remove them with: seed.py demo-activity --reset")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("admin", help="create a platform administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--password", required=True)
    demo = commands.add_parser("demo", help="create the demonstration organisations and accounts")
    demo.add_argument("--password", required=True, help="given to every demo account (12 characters or more)")
    user = commands.add_parser("user", help="add an account to an existing organisation")
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--password", required=True, help="12 characters or more")
    user.add_argument("--modules", default="", help="comma-separated module keys, e.g. bcl,fatca")
    user.add_argument("--organisation", default=INTERNAL)
    activity = commands.add_parser("demo-activity", help="give the demo accounts a year of activity")
    activity.add_argument("--reset", action="store_true", help="remove the demo activity instead")
    args = parser.parse_args()

    init_db()
    if args.command == "admin":
        create_admin(args.email, args.name, args.password)
    elif args.command == "user":
        modules = [key.strip() for key in args.modules.split(",") if key.strip()]
        create_user(args.email, args.name, args.password, modules, args.organisation)
    elif args.command == "demo-activity":
        create_demo_activity(args.reset)
    else:
        create_demo(args.password)


if __name__ == "__main__":
    main()
