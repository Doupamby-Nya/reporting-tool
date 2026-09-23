"""[Migrated from the Streamlit MVP's tests/test_bcl.py; the engines are
unchanged, only the imports moved from core.* to domain.*.]

Tests for the BCL module — the six reports, end to end.

    cd Backend/api
    poetry run pytest tests/test_bcl_engine.py

Three things are checked for every report:
 1. the official BCL example file validates against the bundled XSD (proving
    the schemas and the validator itself are wired correctly);
 2. what the engine generates validates against that same XSD;
 3. the business rules of the report's compendium of verification rules fire
    on data that breaks them, and stay silent on data that does not.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


from domain.bcl import bcl_engine as be
from domain.bcl import bcl_s220_engine as s220e
from domain.bcl import bcl_xsd
from domain.bcl.bcl_common import ERROR, build_filename, errors_of, filename_id_token, fmt_decimal, warnings_of

# The six official BCL example files, copied from the regulator's packages.
BCL_DIR = Path(__file__).resolve().parent / "fixtures" / "bcl_examples"


# =============================================================================
# Fixtures
# =============================================================================

def header(report_key: str, currency: str = "USD") -> be.BclHeader:
    spec = be.ALL_SPECS[report_key]
    return be.BclHeader(
        end_month_date=date(2025, 12, 31), closing_date=date(2025, 12, 31),
        reporter_type="23", reporter_code="789", declarant_type="26", declarant_code="001220003",
        reporting_currency=currency, layout=spec.layout,
    )


def ledger_rows():
    assets = [
        {"item": "1-002999", "country": "LU", "currency": "EUR", "sector": "32100", "maturity": "I000-01A", "amount": 250000},
        {"item": "1-003000", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 6305400},
        {"item": "1-005000", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 1271974},
        {"item": "1-090010", "country": "XX", "currency": "USD", "sector": "90000", "maturity": "I000-01A", "amount": -50},
        {"item": "1-000000", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 7827324},
    ]
    liabilities = [
        {"item": "2-002050", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 2360000},
        {"item": "2-004000", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 5467324},
        {"item": "2-000000", "country": "XX", "currency": "XXX", "sector": "90000", "maturity": "I999-999", "amount": 7827324},
    ]
    return assets, liabilities


def tptobs_securities():
    return [
        {"line_item": "1-003000", "code_type": "1", "isin": "USG9328DAH38", "hold_security_type": "01",
         "esa2010_type": "F.3", "quotation_type": "percent", "nominal_amount": 2000000,
         "nominal_currency": "USD", "reported_amount": 1840000},
        {"line_item": "1-003000", "code_type": "2", "other_code": "KH00546",
         "security_name": "BK US Certificate of Deposit", "security_currency": "USD",
         "issuer_lei": "0" * 20, "issuer_nationalid_type": "XX_NOTAP", "issuer_nationalid_code": "XX",
         "issuer_country": "US", "issuer_sector": "32100", "hold_security_type": "01", "esa2010_type": "F.3",
         "date_of_issue": "2024-02-15", "date_of_final_maturity": "2027-02-14", "pool_factor": 1,
         "coupon_type": "01", "coupon_frequency": "04", "last_coupon_payment_date": "2025-11-15",
         "coupon_rate": 1.5, "quotation_type": "percent", "nominal_amount": 4500000,
         "nominal_currency": "USD", "reported_amount": 4465400},
        {"line_item": "1-005000", "code_type": "1", "isin": "LU0323134006", "hold_security_type": "01",
         "esa2010_type": "F.52", "quotation_type": "currency", "number_of_units": 100000,
         "reported_amount": 1230000},
        {"line_item": "1-005000", "code_type": "2", "other_code": "B123456", "security_name": "Reporting SARL",
         "security_currency": "EUR", "issuer_lei": "0" * 20, "issuer_nationalid_type": "XX_NOTAP",
         "issuer_nationalid_code": "XX", "issuer_country": "LU", "issuer_sector": "42900",
         "hold_security_type": "01", "esa2010_type": "F.519", "quotation_type": "currency",
         "number_of_units": 31000, "reported_amount": 41974},
        {"line_item": "2-002050", "code_type": "1", "isin": "US92343VBH69", "hold_security_type": "05",
         "esa2010_type": "F.3", "quotation_type": "percent", "nominal_amount": 2500000,
         "nominal_currency": "USD", "reported_amount": 2360000},
        {"line_item": "2-004000", "code_type": "1", "isin": "LU9876543414", "hold_security_type": "04",
         "esa2010_type": "F.52", "quotation_type": "currency", "number_of_units": 10000,
         "reported_amount": 2733662, "cssf_class_code": "0001", "issue_currency": "USD",
         "distributed_amount": 0, "split_date": "2008-12-31", "split_ratio": 1},
        {"line_item": "2-004000", "code_type": "2", "other_code": "INTERNAL01", "security_name": "Class B",
         "security_currency": "EUR", "issuer_lei": "0" * 20, "issuer_nationalid_type": "XX_NOTAP",
         "issuer_nationalid_code": "XX", "issuer_country": "LU", "issuer_sector": "41000",
         "hold_security_type": "04", "esa2010_type": "F.52", "quotation_type": "currency",
         "number_of_units": 10005, "reported_amount": 2733662, "cssf_class_code": "0002",
         "issue_currency": "EUR", "distributed_amount": 0, "split_date": "2008-12-31", "split_ratio": 1},
    ]


def tptobs_lines(securities):
    return (be_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_ASSETS),
            be_lines(securities, be.TPTOBS_BREAKDOWN_SPECS_LIABILITIES))


def be_lines(securities, specs):
    lines = []
    for spec in specs:
        group = be.securities_of(securities, spec["item"])
        if group:
            lines.append({"item": spec["item"], "country": "XX", "currency": "XXX", "sector": "90000",
                          "amount": float(be.line_total(group))})
    return lines


def s220_submission() -> s220e.S220Submission:
    share_class = s220e.ShareClass(
        cssf_code="0001", name="CAP", base_currency="EUR", isin="LU0323134006",
        launch_date=date(2021, 1, 4), spec_instr_fx=True, investor_base=3,
        units_outstanding=1000, nav_per_unit_fund_currency=100, nav_per_unit_shareclass_currency=100,
        net_return=1.5, units_issued=0, units_redeemed=0, distributions=0,
        distributions_per_unit_fund_currency=0, distributions_per_unit_shareclass_currency=0,
        income_fund_currency=600, expenses_fund_currency=500,
    )
    return s220e.S220Submission(
        reference_month="202512", reporting_status=s220e.STATUS_FINAL,
        sender_type="23", sender_code="341",
        sender_employees=[{"name": "John Doe", "phone": "0000000000", "email": "john.doe@test.lu"}],
        declarant_type="42", declarant_code="66012345600001", uci_name="Fund - A",
        uci_base_currency="EUR", uci_lei="5493001KJTIIGC8Y1R12",
        valuation_date=date(2025, 12, 31), nav_freq=13, nav_redemption_freq=4, open_closed_end=1,
        launch_date=date(2021, 1, 4),
        nav_preceding_ref_month=99900, nav_ref_month=100000,
        units_issued=0, units_redeemed=0, total_distributions=0,
        share_classes=[share_class],
        dividends_on_shares=600, dividends_on_shares_lu=100, dividends_on_uci_units=0,
        dividends_on_uci_units_lu=0, interest_bonds=0, interest_bonds_lu=0, interest_loans_banks=0,
        bank_interest=0, bank_interest_lu=0, other_interest=0, other_interest_lu=0, other_income=0,
        rental_income=0, commission_income=0, other_income_other=0,
        charges=500, advisory_management_fees=500, depositary_bank_fees=0, administration_fees=0,
        audit_inspection_fees=0, distribution_fees=0, other_administrative_expenses=0,
        subscription_tax=0, other_taxes=0, performance_fees=0, other_expenses=0, interest_paid=0,
        personnel_expenses=0, rental_expenses=0, amortisation=0, other_expenses_other=0,
        net_realised=0, net_unrealised=0,
    )


def assert_valid(xml: str, report_key: str) -> None:
    result = bcl_xsd.validate(xml, report_key)
    assert result.available, "lxml is required to run these tests"
    assert result.valid, f"{report_key} is invalid against its XSD:\n" + "\n".join(result.errors[:5])


# =============================================================================
# 1. The official examples validate against the bundled schemas
# =============================================================================

def test_official_examples_validate():
    examples = sorted(BCL_DIR.glob("*.xml"))
    assert len(examples) == 6, f"expected the six official BCL examples, found {len(examples)}"
    for path in examples:
        raw = path.read_bytes()
        report_key = bcl_xsd.detect_report(raw)
        assert report_key is not None, f"{path.name} was not identified as a BCL report"
        result = bcl_xsd.validate(raw, report_key)
        assert result.valid, f"{path.name} ({report_key}) is invalid:\n" + "\n".join(result.errors[:5])


def test_detect_report_rejects_a_foreign_document():
    assert bcl_xsd.detect_report(b"<html><body>not a report</body></html>") is None
    assert bcl_xsd.detect_report(b"<not-xml") is None
    result = bcl_xsd.validate(b"<foo xmlns='urn:x'/>")
    assert not result.valid and "Unrecognised root element" in result.errors[0]


# =============================================================================
# 2. Every report generates a document valid against its own XSD
# =============================================================================

def test_s13_and_s213_and_s16_generate_valid_xml():
    assets, liabilities = ledger_rows()
    for report_key in ("s13", "s213"):
        xml = be.build_ledger_xml(report_key, header(report_key), assets, liabilities)
        assert_valid(xml, report_key)
        assert not errors_of(be.validate_ledger(assets, liabilities, report_key, header(report_key)))

    s16_assets = [{"item": "1-007000", "country": "XX", "currency": "XXX", "sector": "90000",
                   "maturity": "I999-999", "amount": 30}]
    xml = be.build_ledger_xml("s16", header("s16"), s16_assets, [])
    assert_valid(xml, "s16")
    assert not errors_of(be.validate_ledger(s16_assets, [], "s16", header("s16")))


def test_each_report_uses_its_own_root_and_namespace():
    """The S 2.13 regression: it used to be emitted as <S13> in the S 1.3
    namespace, which BCL's own validator rejects outright."""
    assets, liabilities = ledger_rows()
    expected = {"s13": ("S13", "http://www.bcl.lu/2008/S1.3"),
                "s213": ("S213", "http://www.bcl.lu/2008/S2.13"),
                "s16": ("S16", "http://www.bcl.lu/2008/S1.6")}
    for report_key, (root, namespace) in expected.items():
        xml = be.build_ledger_xml(report_key, header(report_key), assets, liabilities)
        assert xml.splitlines()[1].startswith(f"<{root} xmlns=\"{namespace}\""), xml.splitlines()[1]
        assert bcl_xsd.detect_report(xml) == report_key


def test_layout_is_fixed_per_report():
    assets, liabilities = ledger_rows()
    for report_key, layout in (("s13", 4), ("s213", 2), ("s16", 2)):
        xml = be.build_ledger_xml(report_key, header(report_key), assets, liabilities)
        assert f"<layout>{layout}</layout>" in xml
    wrong = header("s13")
    wrong.layout = 2
    issues = be.validate_ledger(assets, liabilities, "s13", wrong)
    assert any(i.code == "HDR-010" for i in errors_of(issues))


def test_s44_generates_valid_xml():
    rows = [{"item": "2-004000", "country": "LU", "amount": 50},
            {"item": "2-004000", "country": "BE", "amount": 50}]
    xml = be.build_s44_xml(header("s44"), rows)
    assert_valid(xml, "s44")
    assert not errors_of(be.validate_s44(rows, header("s44")))
    assert "<dataType>PCT</dataType>" in xml


def test_tptobs_generates_valid_xml():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    xml = be.build_tptobs_xml(header("tptobs"), assets, liabilities, securities)
    assert_valid(xml, "tptobs")
    assert not errors_of(be.validate_tptobs(assets, liabilities, securities, header("tptobs")))
    # An ISIN security carries no <issuerID>; a non-ISIN one does.
    assert xml.count("<issuerID>") == 3
    # Own shares issued go under <typeOfShare>, never <equity>.
    assert "<typeOfShare>" in xml and "<cssfCode>0001</cssfCode>" in xml


def test_tptobs_quotation_shapes():
    """A security quoted in % carries nominalAmount + nominalCurrency; one
    quoted in currency carries numberOfUnits. The old engine emitted a
    <percentage><value> element that exists in no BCL schema."""
    import xml.etree.ElementTree as ET

    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    document = be.build_tptobs_xml(header("tptobs"), assets, liabilities, securities)
    assert "<percentage>" not in document and "<value>" not in document

    ns = {"s": be.TPTOBS_SPEC.namespace}
    root = ET.fromstring(document)
    percent = root.findall(".//s:percentageQuoted", ns)
    currency = root.findall(".//s:currencyQuoted", ns)
    assert percent and currency
    def children(node):
        return [c.tag.rpartition("}")[2] for c in node]

    for node in percent:
        assert children(node) == ["nominalAmount", "nominalCurrency"]
    for node in currency:
        assert children(node) == ["numberOfUnits"]


def test_s220_generates_valid_xml():
    sub = s220_submission()
    xml = s220e.build_s220_xml(sub)
    assert_valid(xml, "s220")
    assert not errors_of(s220e.validation_issues(sub))


def test_s220_null_report_omits_the_financial_sections():
    sub = s220_submission()
    sub.reporting_status = s220e.STATUS_NULL
    xml = s220e.build_s220_xml(sub)
    assert_valid(xml, "s220")
    assert "<UCIFinancialInformation>" not in xml
    assert "<UCI_Inv_Income_and_Expenses>" not in xml


def test_s220_blank_amounts_become_zero_not_empty_elements():
    """The S 2.20 regression: a blank amount used to be omitted, leaving the
    schema's mandatory children missing and the document invalid."""
    sub = s220_submission()
    sub.rental_income = None
    sub.commission_income = None
    sub.other_income_other = None
    xml = s220e.build_s220_xml(sub)
    assert_valid(xml, "s220")
    assert "<RentalIncome>0</RentalIncome>" in xml
    assert "<RentalIncome></RentalIncome>" not in xml


# =============================================================================
# 3. Business rules
# =============================================================================

def test_ledger_total_must_match_and_balance():
    assets, liabilities = ledger_rows()
    unbalanced = [dict(r) for r in liabilities]
    unbalanced[-1]["amount"] = 999
    codes = {i.code for i in errors_of(be.validate_ledger(assets, unbalanced, "s13", header("s13")))}
    assert "LED-015" in codes


def test_ledger_rejects_a_breakdown_on_a_no_breakdown_line():
    assets, liabilities = ledger_rows()
    broken = [dict(r) for r in assets]
    broken[1]["country"] = "LU"  # 1-003000 is fixed at XX
    codes = {i.code for i in errors_of(be.validate_ledger(broken, liabilities, "s13", header("s13")))}
    assert "LED-006" in codes


def test_ledger_requires_a_breakdown_where_the_chart_demands_one():
    assets, liabilities = ledger_rows()
    broken = [dict(r) for r in assets]
    broken[0]["country"] = "XX"  # 1-002999 is marked (1)
    codes = {i.code for i in errors_of(be.validate_ledger(broken, liabilities, "s13", header("s13")))}
    assert "LED-004" in codes


def test_ledger_rejects_a_duplicate_line():
    assets, liabilities = ledger_rows()
    duplicated = assets + [dict(assets[0])]
    codes = {i.code for i in errors_of(be.validate_ledger(duplicated, liabilities, "s13", header("s13")))}
    assert "LED-002" in codes


def test_ledger_rejects_a_negative_amount_where_no_debit_is_allowed():
    assets, liabilities = ledger_rows()
    broken = [dict(r) for r in assets]
    broken[0]["amount"] = -1
    codes = {i.code for i in errors_of(be.validate_ledger(broken, liabilities, "s13", header("s13")))}
    assert "LED-008" in codes
    # ... but 1-090010 may be negative, as the fixture already is.
    assert not any(i.code == "LED-008" for i in errors_of(
        be.validate_ledger(assets, liabilities, "s13", header("s13"))))


def test_s44_percentages_must_add_up_to_100_and_be_unique():
    short = [{"item": "2-004000", "country": "LU", "amount": 60}]
    assert "S44-010" in {i.code for i in errors_of(be.validate_s44(short, header("s44")))}

    duplicated = [{"item": "2-004000", "country": "LU", "amount": 50},
                  {"item": "2-004000", "country": "LU", "amount": 50}]
    assert "S44-007" in {i.code for i in errors_of(be.validate_s44(duplicated, header("s44")))}

    unknown = [{"item": "2-004000", "country": "XX", "amount": 100}]
    assert "S44-006" in {i.code for i in errors_of(be.validate_s44(unknown, header("s44")))}


def test_tptobs_holding_and_security_type_are_restricted_per_line():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)

    wrong_holding = [dict(s) for s in securities]
    wrong_holding[0]["hold_security_type"] = "04"  # not allowed on 1-003000
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, wrong_holding, header("tptobs")))}
    assert "TPT-022" in codes

    wrong_type = [dict(s) for s in securities]
    wrong_type[0]["esa2010_type"] = "F.511"  # 1-003000 only accepts F.3
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, wrong_type, header("tptobs")))}
    assert "TPT-024" in codes


def test_tptobs_rejects_a_bad_isin():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    broken = [dict(s) for s in securities]
    broken[0]["isin"] = "USG9328DAH39"  # wrong check digit
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, broken, header("tptobs")))}
    assert "TPT-004" in codes

    broken[0]["isin"] = "XX0000000000"  # forbidden prefix
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, broken, header("tptobs")))}
    assert "TPT-003" in codes


def test_tptobs_line_total_must_equal_the_sum_of_its_securities():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    assets[0]["amount"] = 1
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, securities, header("tptobs")))}
    assert "TPT-064" in codes


def test_tptobs_own_securities_issued_must_be_luxembourg_funds():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    broken = [dict(s) for s in securities]
    broken[-1] = dict(broken[-1], issuer_country="FR", issuer_sector="21000")
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, broken, header("tptobs")))}
    assert "TPT-018" in codes and "TPT-019" in codes


def test_tptobs_zero_coupon_type_and_frequency_go_together():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    broken = [dict(s) for s in securities]
    broken[1] = dict(broken[1], coupon_type="04", coupon_frequency="01")
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, broken, header("tptobs")))}
    assert "TPT-045" in codes


def test_tptobs_orphan_security_is_reported():
    securities = tptobs_securities()
    assets, liabilities = tptobs_lines(securities)
    orphan = securities + [dict(securities[0], line_item="1-006011")]
    codes = {i.code for i in errors_of(be.validate_tptobs(assets, liabilities, orphan, header("tptobs")))}
    assert "TPT-066" in codes


def test_s220_nav_roll_forward_and_arithmetic_rules():
    sub = s220_submission()
    sub.nav_ref_month = 123456
    codes = {i.code for i in warnings_of(s220e.validation_issues(sub))}
    assert "R3020A" in codes and "R3020B" in codes

    sub = s220_submission()
    sub.charges = 999  # no longer the sum of 6061..6068
    assert "R6060A" in {i.code for i in warnings_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.dividends_on_shares_lu = 10_000  # greater than 6010
    assert "R6011A" in {i.code for i in warnings_of(s220e.validation_issues(sub))}


def test_s220_mandatory_fields_and_codes():
    sub = s220_submission()
    sub.declarant_code = "123"
    assert "R2012" in {i.code for i in errors_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.declarant_type = "26"
    assert "RNOM20" in {i.code for i in errors_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.reference_month = "202511"  # before the first accepted period
    assert "R1010B" in {i.code for i in errors_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.reference_month = "202601"  # valid, but not a quarter end
    assert "R1010C" in {i.code for i in warnings_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.sender_employees = []
    assert "R1040" in {i.code for i in errors_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.share_classes[0].cssf_code = "1"
    assert "R4010" in {i.code for i in errors_of(s220e.validation_issues(sub))}

    sub = s220_submission()
    sub.launch_date = date(2026, 6, 1)  # after the valuation date
    assert "R2070A" in {i.code for i in errors_of(s220e.validation_issues(sub))}


def test_s220_duplicate_share_class_code():
    sub = s220_submission()
    sub.share_classes.append(s220e.ShareClass(**{**sub.share_classes[0].__dict__}))
    assert "R4010U" in {i.code for i in errors_of(s220e.validation_issues(sub))}


# =============================================================================
# 4. Cross-report checks
# =============================================================================

def test_cross_check_ledger_vs_tptobs():
    assets, liabilities = ledger_rows()
    securities = tptobs_securities()
    tpt_assets, tpt_liabilities = tptobs_lines(securities)
    issues = be.cross_check_ledger_vs_tptobs(assets, liabilities, tpt_assets, tpt_liabilities, securities)
    # The fixture is built to agree on 1-003000, 1-005000, 2-002050 and 2-004000.
    assert not [i for i in issues if i.code == "XCHK-003"], [str(i) for i in issues]

    broken = [dict(r) for r in assets]
    broken[1]["amount"] = 1
    issues = be.cross_check_ledger_vs_tptobs(broken, liabilities, tpt_assets, tpt_liabilities, securities)
    assert "XCHK-003" in {i.code for i in issues}


def test_cross_check_ledger_vs_s220():
    _, liabilities = ledger_rows()
    assert not be.cross_check_ledger_vs_s220(liabilities, 5467324)
    assert "XCHK-004" in {i.code for i in be.cross_check_ledger_vs_s220(liabilities, 1)}


def test_cross_check_s220_vs_tptobs():
    sub = s220_submission()
    securities = tptobs_securities()
    codes = {i.code for i in s220e.cross_check_s220_vs_tptobs(sub, securities)}
    # Class 0001 is reported in USD in TPTOBS but EUR in S 2.20, and the NAV differs.
    assert "XS220-003" in codes


# =============================================================================
# 5. File naming and number formatting
# =============================================================================

def test_file_names_follow_the_bcl_convention():
    assert be.ledger_filename("s13", header("s13"), date(2026, 1, 5)) == \
        "S0103_L4_202512_B000000789_O001220003_20260105_001.xml"
    assert be.ledger_filename("s213", header("s213"), date(2026, 1, 5)).startswith("S0213_L2_202512_")
    assert be.ledger_filename("s16", header("s16"), date(2026, 1, 5)).startswith("S0106_L2_202512_")
    assert be.s44_filename(header("s44"), date(2026, 1, 5)).startswith("S0404_L0_202512_")
    assert be.tptobs_filename(header("tptobs"), date(2026, 1, 5)).startswith("TPTOBS_L3_202512_")
    assert s220_submission().filename(date(2025, 7, 1)) == \
        "S0220_L0_202512_B000000341_NAF66012345600001_20250701_001.xml"


def test_s220_file_name_matches_bcls_published_regex():
    from domain.bcl.bcl_common import filename_regex
    name = s220_submission().filename(date(2025, 7, 1))
    assert filename_regex("S0220").fullmatch(name), name


def test_filename_tokens():
    assert filename_id_token("23", "789") == "B000000789"
    assert filename_id_token("42", "66012345600001", role="declarant") == "NAF66012345600001"
    assert filename_id_token("26", "001220003") == "O001220003"


def test_amount_formatting_is_exact_and_bounded():
    assert fmt_decimal(0.1 + 0.2, 5) == "0.3"
    assert fmt_decimal("1e-7", 5) == "0"
    assert fmt_decimal(1234567890123456, 5) == "1234567890123456"
    assert fmt_decimal("2.000000", 5) == "2"
    assert fmt_decimal(-0.000001, 5) == "0"
    assert fmt_decimal(None, 5) is None
    assert fmt_decimal(5.5, 2, fixed=True) == "5.50"


def test_generated_amounts_never_use_exponent_notation():
    assets, liabilities = ledger_rows()
    big = [dict(r) for r in assets]
    big[0]["amount"] = 1e20
    big[-1]["amount"] = 1e20 + 6305400 + 1271974 - 50
    liabilities = [dict(r) for r in liabilities]
    liabilities[-1]["amount"] = big[-1]["amount"]
    liabilities[1]["amount"] = big[-1]["amount"] - 2360000
    xml = be.build_ledger_xml("s13", header("s13"), big, liabilities)
    assert "e+" not in xml.lower()
    assert_valid(xml, "s13")


def test_xml_escaping():
    sub = s220_submission()
    sub.uci_name = 'Fund <A> & "B"'
    xml = s220e.build_s220_xml(sub)
    assert "&lt;A&gt; &amp;" in xml
    assert_valid(xml, "s220")


