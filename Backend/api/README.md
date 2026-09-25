# Regulatory reporting API

FastAPI service behind the regulatory reporting platform for third-party
management companies. One endpoint family per regime — PRIIPs KID,
FATCA/CRS, U 1.1, O 4.1, ESEF, AIFMD Annex IV, SAQ and the BCL statistical
reports — each validating a filing against the regulator's own rules and XML
schema before returning it.

## Setup (first usage)

Requires Python 3.14 (`python --version`; on Windows `py -3.14` selects it
when several versions are installed).

```
# 1 create the virtual environment, from /Backend
python.exe -m venv env

# 2 activate it
env/Scripts/activate

# 3 install the dependencies, from /Backend/api
pip install poetry
poetry install

# 4 run the API, from /Backend/api/src
poetry run uvicorn main:app --reload
# By default the API runs on port 8000. If 8000 is busy:
poetry run uvicorn main:app --reload --port 8001
```

The interactive documentation is at `/docs`, the schema at `/openapi.json`.

Every route except the module catalogue and signing in needs an account.
Create one before the first run, from /Backend/api/src:

```
# a platform administrator (sees every module and the /admin endpoints)
poetry run python seed.py admin --email you@forvismazars.com --name "Your Name" --password "at least 12 characters"

# or a demonstration set: three organisations, one expired subscription,
# one account per situation, all with the password given
poetry run python seed.py demo --password "at least 12 characters"
```

Copy `.env.example` to `.env` and check `CORS_ORIGINS`: it must list the
client's origin (`http://localhost:4000` in development), or the browser
refuses every call.

To install a new dependency: `poetry add <name>`.

## Tests

```
# from /Backend/api
poetry run pytest
```

The suite drives the HTTP layer, so it covers the routers, the services and
the reporting engines together: a filing only passes here if it would also
pass the regulator's own schema. It runs against a throwaway `RUNTIME_DIR`
(see `tests/conftest.py`), never against your local drafts and audit trail.

| File | What it proves |
|---|---|
| `test_api.py` | the endpoints answer, refuse and fail as documented |
| `test_generation_api.py` | the generation endpoints, the fund registry, the KID, the 422 envelope |
| `test_non_regression.py` | every regime files what the Streamlit MVP filed for the same input |
| `test_bcl_engine.py`, `test_aifmd_engine.py` | the engines themselves — the Streamlit suite, carried over |
| `test_access.py` | who reaches which module (all eight: signed out, unsubscribed, expired, unassigned) and that organisations never see each other's data |

The API suites talk to the API as real accounts (`tests/_auth.py`): a test
organisation subscribed to every module, with a preparer and a reviewer.

`tests/non_regression/` explains how its references were built from the
Streamlit code and how to re-anchor them; see also `MIGRATION.md`.

## Layout

```
src/
  main.py           the app, and the /api/v1 parent router
  routers/          one router per regime, plus auth and admin; dependencies.py holds the access checks
  services/         orchestration: request in, validated filing out
  models/           the Pydantic request and response shapes
  domain/           the reporting engines, one package per regime
  database/         the account database (db.py, tables.py) and the JSON store of each organisation's files
  seed.py           creates the first administrator, or a demonstration set of accounts
  middlewares/      CORS
  utils/            filesystem locations
  resources/        what the regulators publish: XSD schemas, instructions,
                    verification rules, chart-of-accounts workbooks
tests/              the test suites; non_regression/ holds the Streamlit parity cases
```

`domain/` is where the regulatory knowledge lives, and it is deliberately
free of any web concern: no FastAPI, no Pydantic, no request object. A
service translates the wire format into what an engine expects and back
again. That is what lets the engines be tested directly, and what kept the
migration from Streamlit a move rather than a rewrite.

### Where a filing is checked

Two gates, in this order, and both must pass before a document is returned:

1. **The regulator's business rules** — BCL's compendiums of verification
   rules, the CSSF AIFM Reporting Technical Guidance. Each finding carries
   that regulator's own control code (`LED-015`, `CAF-057`, `CSSF-046`, …)
   so a preparer can look the rule up.
2. **The regulator's XML schema** — the real XSDs, bundled under
   `domain/<regime>/schemas/`. A failure here is a defect of this service
   rather than of the data, and is reported as such.

Checks that need a regulator's own register — whether an entity exists,
whether the sender is linked to it, whether a file name has already been
used — cannot be reproduced locally and are documented as out of scope.

## Accounts and access

`database/` holds the account database (SQLModel: SQLite by default,
`DATABASE_URL` for PostgreSQL): organisations, their subscriptions per
module, users, the modules each user is assigned, and sessions.

- **Sign in**: `POST /auth/login` sets an `httpOnly` session cookie
  (`rr_session`); only a hash of its token is stored. `GET /auth/me` returns
  the user and the modules they can use; `POST /auth/logout` ends it.
- **Access rule** (`services/authService.py`): a platform administrator
  uses every module; anyone else needs an active subscription of their
  organisation, and either the org-administrator role or an assignment to
  the module.
- **Enforcement** (`routers/dependencies.py`): each module's router is
  mounted behind `require_module(<key>)` in `main.py`; shared routes that
  name a module in their path (drafts, documents, regulatory library) check
  it with `require_module_param`. Refusals are 401 (not signed in) and 403
  (no access), in the usual envelope.
- **Identity**: the acting user of a generation, a review step or a
  deletion is the signed-in account, never a name sent in the body, so the
  four-eyes check compares two authenticated accounts.
- **Administration**: `/admin/*` (platform administrators) manages
  organisations, subscriptions, users, module assignment, and disabling an
  account (which ends its sessions). Every change is written to the
  organisation's audit trail.
- **Shared configuration**: the KID templates and the RTS calibration are
  common to every organisation, so only a platform administrator may change
  them. The PRIIPs settings and logo, the FATCA preparers and the client
  records are each organisation's own.

## Runtime state

Everything the API writes is under `Backend/api/runtime/`: the account
database (`platform.db`) and, per organisation, `orgs/<id>/` (drafts, the
document store, the audit trail, the fund registry and `config/`). Set
`RUNTIME_DIR` to move it, for instance onto a mounted volume. Files left at
the root of `runtime/` by earlier versions (before organisations existed)
are no longer read. The store is a JSON file with atomic writes, which suits a
single worker; put a database behind `database/jsonStore.py` before running
several workers against the same volume.
