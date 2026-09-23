# Migration from the Streamlit MVP

What moved here from `PRIIPS_KID_MVP_streamlit_v20260902`, how it was
verified, and what is left. The newest pass comes first.

# Fourth pass — proving parity

## When is the migration finished?

When the Streamlit tool can be archived without losing anything. That is
five checks, each of which can be run rather than argued:

| # | Criterion | How it is checked | Status |
|---|---|---|---|
| 1 | **Functional parity** — every Streamlit screen has its endpoint and its page | the eight chains in `config/navigation.ts` against `views/` | ✅ |
| 2 | **Same outputs** — the same input gives the same filing, byte for byte | `tests/test_non_regression.py` — 35 cases, all eight regimes | ✅ |
| 3 | **Tests carried over** — the Streamlit suite runs here | `test_bcl_engine.py`, `test_aifmd_engine.py` (80 tests), the AIFMD draft checks in `test_generation_api.py` | ✅ |
| 4 | **Structure** — one router and one Home page per reporting, typed routes, HTTP status codes | `routers/`, `pages/<reporting>/Home.tsx`, `/docs` | ✅ |
| 5 | **Runs from scratch** — a newcomer follows the READMEs on a clean machine | to be done by someone who has not worked on it | ⏳ |

The Streamlit `*_app.py` suites drove the Streamlit pages through
`streamlit.testing`; those pages no longer exist. Their data-level checks
were ported (criterion 3); their page-rendering checks have no equivalent
until the React client has tests of its own.

## Non-regression against Streamlit

`tests/non_regression/` holds 35 cases — a captured draft or a filled-in
workbook per regime, refusals included — and, for each, the output the
**Streamlit code itself** produced. `oracle.py` imports the MVP's own `core`
engines and its view helpers (with an inert `streamlit` module) to build
those references; the API suite then asks for the same case and requires the
same answer once production timestamps are masked (`normalize.py` masks
date-times and time-stamp tokens only, never a business date).

```
# the suite (does not need the Streamlit project)
cd Backend/api && poetry run pytest

# re-anchor the references — only for a deliberate change, said so in the commit
poetry run python tests/non_regression/oracle.py ../../../PRIIPS_KID_MVP_streamlit_v20260902
# rebuild the input workbooks (fictitious data)
poetry run python tests/non_regression/make_inputs.py
```

Run against the code as it stood before this pass, 13 of the 35 cases fail.
What they found:

- **U 1.1, O 4.1, ESEF, SAQ — no validation before generation.** The
  Streamlit views ran the engine's `validation_errors()` and refused to
  produce a filing that failed it; the API produced it anyway. It now
  answers `{"generated": false, "errors": [...]}`, as BCL and AIFMD do, and
  the generation page lists the reasons.
- **The same four — importing a workbook could not lead to a filing.** The
  parse endpoint returned the workbook's raw parts (`header`, `share_classes`,
  and for O 4.1 parts mislabelled `totals` / `assets` / `liabilities`), which
  the ingestion screen merged into the form as they were; `/generate` then
  failed on missing fields. The parse now returns the draft the Streamlit
  ingestion views built, which can be posted to `/generate` as it is.
- **U 1.1 — share-class dates crashed the XML** when they came as JSON text,
  and the share-class defaults were not applied.
- **File names** differed from the Streamlit ones (`U11_<CSSF code>_<YYYYMM>.xml`,
  `O41_<UCI>_<year>.edi`, ...). The Streamlit names are restored.
- **FATCA / CRS — a workbook whose tabs are not named exactly CPS /
  Individual / Active was not read.** The Streamlit tool matched the tabs by
  name (`CPS 2025`, `Individuals`...); the API used the raw sheets.
- **PRIIPs — the KID ignored the configured RTS calibration** and used the
  engine's built-in defaults, so it disagreed with the calculation step as
  soon as the calibration was edited. Two of the three KID templates
  (`theme_red`, `theme_dark_blue`) had not been copied over.

Two Streamlit defects were fixed on the way rather than reproduced: a blank
numeric cell in a U 1.1 share class crashed the generation (it now keeps its
default, with a test), and FATCA debug logging wrote the first rows of the
CPS tab — account holders' personal data — to the log.

## Structure

- **Routes are typed.** Every JSON route declares its `response_model`; the
  request bodies are Pydantic models (the U 1.1 / O 4.1 / ESEF / SAQ drafts
  are derived from each engine's submission dataclass; each of the six BCL
  reports has its own route). A malformed body is answered 422 in the usual
  `{success, message}` envelope. See `/docs`.
- **One Home page per reporting.** `pages/<reporting>/` holds that
  reporting's `Home.tsx` — the landing page of `/<reporting>` — and its own
  steps; the steps every reporting shares are in `pages/shared/`.
- **Duplicates removed.** `Reportable_Countries.xlsx` existed twice because
  the FATCA library read it from beside its own code (and defaulted to a path
  on the `8 - AI` share); it now reads `resources/reference/`. The unused
  `resources/config/priips_kid_template.*` are gone. `templates/standard.json`
  and `.yaml` are not duplicates: a template is editable in either format and
  saving writes both.
- **The tests no longer write into `runtime/`.** `tests/conftest.py` points
  `RUNTIME_DIR` at a temporary directory; until now every run added
  `TEST_LIFECYCLE.xml` / `TEST_FOUR_EYES.xml` entries to the local audit trail.

## Left to do

- Criterion 5: a clean-machine run of the READMEs by someone new to the code.
- Set `RUNTIME_DIR` outside the checkout on any shared machine (see
  `Backend/api/.env.example`), and purge the test entries the old suite left
  in the local `runtime/audit_log.json` and `doc_store.json`.
- The KID templates, the RTS calibration and the preparers are still written
  into `src/resources/` when edited from the configuration screens — as in
  Streamlit. On a deployed service they belong under `RUNTIME_DIR`.
- The React client has no tests of its own.

---

# Third pass — the capture screens

## The blocking defect: empty dropdowns

Every picker on the S 2.20 and TPTOBS forms rendered a single "—" and
nothing else, which made both reports impossible to file: a mandatory code
that cannot be chosen is not a cosmetic problem.

The cause was a wrong assumption about the API. Most code lists are served
as a mapping of code to label; a few are a plain list; the helper accepted
only arrays and returned nothing for the rest. Thirteen of the fourteen
lists were therefore empty.

`toOptions()` in `pages/bcl/forms/fields.tsx` now accepts all three shapes,
once, rather than each call site guessing. Verified by compiling that module
and running it against the live API:

```
 21 sectors                              11000 => "11000 — Central government"
  5 maturities                           I000-01A => "I000-01A — Up to 1 year"
  5 hold_security_types                  01 => "01 — Securities held and not affected…"
  …
PASS: every code list produces options
```

## Getting the data in

The Streamlit original had two modes per module — fill the form, or bring a
file. Only the form had been migrated. `components/IngestionPanel.tsx` is
now the same bar on all eight ingestion screens, offering whatever that
regime genuinely supports:

| Module | Entry points |
|---|---|
| PRIIPs KID | Excel template · import a filled file · demo dataset · empty the registry |
| FATCA & CRS | data report template · import a filled workbook (classified on the way in) |
| U 1.1 · O 4.1 · ESEF · SAQ | blank workbook · import a filled workbook · saved drafts |
| AIFMD Annex IV | ESMA consolidated template · **import a filled template** · open an existing XML filing |
| BCL | chart of accounts · instructions · verification rules · **open an existing XML filing** |

Two of these were missing entirely rather than merely unstyled:

- **AIFMD** had `/aifmd/template/parse` on the API and no way to reach it.
  A filled consolidated template now populates `aifm_info` and `aif_info`
  directly, with the parser's own problem list shown, and the reporting
  period preserved because the workbook does not carry it.
- **BCL** had no way back in at all. It is XML-direct rather than an Excel
  round-trip — that is how the regulator works, and the Streamlit original
  said so — so the entry points are the three official reference documents
  and an existing filing, identified and schema-validated on the spot, with
  the chain switching to whichever of the six it turns out to be.

## AI ingestion

A deliberate placeholder, present on all eight screens. It is inert and says
so when pressed, rather than being hidden: the workflow it belongs to — drop
in whatever the client sent, have it read and mapped onto the template, then
review every mapped field before filing — is the one these screens are
designed around, and it should be visible where it will sit. It never
silently does nothing.
