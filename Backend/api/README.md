# Regulatory reporting API

FastAPI service behind the regulatory reporting platform for third-party
management companies. One endpoint family per regime — PRIIPs KID,
FATCA/CRS, U 1.1, O 4.1, ESEF, AIFMD Annex IV, SAQ and the BCL statistical
reports — each validating a filing against the regulator's own rules and XML
schema before returning it.

## Setup (first usage)

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

`tests/non_regression/` explains how its references were built from the
Streamlit code and how to re-anchor them; see also `MIGRATION.md`.

## Layout

```
src/
  main.py           the app, and the /api/v1 parent router
  routers/          one router per regime; HTTP only, no business logic
  services/         orchestration: request in, validated filing out
  models/           the Pydantic request and response shapes
  domain/           the reporting engines, one package per regime
  database/         the JSON store the runtime state is kept in
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

## Runtime state

Saved drafts, the document store and the audit trail are written under
`Backend/api/runtime/`. Set `RUNTIME_DIR` to move them, for instance onto a
mounted volume. The store is a JSON file with atomic writes, which suits a
single worker; put a database behind `database/jsonStore.py` before running
several workers against the same volume.
