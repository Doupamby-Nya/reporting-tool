# Regulatory reporting tool

Regulatory reporting for third-party management companies: PRIIPs KID,
FATCA/CRS, U 1.1, O 4.1, ESEF, AIFMD Annex IV, SAQ and the BCL statistical
reports.

Every filing is validated twice before it can be downloaded — against the
regulator's own business rules, then against its XML schema — and stays
under four-eyes review until it is published.

- `Backend/api` — the FastAPI service. See its README for setup and layout.
- `Frontend` — the React client. See its README.
- `MIGRATION.md` — what moved here from the Streamlit MVP, what was verified,
  and what is left.

## Prerequisites

- Python 3.14 (`requires-python >=3.14` in `Backend/api/pyproject.toml`)
- Node.js 20 or later
- Poetry (installed in the API's virtual environment, see `Backend/api/README.md`)

## Running both

```
# terminal 1 - once only, create the accounts (see "Access" below)
cd Backend/api/src && poetry run python seed.py demo --password "choose-a-long-one"
cd Backend/api/src && poetry run uvicorn main:app --reload --port 8001

# terminal 2 — once only, create Frontend/.env with:
#   VITE_BACKEND_URL=http://localhost:8001/api/v1
cd Frontend && npm install && npm run dev
```

The client then runs on http://localhost:4000 against the API on :8001.
Without `Frontend/.env` the client calls `http://localhost:8000` without the
`/api/v1` prefix and every request fails.

## Access

Modules are sold per organisation. A user sees a module's tab - and the API
answers its routes - only when their organisation holds a subscription
covering today **and** the user is assigned that module (an organisation
administrator gets every module the organisation pays for; a platform
administrator gets all of them). Payment happens outside the platform: an
administrator records the subscription.

A visitor, or an account without any module, sees the home page and the user
guide only. Each organisation's drafts, filings, audit trail, fund registry
and settings are kept apart (`RUNTIME_DIR/orgs/<id>/`).

Accounts are created with `Backend/api/src/seed.py` (`admin` for a platform
administrator, `demo` for a demonstration set) or through the `/admin`
endpoints of the API (see `/docs`). Sign-in is by email and password;
Microsoft sign-in is planned.
