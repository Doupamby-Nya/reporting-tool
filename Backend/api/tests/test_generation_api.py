"""The generation endpoints the first API suite did not reach.

test_non_regression.py proves each regime files what the Streamlit tool
filed. These cover what that comparison cannot: behaviour the migration
changed on purpose (a blank cell no longer crashes U 1.1), outputs that are
binary (the ESEF package, the KID PDF), the fund registry, and the checks
ported from the Streamlit suite's test_aifmd_app.py, which drove the
AIFMD views and now drive the API instead.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path


from _aifmd_fixture import draft as aifmd_draft
from _auth import PREPARER, REVIEWER, login_as  # noqa: E402
from non_regression.cases import ESEF_DRAFT, INPUTS, URR_FINAL, jsonable

client = login_as(PREPARER)
API = "/api/v1"


def result(response) -> dict:
    payload = response.json()
    assert payload["success"] is True, payload.get("message")
    return payload["result"]


# =============================================================================
# U 1.1 / O 4.1 / ESEF / SAQ
# =============================================================================

def test_a_blank_share_class_cell_keeps_its_default():
    """In the Streamlit tool a share class with an empty numeric cell crashed
    the generation (float(""))."""
    share_class = {**URR_FINAL["share_classes"][0], "distributions": "", "units_issued": None}
    answer = result(client.post(f"{API}/urr/generate", json={**URR_FINAL, "share_classes": [share_class]}))
    assert answer["generated"] is True
    assert "<Distributions>0.00000</Distributions>" in answer["content"]


def test_a_refused_filing_is_an_answer_not_an_http_error():
    response = client.post(f"{API}/saq/generate", json={
        "entity_name": "Demo", "uci_type": "UCITS", "financial_year_end": "2025-12-31"})
    assert response.status_code == 200
    answer = result(response)
    assert answer["generated"] is False
    assert any("dirigeants" in message for message in answer["errors"])


def test_a_submission_without_its_dates_is_a_bad_request():
    response = client.post(f"{API}/esef/generate", json={**ESEF_DRAFT, "period_end": None})
    assert response.status_code == 400
    assert "period_end" in response.json()["message"]


def test_the_parsed_workbook_is_a_draft_the_generator_accepts():
    """The parse answer is posted back as it is: that is what the ingestion
    screen does."""
    content = (INPUTS / "o41_filled.xlsx").read_bytes()
    parsed = result(client.post(f"{API}/o41/parse", files={"file": ("o41.xlsx", content)}))
    assert parsed.pop("errors") == []
    assert {"uci_name", "year_end", "values", "country_breakdown", "marketing_countries"} <= parsed.keys()
    assert result(client.post(f"{API}/o41/generate", json=parsed))["generated"] is True


def test_a_malformed_body_is_a_422_in_the_usual_envelope():
    """Typed request models refuse a body that can never be right; the answer
    keeps the {success, message} envelope so the client can show why."""
    response = client.post(f"{API}/urr/generate", json={**URR_FINAL, "reference_month": "not a date"})
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False and "reference_month" in payload["message"]

    response = client.post(f"{API}/priips/calculate", json={})
    assert response.status_code == 422 and "fund" in response.json()["message"]


def test_the_openapi_page_documents_each_regime_s_draft():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("UrrDraft", "O41Draft", "EsefDraft", "SaqDraft", "LedgerRequest", "S220Request",
                 "AifmdRequest", "KidRequest", "FilingResult", "GenerationResult"):
        assert name in schemas, name
    assert "reference_month" in schemas["UrrDraft"]["properties"]


def test_the_esef_report_package_is_a_zip_carrying_the_report():
    answer = result(client.post(f"{API}/esef/generate", json=ESEF_DRAFT, params={"as_package": True}))
    assert answer["generated"] is True and answer["media_type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(answer["content_base64"])))
    assert any(name.endswith(".xhtml") for name in archive.namelist())


# =============================================================================
# PRIIPs
# =============================================================================

def _fund() -> dict:
    return json.loads((INPUTS / "priips_funds.json").read_text(encoding="utf-8"))[0]


def test_the_kid_is_built_on_the_configured_calibration(monkeypatch):
    """Without parameters in the request, the KID must use the calibration the
    configuration screen saved — as the Streamlit KID step did — and so agree
    with the calculation step."""
    from domain.shared import templates

    default = result(client.post(f"{API}/priips/kid", json={"fund": _fund()}))["sri"]

    # A calibration under which every volatility lands in the top class.
    calibrated = templates.load_rts_parameters()
    for band in calibrated["mrm_volatility_bands_pct"][:-1]:
        band["max_vol_pct"] = 0.01
    monkeypatch.setattr(templates, "load_rts_parameters", lambda: calibrated)

    kid = result(client.post(f"{API}/priips/kid", json={"fund": _fund()}))
    calculation = result(client.post(f"{API}/priips/calculate", json={"fund": _fund()}))
    assert calculation["sri"]["mrm_class"] == 7 != default["mrm_class"]
    assert kid["sri"] == calculation["sri"]


def test_the_kid_renders_as_a_pdf():
    kid = result(client.post(f"{API}/priips/kid", json={"fund": _fund()}))
    response = client.post(f"{API}/priips/kid/render", json={"kid": kid})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_the_three_kid_templates_are_available():
    """theme_red and theme_dark_blue were missing from the first migration."""
    available = result(client.get(f"{API}/priips/templates"))["available"]
    assert {"standard", "theme_red", "theme_dark_blue"} <= set(available)
    kid = result(client.post(f"{API}/priips/kid", json={"fund": _fund(), "template_name": "theme_red"}))
    assert kid


# =============================================================================
# The fund registry
# =============================================================================

def test_fund_registry_round_trip():
    assert result(client.delete(f"{API}/funds")) is not None
    assert result(client.get(f"{API}/funds")) == []

    result(client.post(f"{API}/funds/demo"))
    funds = result(client.get(f"{API}/funds"))
    assert len(funds) == 10

    first = funds[0]["fund_id"]
    result(client.delete(f"{API}/funds/{first}"))
    assert first not in {f["fund_id"] for f in result(client.get(f"{API}/funds"))}

    template = client.get(f"{API}/funds/template")
    assert template.status_code == 200 and template.content[:2] == b"PK"
    parsed = result(client.post(f"{API}/funds/parse", files={"file": ("funds.xlsx", template.content)}))
    assert isinstance(parsed, dict)


# =============================================================================
# FATCA / CRS
# =============================================================================

def test_fatca_classification_counts_each_category():
    content = (INPUTS / "fatca_crs.xlsx").read_bytes()
    parameters = {"crs_fatca": "CRS", "report_type": "Data Report", "selection": "Initial", "version": "1"}
    classified = result(client.post(f"{API}/fatca/classify", files={"file": ("f.xlsx", content)},
                                    data={"parameters": json.dumps(parameters)}))
    assert classified["counts"]["Individual"] == 2
    assert classified["counts"]["Active NFE"] == 1


def test_fatca_refuses_an_unknown_preparer():
    content = (INPUTS / "fatca_crs.xlsx").read_bytes()
    response = client.post(f"{API}/fatca/generate", files={"file": ("f.xlsx", content)},
                           data={"parameters": json.dumps({"crs_fatca": "CRS", "report_type": "Zero Report",
                                                           "selection": "Initial", "version": "1"}),
                                 "preparer": "Nobody"})
    assert response.json()["success"] is False


# =============================================================================
# AIFMD — ported from the Streamlit suite's test_aifmd_app.py
#
# Those tests started from the draft the ingestion view saved and checked
# that every value reached the XML. The API is now the path a draft takes,
# so they post the same draft to it.
# =============================================================================

def _aifmd(d: dict | None = None) -> dict:
    d = d or aifmd_draft()
    return jsonable({"aifm_info": d["aifm_info"], "aif_info": d["aif_info"],
                     "period_start": d["period_start"], "period_end": d["period_end"]})


def _files(payload: dict) -> dict[str, str]:
    answer = result(client.post(f"{API}/aifmd/generate", json=payload))
    assert answer["generated"] is True, answer["validation"]["errors"]
    return {f["key"]: f["content"] for f in answer["files"]}


def test_aifmd_scalar_values_reach_the_xml():
    files = _files(_aifmd())
    for fragment in ("<AIFMNationalCode>A12345678</AIFMNationalCode>", "<AIFMName>Test AIFM S.A.</AIFMName>",
                     "<AIFMReportingCode>5</AIFMReportingCode>", "<AUMAmountInEuro>5500000</AUMAmountInEuro>",
                     "<QuestionNumber>45</QuestionNumber>"):
        assert fragment in files["datman"], f"missing from DATMAN: {fragment}"
    for fragment in (
        "<AIFName>Test AIF</AIFName>", "<AIFNationalCode>O12345678</AIFNationalCode>",
        "<AIFReportingCode>29</AIFReportingCode>", "<InceptionDate>2020-01-01</InceptionDate>",
        "<AIFNetAssetValue>9500000</AIFNetAssetValue>",
        "<AUMAmountInBaseCurrency>10000000</AUMAmountInBaseCurrency>",
        "<PredominantAIFType>HFND</PredominantAIFType>", "<HedgeFundStrategyType>EQTY_LGST</HedgeFundStrategyType>",
        "<ShareClassName>Class A</ShareClassName>", "<EntityName>Prime Broker 1</EntityName>",
        "<EEANAVRate>100</EEANAVRate>", "<MainBeneficialOwnersRate>60</MainBeneficialOwnersRate>",
        "<AnnualInvestmentReturnRate>5.5</AnnualInvestmentReturnRate>",
        "<UnencumberedCash>1000000</UnencumberedCash>",
        "<InvestorRedemptionFrequency>M</InvestorRedemptionFrequency>",
        "<InvestorGroupType>BANK</InvestorGroupType>", "<TotalFinancingAmount>500000</TotalFinancingAmount>",
        "<TotalOpenPositions>42</TotalOpenPositions>",
        "<StressTestsResultArticle15>Article 15 narrative.</StressTestsResultArticle15>",
        "<GrossMethodRate>110</GrossMethodRate>", "<CommitmentMethodRate>105</CommitmentMethodRate>",
        "<AllCounterpartyCollateralRehypothecatedRate>25</AllCounterpartyCollateralRehypothecatedRate>",
        "<ControlledStructureExposureValue>9000</ControlledStructureExposureValue>",
        "<LeverageAmount>1000000</LeverageAmount>", "<CCPExposureValue>5000</CCPExposureValue>",
        "<RateOctober>1.1</RateOctober>", "<QuantityOctober>10000</QuantityOctober>",
    ):
        assert fragment in files["dataif"], f"missing from DATAIF: {fragment}"


def test_aifmd_every_repeating_table_reaches_the_xml():
    dataif = _files(_aifmd())["dataif"]
    for fragment, label in (
        ("<SubAssetType>SEC_LEQ_IFIN</SubAssetType>", "main instruments / exposures"),
        ("<ISINInstrumentIdentification>LU0323134006</ISINInstrumentIdentification>", "instrument ISIN"),
        ("<AssetType>SEC_LEQ</AssetType>", "portfolio concentration"),
        ("<MarketCode>XLUX</MarketCode>", "principal market MIC"),
        ("<ExposureCurrency>USD</ExposureCurrency>", "currency exposure"),
        ("<TurnoverSubAssetType>SEC_LEQ_LEQ</TurnoverSubAssetType>", "asset turnover"),
        ("<RiskMeasureType>NET_EQTY_DELTA</RiskMeasureType>", "risk measure"),
        ("<VARCalculationMethodCodeType>HISTO</VARCalculationMethodCodeType>", "VAR method"),
        ("<GrossValue>500000</GrossValue>", "FX derivative gross value"),
        ("<LongValue>1000000</LongValue>", "individual exposure long value"),
    ):
        assert fragment in dataif, f"missing from DATAIF ({label}): {fragment}"


def test_aifmd_blank_editor_rows_do_not_leak_into_the_filing():
    d = aifmd_draft()
    blank_main = {k: None for k in d["aif_info"]["main_instruments"][0]}
    d["aif_info"]["main_instruments"] = d["aif_info"]["main_instruments"] + [blank_main]
    d["aif_info"]["currency_exposures"] = d["aif_info"]["currency_exposures"] + [
        {"currency": None, "long_value": None, "short_value": None}]
    d["aif_info"]["aif_prime_brokers"] = d["aif_info"]["aif_prime_brokers"] + [
        {"name": None, "lei": None, "bic": None}]
    dataif = _files(_aifmd(d))["dataif"]
    assert dataif.count("<MainInstrumentTraded>") == 5
    assert dataif.count("<CurrencyExposure>") == 1
    assert dataif.count("<PrimeBrokerIdentification>") == 1


def test_aifmd_a_blank_draft_is_reported_not_crashed():
    answer = result(client.post(f"{API}/aifmd/generate", json={
        "aifm_info": {}, "aif_info": {}, "period_start": "2025-01-01", "period_end": "2025-12-31"}))
    assert answer["generated"] is False and answer["validation"]["errors"]


def test_inputs_are_present():
    """The suite reads committed fixtures; a missing one is a setup error,
    reported as such rather than as twenty confusing failures."""
    for name in ("urr_filled.xlsx", "o41_filled.xlsx", "esef_filled.xlsx", "saq_filled.xlsx",
                 "fatca_crs.xlsx", "fatca_crs_renamed_tabs.xlsx", "priips_funds.json"):
        assert (Path(INPUTS) / name).exists(), name
