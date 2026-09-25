"""End-to-end tests of the regulatory reporting API.

Every test goes through the HTTP layer, so it covers the routers, the
services and the domain engines together — a filing is only accepted here if
it would also be accepted by the regulator's own schema.

    cd Backend/api
    poetry run pytest
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from _auth import PREPARER, REVIEWER, login_as  # noqa: E402

client = login_as(PREPARER)
reviewer = login_as(REVIEWER)

HEADER = {
    "end_month_date": "2025-12-31", "closing_date": "2025-12-31",
    "reporter_type": "23", "reporter_code": "789",
    "declarant_type": "26", "declarant_code": "001220003", "reporting_currency": "EUR",
}


def line(item: str, amount: float) -> dict:
    return {"item": item, "country": "XX", "currency": "XXX", "sector": "90000",
            "maturity": "I999-999", "amount": amount}


def ledger_body() -> dict:
    return {"header": HEADER,
            "assets": [line("1-003000", 1000), line("1-000000", 1000)],
            "liabilities": [line("2-004000", 1000), line("2-000000", 1000)],
            "creation_date": "2026-01-05"}


def result(response) -> dict:
    payload = response.json()
    assert payload["success"] is True, payload.get("message")
    return payload["result"]


def jsonable(value):
    """JSON has no date type; a client sends ISO strings."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


# =============================================================================
# Health and reference data
# =============================================================================

def test_healthcheck():
    assert client.get("/healthcheck").json() == {"status": "ok"}


def test_modules_are_listed():
    modules = result(client.get("/api/v1/reference/modules"))
    keys = {m["key"] for m in modules}
    assert {"priips", "fatca", "urr", "o41", "esef", "aifmd", "saq", "bcl"} <= keys


def test_regulatory_library_is_served():
    documents = result(client.get("/api/v1/reference/regulations/bcl"))
    assert documents and all(d["downloadable"] for d in documents)
    response = client.get("/api/v1/reference/regulations/bcl/0/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 10_000


def test_unknown_module_is_reported_not_crashed():
    payload = client.get("/api/v1/reference/regulations/nope").json()
    assert payload["success"] is False and "nope" in payload["message"]


# =============================================================================
# BCL — the six reports
# =============================================================================

def test_bcl_reports_and_codes_are_described():
    reports = result(client.get("/api/v1/bcl/reports"))["reports"]
    assert [r["key"] for r in reports] == ["s13", "s213", "s16", "s220", "s44", "tptobs"]
    codes = result(client.get("/api/v1/bcl/codes"))
    assert codes["sectors"]["32100"] == "Credit institutions"
    assert codes["schema_validation_available"] is True


@pytest.mark.parametrize("report_key,expected_prefix", [
    ("s13", "S0103_L4_202512_"), ("s213", "S0213_L2_202512_"), ("s16", "S0106_L2_202512_"),
])
def test_bcl_balance_sheets_generate_schema_valid_xml(report_key, expected_prefix):
    body = ledger_body() if report_key != "s16" else {
        "header": HEADER, "assets": [line("1-007000", 30)], "liabilities": [],
        "creation_date": "2026-01-05"}
    generated = result(client.post(f"/api/v1/bcl/{report_key}/generate", json=body))
    assert generated["generated"] is True
    produced = generated["files"][0]
    assert produced["schema_validation"]["valid"] is True
    assert produced["filename"].startswith(expected_prefix)
    assert produced["content"].startswith("<?xml")


def test_each_bcl_report_uses_its_own_root_element():
    """The S 2.13 regression: it used to be emitted in the S 1.3 namespace."""
    roots = {"s13": "<S13 ", "s213": "<S213 ", "s16": "<S16 "}
    for report_key, root in roots.items():
        body = ledger_body() if report_key != "s16" else {
            "header": HEADER, "assets": [line("1-007000", 30)], "liabilities": []}
        content = result(client.post(f"/api/v1/bcl/{report_key}/generate", json=body))["files"][0]["content"]
        assert root in content


def test_bcl_refuses_an_unbalanced_balance_sheet():
    body = ledger_body()
    body["liabilities"] = [line("2-004000", 1000), line("2-000000", 5)]
    generated = result(client.post("/api/v1/bcl/s13/generate", json=body))
    assert generated["generated"] is False
    assert "LED-015" in {e["code"] for e in generated["validation"]["errors"]}
    assert not generated["files"]


def test_bcl_s44_percentages_must_total_100():
    body = {"header": HEADER, "marketing_countries": [{"country": "LU", "amount": 60}]}
    generated = result(client.post("/api/v1/bcl/s44/generate", json=body))
    assert generated["generated"] is False
    assert "S44-010" in {e["code"] for e in generated["validation"]["errors"]}


def test_bcl_tptobs_derives_its_line_totals_from_the_securities():
    body = {"header": HEADER, "creation_date": "2026-01-05", "securities": [
        {"line_item": "1-003000", "code_type": "1", "isin": "USG9328DAH38", "hold_security_type": "01",
         "esa2010_type": "F.3", "quotation_type": "percent", "nominal_amount": 2_000_000,
         "nominal_currency": "USD", "reported_amount": 1_840_000},
    ]}
    generated = result(client.post("/api/v1/bcl/tptobs/generate", json=body))
    assert generated["generated"] is True
    content = generated["files"][0]["content"]
    assert generated["files"][0]["schema_validation"]["valid"] is True
    assert "<totalReportedAmount>1840000</totalReportedAmount>" in content


def test_bcl_s220_generates_schema_valid_xml():
    body = {
        "reference_month": "202512", "sender_type": "23", "sender_code": "341",
        "sender_employees": [{"name": "J Doe", "phone": "000", "email": "a@b.lu"}],
        "declarant_type": "42", "declarant_code": "66012345600001", "uci_name": "Fund - A",
        "valuation_date": "2025-12-31", "launch_date": "2021-01-04",
        "nav_freq": 13, "nav_redemption_freq": 4, "open_closed_end": 1,
        "nav_preceding_ref_month": 99_900, "nav_ref_month": 100_000,
        "units_issued": 0, "units_redeemed": 0, "total_distributions": 0,
        "share_classes": [{
            "cssf_code": "0001", "name": "CAP", "base_currency": "EUR", "launch_date": "2021-01-04",
            "investor_base": 3, "units_outstanding": 1000, "nav_per_unit_fund_currency": 100,
            "nav_per_unit_shareclass_currency": 100, "net_return": 1.5, "units_issued": 0,
            "units_redeemed": 0, "distributions": 0, "distributions_per_unit_fund_currency": 0,
            "distributions_per_unit_shareclass_currency": 0,
            "income_fund_currency": 600, "expenses_fund_currency": 500}],
        "dividends_on_shares": 600, "dividends_on_shares_lu": 100,
        "charges": 500, "advisory_management_fees": 500, "creation_date": "2025-07-01",
    }
    generated = result(client.post("/api/v1/bcl/s220/generate", json=body))
    assert generated["generated"] is True
    produced = generated["files"][0]
    assert produced["schema_validation"]["valid"] is True
    assert produced["filename"] == "S0220_L0_202512_B000000341_NAF66012345600001_20250701_001.xml"


def test_bcl_inspect_identifies_and_validates_an_upload():
    content = result(client.post("/api/v1/bcl/s13/generate", json=ledger_body()))["files"][0]["content"]
    inspected = result(client.post("/api/v1/bcl/inspect",
                                   files={"file": ("f.xml", content.encode(), "application/xml")}))
    assert inspected["recognised"] is True
    assert inspected["report_key"] == "s13"
    assert inspected["schema_validation"]["valid"] is True

    rejected = result(client.post("/api/v1/bcl/inspect",
                                  files={"file": ("f.xml", b"<html/>", "application/xml")}))
    assert rejected["recognised"] is False


def test_bcl_reference_documents_download():
    response = client.get("/api/v1/bcl/s13/reference/instructions")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    payload = client.get("/api/v1/bcl/s13/reference/nope").json()
    assert payload["success"] is False


def test_bcl_unknown_report_is_reported_not_crashed():
    payload = client.post("/api/v1/bcl/nope/generate", json=ledger_body()).json()
    assert payload["success"] is False and "nope" in payload["message"]


# =============================================================================
# AIFMD — the two files
# =============================================================================

def aifmd_payload() -> dict:
    from _aifmd_fixture import draft
    d = draft()
    return jsonable({"aifm_info": d["aifm_info"], "aif_info": d["aif_info"],
                     "period_start": d["period_start"], "period_end": d["period_end"]})


def test_aifmd_metadata_is_described():
    metadata = result(client.get("/api/v1/aifmd/metadata"))
    assert len(metadata["aif_reporting_codes"]) == 45
    assert metadata["fixed_cardinalities"]["ten_principal_exposures"] == 10


def test_aifmd_generates_both_schema_valid_files():
    generated = result(client.post("/api/v1/aifmd/generate", json=aifmd_payload()))
    assert generated["generated"] is True
    assert [f["key"] for f in generated["files"]] == ["datman", "dataif"]
    for produced in generated["files"]:
        assert produced["schema_validation"]["valid"] is True
        # CSSF control FOR-010: exactly one reporting record per file.
        assert produced["record_count"] == 1
        assert produced["filename"].startswith("AIFREP-S12345678-A12345678-")


def test_aifmd_accepts_iso_date_strings():
    """JSON has no date type, so every date arrives as a string; the engine
    wants real dates and would otherwise drop them silently."""
    validated = result(client.post("/api/v1/aifmd/validate", json=aifmd_payload()))
    assert validated["valid"] is True, validated["errors"]
    content = result(client.post("/api/v1/aifmd/generate", json=aifmd_payload()))["files"][1]["content"]
    assert "<InceptionDate>2020-01-01</InceptionDate>" in content


def test_aifmd_refuses_a_filing_that_breaks_a_cssf_control():
    payload = aifmd_payload()
    payload["aif_info"]["nav_geo_focus"] = {"EEA": 90}   # CAF-057 wants 100%
    generated = result(client.post("/api/v1/aifmd/generate", json=payload))
    assert generated["generated"] is False
    assert "CAF-057" in {e["code"] for e in generated["validation"]["errors"]}


def test_aifmd_inspect_distinguishes_the_two_files():
    files = result(client.post("/api/v1/aifmd/generate", json=aifmd_payload()))["files"]
    for produced, expected in zip(files, ("datman", "dataif")):
        inspected = result(client.post(
            "/api/v1/aifmd/inspect",
            files={"file": (produced["filename"], produced["content"].encode(), "application/xml")}))
        assert inspected["recognised"] is True and inspected["file_key"] == expected


def test_aifmd_template_downloads():
    response = client.get("/api/v1/aifmd/template")
    assert response.status_code == 200 and len(response.content) > 10_000


# =============================================================================
# Cross-report consistency
# =============================================================================

def test_bcl_cross_checks_flag_a_mismatch():
    body = {"s13": ledger_body(), "tptobs": {"header": HEADER, "securities": [
        {"line_item": "2-004000", "code_type": "1", "isin": "LU9876543414", "hold_security_type": "04",
         "esa2010_type": "F.52", "quotation_type": "currency", "number_of_units": 10,
         "reported_amount": 1, "cssf_class_code": "0001", "issue_currency": "EUR"}]}}
    checks = result(client.post("/api/v1/bcl/cross-checks", json=body))
    assert "XCHK-003" in {w["code"] for w in checks["warnings"]}


# =============================================================================
# Workflow, audit and drafts
# =============================================================================

def test_document_lifecycle_and_audit_trail():
    document_id = "TEST_LIFECYCLE.xml"
    assert result(client.post("/api/v1/documents/bcl",
                              json={"document_id": document_id, "label": "S 1.3"}))

    # The preparer may send their own filing for review; the approval has to
    # come from somebody else.
    for status, who in (("Under review", client), ("Approved", reviewer),
                        ("Published", reviewer)):
        entry = result(who.post(f"/api/v1/documents/bcl/{document_id}/status",
                                json={"status": status, "comment": "ok"}))
        assert entry["status"] == status
    assert entry["history"][-1]["user"] == REVIEWER

    # A published filing has nowhere further to go.
    refused = reviewer.post(f"/api/v1/documents/bcl/{document_id}/status",
                            json={"status": "Approved"}).json()
    assert refused["success"] is False


def test_a_preparer_cannot_approve_their_own_filing():
    """The control the review exists for. Recording who clicked is not it:
    without this check one person can generate a filing and approve it a
    second later, and the trail will faithfully record them doing it."""
    document_id = "TEST_FOUR_EYES.xml"
    result(client.post("/api/v1/documents/bcl",
                       json={"document_id": document_id, "label": "S 1.3"}))
    result(client.post(f"/api/v1/documents/bcl/{document_id}/status",
                       json={"status": "Under review"}))

    # A name in the body is ignored: the session says who is acting.
    response = client.post(f"/api/v1/documents/bcl/{document_id}/status",
                           json={"status": "Approved", "user": "someone else"})
    assert response.status_code == 400
    assert "cannot also approve" in response.json()["message"]

    # Somebody else can.
    entry = result(reviewer.post(f"/api/v1/documents/bcl/{document_id}/status",
                                 json={"status": "Approved"}))
    assert entry["status"] == "Approved"

    entries = result(client.get("/api/v1/audit?limit=50"))
    assert any(e["subject"] == document_id for e in entries)


def test_transition_of_an_unknown_document_is_reported():
    payload = client.post("/api/v1/documents/bcl/nothing.xml/status",
                          json={"status": "Approved"}).json()
    assert payload["success"] is False


def test_draft_round_trip_keeps_dates_and_tables():
    body = ledger_body()
    assert result(client.post("/api/v1/drafts/bcl", json={"name": "Test draft", "data": body}))
    names = [d["name"] for d in result(client.get("/api/v1/drafts/bcl"))]
    assert "Test draft" in names

    loaded = result(client.get("/api/v1/drafts/bcl/Test draft"))
    assert loaded["data"]["assets"] == body["assets"]
    assert loaded["data"]["header"]["end_month_date"] == "2025-12-31"

    assert result(client.delete("/api/v1/drafts/bcl/Test draft"))
    assert client.get("/api/v1/drafts/bcl/Test draft").json()["success"] is False


# =============================================================================
# The workbook-driven regimes and the PRIIPs KID
# =============================================================================

@pytest.mark.parametrize("regime_key", ["urr", "o41", "esef", "saq"])
def test_filing_templates_download(regime_key):
    response = client.get(f"/api/v1/{regime_key}/template")
    assert response.status_code == 200
    assert response.content[:2] == b"PK"          # a real xlsx is a zip
    assert len(response.content) > 1_000


def test_filing_regimes_are_described():
    regimes = result(client.get("/api/v1/reference/regimes"))
    assert {r["key"] for r in regimes} == {"urr", "o41", "esef", "saq"}


def test_unknown_filing_regime_has_no_route_at_all():
    """Each regime now owns its routes, so an unknown one cannot be reached
    rather than being reported at run time — a stronger guarantee than the
    LookupError it used to raise."""
    assert client.get("/api/v1/nope/template").status_code == 404


def test_a_bad_request_carries_a_client_error_status():
    """The envelope says why; the status says what kind. Without the status a
    failure is invisible in a network tab, a proxy log or a monitoring
    probe."""
    response = client.post("/api/v1/funds", json={"funds": [{"fund_name": "No identifier"}]})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_a_filing_refused_by_its_controls_is_not_an_http_error():
    """Deliberate: the call succeeded — the API validated the submission and
    reported that it would be rejected. That is the answer, not a failure to
    answer, so it is a 200 carrying `generated: false`. Only the API's own
    refusals and defects use 4xx and 5xx."""
    response = client.post("/api/v1/bcl/s13/generate", json={"header": {}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["generated"] is False
    assert payload["result"]["validation"]["errors"]


def test_something_missing_is_a_404_not_a_400():
    response = client.get("/api/v1/drafts/bcl/no such draft")
    assert response.status_code == 404
    assert response.json()["success"] is False


def test_a_successful_call_is_still_a_200():
    response = client.get("/api/v1/reference/modules")
    assert response.status_code == 200 and response.json()["success"] is True


def test_priips_parameters_and_templates_are_served():
    assert result(client.get("/api/v1/priips/parameters"))
    templates = result(client.get("/api/v1/priips/templates"))
    assert "standard" in templates["available"]


def test_fatca_template_downloads():
    response = client.get("/api/v1/fatca/template")
    assert response.status_code == 200 and response.content[:2] == b"PK"


def test_every_regime_with_a_capture_form_serves_it():
    """Guards the regression that splitting the routers introduced.

    The form used to be served by one generic route. Giving each regime its
    own router left AIFMD without it, and the screen answered 404 — so the
    contract is asserted here rather than left to be found in the browser:
    every regime the forms service can describe must have a route serving it.
    """
    from services.formsService import _FORMS  # noqa: PLC0415

    for regime in _FORMS:
        response = client.get(f"/api/v1/{regime}/form")
        assert response.status_code == 200, f"{regime} serves no capture form"
        assert response.json()["result"]["sections"], f"{regime} serves an empty form"
