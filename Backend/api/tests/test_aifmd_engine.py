"""[Migrated from the Streamlit MVP's tests/test_aifmd.py; the engines are
unchanged, only the imports moved from core.* to domain.*.]

Tests for the AIFMD Annex IV module — the two files, end to end.

    cd Backend/api
    poetry run pytest tests/test_aifmd_engine.py

Three things are checked:
 1. the official ESMA sample files validate against the bundled XSDs (proving
    the schemas and the validator itself are wired correctly);
 2. what the engine generates validates against those same XSDs, for every
    AIF content type — which is where the fixed-cardinality blocks and the
    all-or-nothing optional blocks are easy to get wrong;
 3. the CSSF controls of the Technical Guidance fire on data that breaks
    them, and stay silent on data that does not.
"""

from __future__ import annotations

from datetime import date

from domain.aifmd import aifmd_engine as ae
from domain.aifmd import aifmd_xsd
from domain.shared.xml_common import errors_of, warnings_of
from utils.paths import RESOURCES_DIR

SAMPLES = (RESOURCES_DIR / "regulation" / "aifmd" / "esma_package" / "extracted"
           / "2013-1358_aifmd_reporting_it_technical_guidance-revision6")


# =============================================================================
# Fixtures
# =============================================================================

def submission(content_type: str = "4") -> ae.AifmdSubmission:
    """A complete, rule-clean filing: quarterly Q4 2025, an authorised AIFM,
    a leveraged EU AIF subject to Articles 24(1), 24(2) and 24(4)."""
    return ae.AifmdSubmission(
        sender_entity_type="S", sender_id="12345678",
        reporting_period_type="Q4", reporting_period_year=2025,
        reporting_period_start=date(2025, 10, 1), reporting_period_end=date(2025, 12, 31),
        aifm_content_type="1", aifm_reporting_code=5,
        aifm_national_code="A12345678", aifm_name="Test AIFM S.A.", aifm_jurisdiction="LU",
        aifm_lei="5493001KJTIIGC8Y1R12",
        total_aum_eur=5_500_000, total_aum_base_currency=5_500_000, aifm_base_currency="EUR",
        aifm_principal_markets=[
            {"ranking": 1, "market_code_type": "MIC", "market_code": "XLUX", "aggregated_value": 4_000_000},
            {"ranking": 2, "market_code_type": "OTC", "aggregated_value": 1_500_000},
        ],
        aifm_principal_instruments=[
            {"ranking": 1, "sub_asset_type": "SEC_LEQ_IFIN", "aggregated_value": 4_000_000},
            {"ranking": 2, "sub_asset_type": "DER_FID_FIXI", "aggregated_value": 1_500_000},
        ],
        aif_content_type=content_type, aif_reporting_code=29,
        aif_legal_form="O", aif_national_number="12345678", aif_subfund_number="00000000",
        aif_name="Test AIF", aif_domicile="LU", aif_eea_flag=True,
        aif_inception_date=date(2020, 1, 1),
        aif_lei="5493001KJTIIGC8Y1R12",
        aif_base_currency="EUR", aif_aum_base_currency=10_000_000, aif_nav=9_500_000,
        aif_share_class_flag=True,
        aif_share_classes=[{"name": "Class A", "isin": "LU0323134006"}],
        aif_prime_brokers=[{"name": "Prime Broker 1", "lei": "5493001KJTIIGC8Y1R12"}],
        predominant_aif_type="HFND",
        investment_strategies=[{"group": "HFND", "code": "EQTY_LGST", "primary_flag": True, "nav_rate": 100}],
        main_instruments=[
            {"ranking": 1, "sub_asset_type": "SEC_LEQ_IFIN", "instrument_code_type": "ISIN",
             "instrument_name": "Instrument 1", "isin": "LU0323134006",
             "position_value": 1_000_000, "position_type": "L"},
            {"ranking": 2, "sub_asset_type": "DER_IRD_INTR", "instrument_code_type": "AII",
             "instrument_name": "Rate option", "aii_exchange_code": "XLIF", "aii_product_code": "ABC",
             "aii_derivative_type": "O", "aii_put_call": "C", "aii_expiry_date": date(2027, 12, 16),
             "aii_strike_price": 1.6, "position_value": 900_000, "position_type": "S", "hedging_rate": 1.26},
        ],
        nav_geo_focus={"EEA": 100},
        aum_geo_focus={"EEA": 100},
        ten_principal_exposures=[
            {"ranking": 1, "macro_type": "SEC", "sub_asset_type": "SEC_LEQ_IFIN", "position_type": "L",
             "aggregated_value": 1_000_000, "aggregated_value_pct": 50,
             "counterparty_name": "Bank A", "counterparty_lei": "5493001KJTIIGC8Y1R12"},
        ],
        portfolio_concentrations=[
            {"ranking": 1, "asset_type": "SEC_LEQ", "position_type": "L", "market_code_type": "MIC",
             "market_code": "XLUX", "aggregated_value": 1_000_000, "aggregated_value_pct": 50},
            {"ranking": 2, "asset_type": "DER_IRD", "position_type": "S", "market_code_type": "OTC",
             "aggregated_value": 500_000, "aggregated_value_pct": 25, "counterparty_name": "Bank B"},
        ],
        aif_principal_markets=[
            {"ranking": 1, "market_code_type": "MIC", "market_code": "XLUX", "aggregated_value": 1_000_000},
        ],
        investor_beneficial_owners_rate=60, investor_professional_rate=100, investor_retail_rate=0,
        instrument_exposures=[
            {"code": "SEC_LEQ_IFIN", "long_value": 1_000_000, "short_value": 0},
            {"code": "DER_FEX_HEDG", "gross_value": 500_000},
        ],
        asset_turnovers=[{"code": "SEC_LEQ_LEQ", "market_value": 100_000, "notional_value": 0}],
        currency_exposures=[{"currency": "USD", "long_value": 10_000, "short_value": 0}],
        annual_investment_return_rate="5.5",
        market_risk_measures=[
            {"code": "NET_EQTY_DELTA", "value": 1.2},
            {"code": "NET_DV01", "bucket_lt5": 1},
            {"code": "NET_CS01", "bucket_lt5": 0.5},
            {"code": "VEGA_EXPO", "vega_current": 2},
            {"code": "VAR", "var_value": 3, "var_method": "HISTO"},
        ],
        trading_pct_securities_exchange=90, trading_pct_securities_otc=10,
        trading_pct_derivatives_exchange=80, trading_pct_derivatives_otc=20,
        derivatives_ccp_rate=70, derivatives_bilateral_rate=30,
        repo_ccp_rate=50, repo_bilateral_rate=30, repo_triparty_rate=20,
        collateral_cash_posted=1_000, collateral_securities_posted=2_000, collateral_other_posted=0,
        counterparty_exposures_to_aif=[{"ranking": 1, "name": "Bank A", "nav_pct": 3.5}],
        counterparty_exposures_from_aif=[{"ranking": 1, "name": "Bank B", "nav_pct": 2.5}],
        ccp_clearing_flag=True,
        ccp_exposures=[{"ranking": 1, "name": "LCH", "lei": "5493001KJTIIGC8Y1R12", "exposure_value": 5_000}],
        portfolio_liquidity={"D0_1": 100}, unencumbered_cash=1_000_000,
        investor_liquidity={"D0_1": 100},
        provide_withdrawal_rights=True, redemption_frequency="M",
        redemption_notice_period_days=5, redemption_lockup_period_days=0,
        side_pocket_rate=1, gates_rate=2, dealing_suspension_rate=3, total_arrangement_rate=6,
        investor_preferential_treatment_flag=True, pref_disclosure_flag=True,
        pref_liquidity_flag=False, pref_fee_flag=False, pref_other_flag=False,
        investor_groups=[{"code": "BANK", "rate": 40}, {"code": "PFND", "rate": 60}],
        total_financing_amount=500_000, financing_buckets={"D0_1": 100},
        total_open_positions=42,
        historical_performance=[
            {"month": "October", "gross_return": 1.1, "net_return": 1.0, "nav_change": 0.9,
             "subscriptions": 10_000, "redemptions": 5_000},
        ],
        stress_test_article15="Article 15 stress test narrative.",
        stress_test_article16="Article 16 stress test narrative.",
        rehypothecation_flag=True, rehypothecation_rate=25,
        unsecured_borrowing_amount=1_000, secured_borrowing_prime_brokerage_amount=2_000,
        secured_borrowing_reverse_repo_amount=3_000, secured_borrowing_other_amount=4_000,
        exchange_traded_derivatives_exposure=5_000, otc_derivatives_amount=6_000,
        short_position_borrowed_securities_value=7_000,
        controlled_structures=[{"name": "SPV 1", "exposure_value": 9_000}],
        gross_method_rate=110, commitment_method_rate=105,
        borrowing_sources=[{"ranking": 1, "name": "Bank C", "leverage_amount": 1_000_000}],
    )


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def assert_valid(xml: str, key: str) -> None:
    result = aifmd_xsd.validate(xml, key)
    assert result.available, "lxml is required to run these tests"
    assert result.valid, f"{key} is invalid against its XSD:\n" + "\n".join(result.errors[:5])


# =============================================================================
# 1. The official ESMA samples validate against the bundled schemas
# =============================================================================

def test_official_samples_validate():
    for name, key in (("AIFMSample.xml", "datman"), ("AIFSample.xml", "dataif")):
        raw = (SAMPLES / name).read_bytes()
        assert aifmd_xsd.detect_file(raw) == key, f"{name} was not identified as {key}"
        result = aifmd_xsd.validate(raw, key)
        assert result.valid, f"{name} is invalid:\n" + "\n".join(result.errors[:5])


def test_detect_file_rejects_a_foreign_document():
    assert aifmd_xsd.detect_file(b"<html><body>not a report</body></html>") is None
    assert aifmd_xsd.detect_file(b"<not-xml") is None
    result = aifmd_xsd.validate(b"<foo/>")
    assert not result.valid and "Unrecognised root element" in result.errors[0]


def test_an_aif_file_is_not_accepted_as_an_aifm_file():
    """CSSF controls FOR-003 / FOR-004: the file type in the name must match
    the XML."""
    raw = (SAMPLES / "AIFSample.xml").read_bytes()
    result = aifmd_xsd.validate(raw, "datman")
    assert not result.valid
    assert "FOR-003" in result.errors[0]


# =============================================================================
# 2. Both files generate valid XML, for every content type
# =============================================================================

def test_both_files_validate_for_every_content_type():
    for content_type in ae.AIF_CONTENT_TYPES:
        sub = submission(content_type)
        assert_valid(ae.build_datman_xml(sub), "datman")
        assert_valid(ae.build_dataif_xml(sub), "dataif")


def test_each_file_carries_exactly_one_record():
    """CSSF control FOR-010."""
    sub = submission()
    assert aifmd_xsd.record_count(ae.build_datman_xml(sub)) == 1
    assert aifmd_xsd.record_count(ae.build_dataif_xml(sub)) == 1


def test_fixed_cardinality_blocks_are_padded_in_full():
    """The regression that made every AIFMD file invalid: the blocks the
    schema declares with an exact number of occurrences were emitted with only
    the rows a preparer had filled in, or empty."""
    sub = submission()
    datman = ae.build_datman_xml(sub)
    assert datman.count("<AIFMFivePrincipalMarket>") == 5
    assert datman.count("<AIFMPrincipalInstrument>") == 5

    dataif = ae.build_dataif_xml(sub)
    assert dataif.count("<MainInstrumentTraded>") == 5
    assert dataif.count("<PrincipalExposure>") == 10
    assert dataif.count("<PortfolioConcentration>") == 5
    assert dataif.count("<AIFPrincipalMarket>") == 3
    assert dataif.count("<FundToCounterpartyExposure>") == 5
    assert dataif.count("<CounterpartyToFundExposure>") == 5
    assert dataif.count("<BorrowingSource>") == 5


def test_unused_ranks_use_the_nothing_to_report_codes():
    sub = submission()
    dataif = ae.build_dataif_xml(sub)
    # Three of the five main instruments and nine of the ten exposures are unused.
    assert dataif.count("<SubAssetType>NTA_NTA_NOTA</SubAssetType>") == 3
    assert dataif.count("<AssetMacroType>NTA</AssetMacroType>") == 9
    assert dataif.count("<AssetType>NTA_NTA</AssetType>") == 3
    assert dataif.count("<MarketCodeType>NOT</MarketCodeType>") == 2
    assert dataif.count("<CounterpartyExposureFlag>false</CounterpartyExposureFlag>") == 8
    assert dataif.count("<BorrowingSourceFlag>false</BorrowingSourceFlag>") == 4


def test_empty_report_omits_the_description_block():
    """CSSF controls CAF-012 / CSSF-018."""
    sub = submission()
    sub.aif_no_reporting_flag = True
    sub.aifm_no_reporting_flag = True
    dataif = ae.build_dataif_xml(sub)
    datman = ae.build_datman_xml(sub)
    assert_valid(dataif, "dataif")
    assert_valid(datman, "datman")
    assert "<AIFCompleteDescription>" not in dataif
    assert "<AIFMCompleteDescription>" not in datman


def test_cancellation_records():
    """CSSF controls CSSF-009 / CSSF-013."""
    sub = submission()
    sub.aifm_cancellation = True
    sub.aif_cancellation = True
    datman = ae.build_datman_xml(sub)
    dataif = ae.build_dataif_xml(sub)
    assert_valid(datman, "datman")
    assert_valid(dataif, "dataif")
    assert "<CancellationAIFMRecordInfo>" in datman and "<CancelledRecordFlag>C</CancelledRecordFlag>" in datman
    assert "<CancellationAIFRecordInfo>" in dataif


def test_article_blocks_follow_the_content_type():
    """Article 24(2) drives AIFIndividualInfo, Articles 24(2)/24(4) drive
    AIFLeverageInfo, and 24(4) alone drives the borrowing sources."""
    expectations = {
        "1": (False, False, False),
        "2": (True, True, False),
        "3": (False, False, False),
        "4": (True, True, True),
        "5": (False, True, True),
    }
    for content_type, (individual, leverage, article_24_4) in expectations.items():
        xml = ae.build_dataif_xml(submission(content_type))
        assert ("<AIFIndividualInfo>" in xml) is individual, content_type
        assert ("<AIFLeverageInfo>" in xml) is leverage, content_type
        assert ("<AIFLeverageArticle24-4>" in xml) is article_24_4, content_type


def test_eur_base_currency_omits_the_fx_block():
    """CSSF control CAF-030: the FX rate is forbidden for a EUR base currency."""
    sub = submission()
    xml = ae.build_dataif_xml(sub)
    assert "<FXEURRate>" not in xml
    sub.aif_base_currency = "USD"
    sub.aif_fx_rate = 0.9234
    sub.aif_fx_ref_rate_type = "ECB"
    xml = ae.build_dataif_xml(sub)
    assert "<FXEURRate>0.9234</FXEURRate>" in xml
    assert_valid(xml, "dataif")


def test_amounts_are_integers_and_rates_carry_two_decimals():
    sub = submission()
    sub.aif_nav = 9_500_000.4
    sub.investor_beneficial_owners_rate = 60.125
    xml = ae.build_dataif_xml(sub)
    assert "<AIFNetAssetValue>9500000</AIFNetAssetValue>" in xml
    assert "<MainBeneficialOwnersRate>60.13</MainBeneficialOwnersRate>" in xml
    assert "e+" not in xml.lower()
    assert_valid(xml, "dataif")


def test_xml_escaping():
    sub = submission()
    sub.aif_name = 'Fund <A> & "B"'
    xml = ae.build_dataif_xml(sub)
    assert "&lt;A&gt; &amp;" in xml
    assert_valid(xml, "dataif")


def test_file_names_follow_the_cssf_convention():
    sub = submission()
    datman = ae.build_datman_filename(sub)
    dataif = ae.build_dataif_filename(sub)
    assert datman.startswith("AIFREP-S12345678-A12345678-F00000000-00000000-MAN-")
    assert dataif.startswith("AIFREP-S12345678-A12345678-O12345678-00000000-AIF-")
    assert datman.endswith(".xml") and dataif.endswith(".xml")
    assert len(datman.rsplit("-", 1)[1]) == len("20260101120000.xml")


# =============================================================================
# 3. The CSSF controls
# =============================================================================

def test_a_complete_submission_raises_no_issue():
    issues = submission().validation_issues()
    assert not issues, [str(i) for i in issues]


def test_reporting_period_dates_must_match_the_period_type():
    sub = submission()
    sub.reporting_period_start = date(2025, 11, 1)
    assert "CAM-002" in codes(errors_of(sub.validation_issues()))
    assert "CAF-003" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.reporting_period_end = date(2025, 11, 30)
    assert "CAM-003" in codes(errors_of(sub.validation_issues()))

    # A last report may stop early.
    sub = submission()
    sub.reporting_period_end = date(2025, 11, 30)
    sub.aifm_last_reporting_flag = True
    sub.aif_last_reporting_flag = True
    assert "CAM-003" not in codes(errors_of(sub.validation_issues()))


def test_reporting_period_year_must_match_the_dates():
    sub = submission()
    sub.reporting_period_year = 2024
    assert "CSSF-006" in codes(errors_of(sub.validation_issues()))


def test_reporting_codes_must_match_the_supervision_status():
    sub = submission()
    sub.aifm_reporting_code = 1  # registered, but the content type says authorised
    assert "CSSF-032" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_reporting_code = 40  # an Article 42 code under an authorised AIFM
    assert "CSSF-034" in codes(errors_of(sub.validation_issues()))


def test_content_type_must_match_the_article_obligations():
    """CSSF control CSSF-046."""
    sub = submission("1")   # 24(1) only, but code 29 is a leveraged AIF under 24(2)/24(4)
    assert "CSSF-046" in codes(errors_of(sub.validation_issues()))


def test_eea_flag_must_match_the_domicile():
    sub = submission()
    sub.aif_domicile = "US"
    assert "CAF-009" in codes(errors_of(sub.validation_issues()))


def test_inception_date_must_precede_the_period():
    sub = submission()
    sub.aif_inception_date = date(2026, 1, 1)
    assert "CAF-011" in codes(errors_of(sub.validation_issues()))


def test_identifier_check_digits():
    sub = submission()
    sub.aif_lei = "5493001KJTIIGC8Y1R13"  # wrong check digits
    assert "CAF-013" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_share_classes = [{"name": "Class A", "isin": "LU0323134007"}]
    assert "CAF-017" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.main_instruments[0]["isin"] = "LU0323134007"
    assert "CAF-044" in codes(errors_of(sub.validation_issues()))


def test_national_code_formats():
    sub = submission()
    sub.aifm_national_code = "12345678"
    assert "CSSF-001" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_national_number = "123"
    assert "ERR-008" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_subfund_number = "1"
    assert "CSSF-015" in codes(errors_of(sub.validation_issues()))


def test_reporting_member_state_must_be_lu():
    sub = submission()
    sub.reporting_member_state = "FR"
    assert "FIL-009" in codes(errors_of(sub.validation_issues()))


def test_percentages_that_must_sum_to_100():
    sub = submission()
    sub.nav_geo_focus = {"EEA": 90}
    assert "CAF-057" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.investment_strategies = [{"group": "HFND", "code": "EQTY_LGST", "primary_flag": True, "nav_rate": 80}]
    assert "CAF-039" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.investor_groups = [{"code": "BANK", "rate": 40}]
    assert "CSSF-023" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.portfolio_liquidity = {"D0_1": 90}
    assert "CAF-128" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.trading_pct_securities_exchange = 50  # 50 + 10 != 100
    assert "CAF-109" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.repo_triparty_rate = 5  # 50 + 30 + 5 != 100
    assert "WAF-002" in codes(errors_of(sub.validation_issues()))


def test_financing_breakdown_tolerance():
    """CSSF controls CSSF-042 / CAF-204: 99-101% is a warning, outside is an
    error."""
    sub = submission()
    sub.financing_buckets = {"D0_1": 99.5}
    assert "CSSF-042" in codes(warnings_of(sub.validation_issues()))
    assert "CAF-204" not in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.financing_buckets = {"D0_1": 80}
    assert "CAF-204" in codes(errors_of(sub.validation_issues()))


def test_duplicate_and_out_of_order_ranks():
    sub = submission()
    sub.main_instruments[1]["ranking"] = 1
    assert "CSSF-020" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.ten_principal_exposures = [
        {"ranking": 1, "macro_type": "SEC", "sub_asset_type": "SEC_LEQ_IFIN", "position_type": "L",
         "aggregated_value": 100, "aggregated_value_pct": 10},
        {"ranking": 2, "macro_type": "SEC", "sub_asset_type": "SEC_LEQ_OTHR", "position_type": "L",
         "aggregated_value": 900, "aggregated_value_pct": 40},
    ]
    assert "CAF-062" in codes(errors_of(sub.validation_issues()))


def test_main_instrument_conditional_fields():
    sub = submission()
    sub.main_instruments[0]["instrument_code_type"] = "ISIN"
    sub.main_instruments[0]["isin"] = ""
    assert "CAF-045" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.main_instruments[1]["aii_exchange_code"] = ""
    assert "CAF-047" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.main_instruments[1]["aii_expiry_date"] = date(2009, 1, 1)
    assert "CSSF-016" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.main_instruments[1]["aii_put_call"] = "F"  # an option must be P or C
    assert "CAF-050" in codes(errors_of(sub.validation_issues()))


def test_market_code_conditionals():
    sub = submission()
    sub.aifm_principal_markets[0]["market_code"] = ""
    assert "CAM-010" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.portfolio_concentrations[0]["market_code"] = ""
    assert "CAF-069" in codes(errors_of(sub.validation_issues()))


def test_beneficial_owners_rate_cannot_be_zero():
    sub = submission()
    sub.investor_beneficial_owners_rate = 0
    assert "CSSF-021" in codes(errors_of(sub.validation_issues()))


def test_aum_and_nav_cannot_be_zero():
    sub = submission()
    sub.aif_nav = 0
    assert "CSSF-047" in codes(errors_of(sub.validation_issues()))


def test_aum_in_euro_must_match_the_base_currency_amount():
    """CSSF control CSSF-031."""
    sub = submission()
    sub.total_aum_eur = 1
    assert "CSSF-031" in codes(errors_of(sub.validation_issues()))


def test_derivatives_require_a_lei():
    """CSSF control CSSF-040."""
    sub = submission()
    sub.aif_lei = ""
    assert "CSSF-040" in codes(errors_of(sub.validation_issues()))


def test_predominant_type_none_requires_two_strategies():
    """CSSF control CSSF-012."""
    sub = submission()
    sub.predominant_aif_type = "NONE"
    assert "CSSF-012" in codes(errors_of(sub.validation_issues()))


def test_only_one_primary_strategy_per_group():
    sub = submission()
    sub.investment_strategies = [
        {"group": "HFND", "code": "EQTY_LGST", "primary_flag": True, "nav_rate": 50},
        {"group": "HFND", "code": "MACR_MACR", "primary_flag": True, "nav_rate": 50},
    ]
    assert "CSSF-024" in codes(errors_of(sub.validation_issues()))


def test_other_strategy_requires_a_description():
    sub = submission()
    sub.investment_strategies = [{"group": "HFND", "code": "OTHR_HFND", "primary_flag": True, "nav_rate": 100}]
    assert "CAF-041" in codes(errors_of(sub.validation_issues()))


def test_article_24_2_mandatory_fields():
    sub = submission()
    sub.unencumbered_cash = None
    assert "CAF-206" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.provide_withdrawal_rights = None
    assert "CAF-207" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.market_risk_measures = [{"code": "NET_EQTY_DELTA", "value": 1.2}]
    missing = codes(errors_of(sub.validation_issues()))
    assert "CAF-216" in missing


def test_article_24_4_mandatory_fields():
    sub = submission()
    sub.unsecured_borrowing_amount = None
    assert "CAF-208" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.borrowing_sources = []
    assert "CAF-141" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.gross_method_rate = None
    assert "CSSF-045" in codes(errors_of(sub.validation_issues()))


def test_individual_exposure_rules():
    sub = submission()
    sub.instrument_exposures = [{"code": "NTA_NTA_NOTA", "long_value": 1}]
    assert "CSSF-022" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.instrument_exposures = [{"code": "DER_FEX_HEDG", "long_value": 1}]
    assert "CAF-085" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.currency_exposures = [{"currency": "USD", "long_value": 1}, {"currency": "USD", "short_value": 2}]
    assert "CSSF-033" in codes(errors_of(sub.validation_issues()))


def test_rehypothecation_rate_requires_the_flag():
    sub = submission()
    sub.rehypothecation_flag = False
    assert "CAF-139" in codes(warnings_of(sub.validation_issues()))

    sub = submission()
    sub.rehypothecation_rate = None
    assert "CAF-139" in codes(errors_of(sub.validation_issues()))


def test_ccp_flag_requires_an_exposure():
    """CSSF control CAF-125."""
    sub = submission()
    sub.ccp_exposures = []
    assert "CAF-125" in codes(errors_of(sub.validation_issues()))


def test_change_quarter_is_conditional():
    sub = submission()
    sub.aifm_change_frequency_code = "QH"
    assert "CAM-004" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_change_quarter = "Q4"
    assert "CAF-006" in codes(warnings_of(sub.validation_issues()))


def test_typical_position_size_is_private_equity_only():
    sub = submission()
    sub.typical_position_size = "L_CAP"
    assert "CAF-079" in codes(warnings_of(sub.validation_issues()))

    sub = submission()
    sub.predominant_aif_type = "PEQF"
    sub.investment_strategies = [{"group": "PEQF", "code": "VENT_CAPL", "primary_flag": True, "nav_rate": 100}]
    assert "CAF-079" in codes(errors_of(sub.validation_issues()))


def test_master_feeder_rules():
    sub = submission()
    sub.aif_master_feeder_status = "FEEDER"
    assert "CAF-024" in codes(errors_of(sub.validation_issues()))

    sub = submission()
    sub.aif_master_aifs = [{"name": "Master AIF"}]
    assert "CAF-024" in codes(warnings_of(sub.validation_issues()))


def test_share_class_rules():
    sub = submission()
    sub.aif_share_class_flag = False
    assert "CAF-016" in codes(warnings_of(sub.validation_issues()))

    sub = submission()
    sub.aif_share_classes = []
    assert "CAF-023" in codes(errors_of(sub.validation_issues()))


