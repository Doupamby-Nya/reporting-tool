"""U 1.1 — which XML element every captured field is tagged to.

Each path below is copied directly from ``urr_engine.build_u11_xml``, whose
element names and nesting come from a real CSSF example workbook
(version 5.1 - 12/2025 of the U 1.1 reporting spec, Circular CSSF 15/627)
rather than being guessed.

A leading ``.../`` abbreviates the repeating parent block the row sits in —
one ``Unit_Share_Information`` per share class, and the detail blocks of
``UCI_Inv_Income_and_Expenses`` — so the table reads as the schema does.

This is reference data about the filing, not presentation: it lives here so
the rules-engine screen and the generator quote one source.
"""

from __future__ import annotations

FUND_INFO_XML_MAP: dict[str, str] = {
    "reference_month": "GeneralInformation/ReferenceMonth",
    "reporting_status": "GeneralInformation/ReportingStatus",
    "sender_cssf_code": "GeneralInformation/SenderCssfCode",
    "employee_name": "GeneralInformation/SenderInformations/SenderInformation/NameOfEmployee",
    "employee_phone": "GeneralInformation/SenderInformations/SenderInformation/PhoneNumber",
    "sender_email": "GeneralInformation/SenderInformations/SenderInformation/EmailAdress",
    "uci_cssf_code": "UCIGeneralInformation/UCISignaBasic/UCICssfCode",
    "uci_name": "UCIGeneralInformation/UCISignaBasic/UCIName",
    "uci_currency": "UCIGeneralInformation/UCISignaBasic/UCIBaseCurrency",
    "lei": "UCIGeneralInformation/UCISignaBasic/LEI",
    "valuation_date": "UCIGeneralInformation/UCISignaDate/ValuationDate",
    "nav_frequency": "UCIGeneralInformation/UCISignaDate/NavInformation/NavFreq",
    "launch_date": "UCIGeneralInformation/UCISignaDate/LaunchDate",
    "closing_date": "UCIGeneralInformation/UCISignaDate/ClosingDate",
    "closing_reason": "UCIGeneralInformation/UCISignaDate/ReasonForClosing",
    "redemption_frequency": "UCIGeneralInformation/UCISignaDate/NavInformation/NavRedemptionFreq",
    "open_closed_end": "UCIGeneralInformation/UCISignaDate/NavInformation/OpenClosedEnd",
    "nav_preceding_month": "UCIFinancialInformation/NAVPrecedingRefMonth",
    "nav_this_month": "UCIFinancialInformation/NAVRefMonth",
    "proceeds_issued": "UCIFinancialInformation/TotUnitsOrSharesIssued",
    "payments_redeemed": "UCIFinancialInformation/TotUnitsOrSharesRedeemed",
    "total_distributions": "UCIFinancialInformation/TotalDistributions",
}

SHARE_CLASS_XML_MAP: dict[str, str] = {
    "cssf_code": "Unit_Share_Informations/Unit_Share_Information/CssfCode",
    "name": ".../UnitShareClassGeneralInformation/Unit_ShareClass_Name",
    "currency": ".../UnitShareClassGeneralInformation/BaseCurrency",
    "isin": ".../UnitShareClassGeneralInformation/ISINCode",
    "launch_date": ".../UnitShareClassGeneralInformation/LaunchDate",
    "closing_date": ".../UnitShareClassGeneralInformation/ClosingDate",
    "closing_reason": ".../UnitShareClassGeneralInformation/ReasonForClosing",
    "spec_fx": ".../UnitShareClassGeneralInformation/Unit_ShareClass_SpecInstr_FX",
    "spec_ir": ".../UnitShareClassGeneralInformation/Unit_ShareClass_SpecInstr_InterestRate",
    "spec_other": ".../UnitShareClassGeneralInformation/Unit_ShareClass_SpecInstr_Other",
    "investor_base": ".../UnitShareClassGeneralInformation/InvestorBase",
    "units_outstanding": ".../UnitShareClassFinancialInformation/NumberUnitOrShareOutstanding",
    "nav_per_unit_uci_ccy": ".../UnitShareClassFinancialInformation/NetAssetValueInSubFundCurrency",
    "nav_per_unit_class_ccy": ".../UnitShareClassFinancialInformation/NetAssetValueInShareClassCurrency",
    "net_return_pct": ".../UnitShareClassFinancialInformation/NetReturn",
    "units_issued": ".../UnitShareClassFinancialInformation/UnitOrSharesIssued",
    "units_redeemed": ".../UnitShareClassFinancialInformation/UnitOrSharesRedeemed",
    "distributions": ".../UnitShareClassFinancialInformation/Distributions",
    "distrib_per_unit_uci_ccy": ".../UnitShareClassFinancialInformation/AmountDistributionsInUCICurrency",
    "distrib_per_unit_class_ccy": ".../UnitShareClassFinancialInformation/AmountDistributionsInShareClassCurrency",
    "income_uci_ccy": ".../UnitShareClassFinancialInformation/IncomeInFundCurrency",
    "expenses_uci_ccy": ".../UnitShareClassFinancialInformation/ExpensesInFundCurrency",
}

INCOME_XML_MAP: dict[str, str] = {
    "dividends_shares": "UCI_Inv_Income_and_Expenses/DividendsOnShares/DividendsOnShares",
    "dividends_shares_lu": ".../DividendsOnShares/DivShOfWhichFromLu",
    "dividends_uci_units": "UCI_Inv_Income_and_Expenses/DividendsOnUCI_Units_Shares/DividendsOnUCI_Units_Shares",
    "dividends_uci_units_lu": ".../DividendsOnUCI_Units_Shares/DivUCIOfWhichFromLu",
    "interest_bonds": "UCI_Inv_Income_and_Expenses/Interest/Interest_bonds_debt_securities",
    "interest_bonds_lu": ".../Interest/DivIntBondsOfWhichFromLu",
    "interest_loans_banks": "UCI_Inv_Income_and_Expenses/InterestLoansBanksBearingAccounts",
    "bank_interest": "UCI_Inv_Income_and_Expenses/BankInterest/BankInterest",
    "bank_interest_lu": ".../BankInterest/BankIntOfWhichFromLu",
    "other_interest": "UCI_Inv_Income_and_Expenses/OtherInterest/OtherInterest",
    "other_interest_lu": ".../OtherInterest/OtherIntOfWhichFromLu",
    "other_income": "UCI_Inv_Income_and_Expenses/OtherIncome",
    "rental_income": "UCI_Inv_Income_and_Expenses/OtherIncomeDetails/RentalIncome",
    "commission_income": ".../OtherIncomeDetails/CommissionIncome",
    "other_income_other": ".../OtherIncomeDetails/OtherOfWhichFromOtherIncome",
    "charges": "UCI_Inv_Income_and_Expenses/Charges",
    "advisory_mgmt_fees": "UCI_Inv_Income_and_Expenses/ChargesDetails/AdvisoryManagementFees",
    "depositary_fees": ".../ChargesDetails/DepositaryBankFees",
    "admin_fees": ".../ChargesDetails/AdministrationFees",
    "audit_fees": ".../ChargesDetails/AuditInspectionFees",
    "distribution_fees": ".../ChargesDetails/DistributionFees",
    "other_admin_expenses": ".../ChargesDetails/OtherAdministrativeExpenses",
    "subscription_tax": ".../ChargesDetails/SubscriptionTax",
    "other_taxes": ".../ChargesDetails/OtherTaxes",
    "performance_fees": "UCI_Inv_Income_and_Expenses/PerformanceFees",
    "other_expenses": "UCI_Inv_Income_and_Expenses/OtherExpenses",
    "interest_paid": "UCI_Inv_Income_and_Expenses/OtherExpensesDetails/InterestPaid",
    "personnel_expenses": ".../OtherExpensesDetails/PersonnelExpenses",
    "rental_expenses": ".../OtherExpensesDetails/RentalExpenses",
    "amortisation": ".../OtherExpensesDetails/Amortisation",
    "other_expenses_other": ".../OtherExpensesDetails/OtherOfWhichFromOtherExpenses",
    "net_realised": "UCI_Inv_Income_and_Expenses/NetRealised",
    "net_unrealised": "UCI_Inv_Income_and_Expenses/NetUnrealised",
}
