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

## Running both

```
# terminal 1
cd Backend/api/src && poetry run uvicorn main:app --reload --port 8001

# terminal 2
cd Frontend && npm run dev
```

The client then runs on :3000 against the API on :8001.
