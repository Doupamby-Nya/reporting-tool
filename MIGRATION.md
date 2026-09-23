
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

`toOptions()` in `pages/steps/bcl/fields.tsx` now accepts all three shapes,
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
