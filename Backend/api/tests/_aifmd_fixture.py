"""The AIFMD draft the API tests build a filing from.

This is the dictionary the capture form saves — every repeating table uses
the column names of its own editor, every scalar its own field key — so a
field written under one name and read under another is caught here rather
than in a CSSF rejection notice.

It is a copy rather than an import: the reference suite it came from drives
the Streamlit app through `streamlit.testing`, and the API has no reason to
depend on Streamlit being installed, nor on that project being on disk.
"""

from __future__ import annotations

from datetime import date


def draft() -> dict:
    """Every repeating table uses the column names of its own st.data_editor
    in views/aifmd_ingestion.py; every scalar uses its widget key."""
    return {
        "period_start": date(2025, 10, 1),
        "period_end": date(2025, 12, 31),
        "aifm_info": {
            "sender_entity_type": "S", "sender_id": "12345678",
            "aifm_version": "1.2", "aifm_filing_type": "INIT", "aifm_content_type": "1",
            "reporting_period_type": "Q4", "reporting_period_year": 2025,
            "aifm_last_reporting_flag": False,
            "aifm_assumptions": [{"question_number": 45, "description": "Estimated NAV"}],
            "aifm_reporting_code": 5, "aifm_jurisdiction": "LU",
            "aifm_national_code": "A12345678", "aifm_name": "Test AIFM S.A.",
            "aifm_eea_flag": True, "aifm_no_reporting_flag": False,
            "aifm_lei": "5493001KJTIIGC8Y1R12", "aifm_bic": "",
            "aifm_principal_markets": [
                {"ranking": 1, "market_code_type": "MIC", "market_code": "XLUX", "aggregated_value": 4_000_000},
                {"ranking": 2, "market_code_type": "OTC", "market_code": None, "aggregated_value": 1_500_000},
            ],
            "aifm_principal_instruments": [
                {"ranking": 1, "sub_asset_type": "SEC_LEQ_IFIN", "aggregated_value": 4_000_000},
                {"ranking": 2, "sub_asset_type": "DER_FID_FIXI", "aggregated_value": 1_500_000},
            ],
            "total_aum_eur": 5_500_000, "total_aum_base_currency": 5_500_000,
            "aifm_base_currency": "EUR", "aifm_fx_ref_rate_type": "", "eur_fx_rate": 1.0,
            "aifm_fx_ref_rate_description": "",
        },
        "aif_info": {
            "aif_version": "1.2", "aif_filing_type": "INIT", "aif_content_type": "4",
            "aif_last_reporting_flag": False,
            "aif_assumptions": [{"question_number": 50, "description": "Look-through applied"}],
            "aif_legal_form": "O", "aif_national_number": "12345678", "aif_subfund_number": "00000000",
            "aif_name": "Test AIF", "aif_eea_flag": True, "aif_reporting_code": 29,
            "aif_domicile": "LU", "aif_inception_date": date(2020, 1, 1), "aif_no_reporting_flag": False,
            "aif_lei": "5493001KJTIIGC8Y1R12",
            "aif_share_class_flag": True,
            "aif_share_classes": [{"name": "Class A", "isin": "LU0323134006", "national_code": None,
                                   "cusip": None, "sedol": None, "bloomberg": None, "reuters": None}],
            "aif_master_feeder_status": "NONE", "aif_master_aifs": [],
            "aif_prime_brokers": [{"name": "Prime Broker 1", "lei": "5493001KJTIIGC8Y1R12", "bic": None}],
            "aif_aum_base_currency": 10_000_000, "aif_base_currency": "EUR",
            "aif_fx_rate": 1.0, "aif_fx_ref_rate_type": "", "aif_nav": 9_500_000,
            "predominant_aif_type": "HFND",
            "investment_strategies": [
                {"group": "HFND", "code": "EQTY_LGST", "primary_flag": True, "nav_rate": 100,
                 "other_description": ""},
            ],
            "main_instruments": [
                {"ranking": 1, "sub_asset_type": "SEC_LEQ_IFIN", "instrument_code_type": "ISIN",
                 "instrument_name": "Instrument 1", "isin": "LU0323134006",
                 "position_value": 1_000_000, "position_type": "L", "hedging_rate": None,
                 "aii_exchange_code": None, "aii_product_code": None, "aii_derivative_type": None,
                 "aii_put_call": None, "aii_expiry_date": None, "aii_strike_price": None},
            ],
            "nav_geo_focus": {"EEA": 100},
            "aum_geo_focus": {"EEA": 100},
            "ten_principal_exposures": [
                {"ranking": 1, "macro_type": "SEC", "sub_asset_type": "SEC_LEQ_IFIN", "position_type": "L",
                 "aggregated_value": 1_000_000, "aggregated_value_pct": 50,
                 "counterparty_name": "Bank A", "counterparty_lei": "5493001KJTIIGC8Y1R12",
                 "counterparty_bic": None},
            ],
            "portfolio_concentrations": [
                {"ranking": 1, "asset_type": "SEC_LEQ", "position_type": "L", "market_code_type": "MIC",
                 "market_code": "XLUX", "aggregated_value": 1_000_000, "aggregated_value_pct": 50,
                 "counterparty_name": None, "counterparty_lei": None, "counterparty_bic": None},
            ],
            "aif_principal_markets": [
                {"ranking": 1, "market_code_type": "MIC", "market_code": "XLUX", "aggregated_value": 1_000_000},
            ],
            "investor_beneficial_owners_rate": 60, "investor_professional_rate": 100,
            "investor_retail_rate": 0, "typical_position_size": "",
            "instrument_exposures": [
                {"code": "SEC_LEQ_IFIN", "gross_value": None, "long_value": 1_000_000, "short_value": 0},
                {"code": "DER_FEX_HEDG", "gross_value": 500_000, "long_value": None, "short_value": None},
            ],
            "asset_turnovers": [{"code": "SEC_LEQ_LEQ", "market_value": 100_000, "notional_value": 0}],
            "currency_exposures": [{"currency": "USD", "long_value": 10_000, "short_value": 0}],
            "dominant_influence_companies": [],
            "annual_investment_return_rate": "5.5",
            "market_risk_measures": [
                {"code": "NET_EQTY_DELTA", "value": 1.2}, {"code": "NET_DV01", "bucket_lt5": 1},
                {"code": "NET_CS01", "bucket_lt5": 0.5}, {"code": "VEGA_EXPO", "vega_current": 2},
                {"code": "VAR", "var_value": 3, "var_method": "HISTO"},
            ],
            "trading_pct_securities_exchange": 90, "trading_pct_securities_otc": 10,
            "trading_pct_derivatives_exchange": 80, "trading_pct_derivatives_otc": 20,
            "derivatives_ccp_rate": 70, "derivatives_bilateral_rate": 30,
            "repo_ccp_rate": 50, "repo_bilateral_rate": 30, "repo_triparty_rate": 20,
            "collateral_cash_posted": 1_000, "collateral_securities_posted": 2_000,
            "collateral_other_posted": 0,
            "counterparty_exposures_to_aif": [
                {"ranking": 1, "flag": True, "name": "Bank A", "lei": None, "bic": None, "nav_pct": 3.5}],
            "counterparty_exposures_from_aif": [
                {"ranking": 1, "flag": True, "name": "Bank B", "lei": None, "bic": None, "nav_pct": 2.5}],
            "ccp_clearing_flag": True,
            "ccp_exposures": [{"ranking": 1, "name": "LCH", "lei": "5493001KJTIIGC8Y1R12",
                               "bic": None, "exposure_value": 5_000}],
            "portfolio_liquidity": {"D0_1": 100}, "unencumbered_cash": 1_000_000,
            "investor_liquidity": {"D0_1": 100},
            "provide_withdrawal_rights": True, "redemption_frequency": "M",
            "redemption_notice_period_days": 5, "redemption_lockup_period_days": 0,
            "side_pocket_rate": 1, "gates_rate": 2, "dealing_suspension_rate": 3,
            "other_arrangement_type": "", "other_arrangement_rate": None, "total_arrangement_rate": 6,
            "investor_preferential_treatment_flag": True, "pref_disclosure_flag": True,
            "pref_liquidity_flag": False, "pref_fee_flag": False, "pref_other_flag": False,
            "investor_groups": [{"code": "BANK", "rate": 40}, {"code": "PFND", "rate": 60}],
            "total_financing_amount": 500_000, "financing_buckets": {"D0_1": 100},
            "total_open_positions": 42,
            "historical_performance": [
                {"month": "October", "gross_return": 1.1, "net_return": 1.0, "nav_change": 0.9,
                 "subscriptions": 10_000, "redemptions": 5_000}],
            "stress_test_article15": "Article 15 narrative.",
            "stress_test_article16": "Article 16 narrative.",
            "rehypothecation_flag": True, "rehypothecation_rate": 25,
            "unsecured_borrowing_amount": 1_000, "secured_borrowing_prime_brokerage_amount": 2_000,
            "secured_borrowing_reverse_repo_amount": 3_000, "secured_borrowing_other_amount": 4_000,
            "exchange_traded_derivatives_exposure": 5_000, "otc_derivatives_amount": 6_000,
            "short_position_borrowed_securities_value": 7_000,
            "controlled_structures": [{"name": "SPV 1", "lei": None, "bic": None, "exposure_value": 9_000}],
            "gross_method_rate": 110, "commitment_method_rate": 105,
            "borrowing_sources": [{"ranking": 1, "flag": True, "name": "Bank C", "lei": None,
                                   "bic": None, "leverage_amount": 1_000_000}],
        },
    }
