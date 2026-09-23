"""SAQ (Self-Assessment Questionnaire) tracker — Circular CSSF 21/790.

Circular CSSF 21/790, "Practical rules concerning the self-assessment
questionnaire to be submitted annually by Luxembourg undertakings for
collective investment" (17 December 2021, repeals Circular CSSF 02/81), is
the real basis for the SAQ — grounded here from the actual circular text
(PDF at data/regulation/saq/CSSF_21_790_SAQ_Practical_Rules.pdf). It is
genuinely unrelated to Circular CSSF 02/77 ("Protection of investors in
case of NAV calculation error...", itself repealed and replaced by Circular
CSSF 24/856 from 1 January 2025) — two distinct circulars covering
unrelated topics.

Scope of this engine: the SAQ is filed by UCI "dirigeants" as a structured
questionnaire directly on CSSF's eDesk portal (CISERO module) — the
questionnaire's own exact question wording is not publicly published
(it lives behind eDesk's authentication). What IS real and genuinely
public, and used to build SAQ_SECTIONS/SAQ_QUESTIONS below, is the CSSF's
own "Self-Assessment Questionnaire, Separate Report and Management Letter
for Funds — CSSF Feedback Report" (PDF at
data/regulation/saq/CSSF_SAQ_Feedback_Report.pdf, downloaded from
cssf.lu/wp-content/uploads/Feedback-Report-Reports-Circular-CSSF-21-790.pdf) —
a public document in which the CSSF describes, section by section, the
real topic structure of the SAQ (7 sections, ~19 predefined sub-topics) and
what it expects to find for each, based on its actual review of thousands
of submitted questionnaires. Every question below is grounded in that
document's own wording of what the SAQ assesses (paraphrased into a
closed-ended self-assessment question, since the report describes findings
rather than quoting the question text itself) plus the underlying legal
provision(s) it cites — not invented, but also not a verbatim reproduction
of eDesk's own question text, which remains unverifiable without portal
access. The applicability scope, the real submission deadlines (3 months
after financial year-end for UCITS, 4 months for the others, per Section
2.1 of the circular) and the "dirigeants must review and validate before
submission" requirement come directly from the circular itself. The
Generation step produces an internal self-assessment summary (for
four-eyes review and record-keeping) rather than a machine-readable
report — the SAQ itself is still filed manually via eDesk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, timedelta

# Section 1 ("Scope and legal basis") of Circular CSSF 21/790 — label and
# the submission deadline in months after financial year-end (Section 2.1).
UCI_TYPES: dict[str, tuple[str, int]] = {
    "UCITS": ("UCITS (Part I of the UCI Law)", 3),
    "PART_II": ("UCI subject to Part II of the UCI Law", 4),
    "SIF": ("Specialised Investment Fund (SIF Law)", 4),
    "SICAR": ("Investment company in risk capital (SICAR Law)", 4),
}

# The 7 real top-level sections of the SAQ, per the Table of Contents of the
# CSSF Feedback Report (Section II, "Observations").
SAQ_SECTIONS: list[tuple[str, str]] = [
    ("organisation", "1. Organisation of the Fund"),
    ("investment_compliance", "2. Investment Compliance"),
    ("valuation", "3. Valuation"),
    ("nav_determination", "4. NAV determination"),
    ("expenses", "5. Expenses"),
    ("depositary", "6. Relationship with depositary"),
    ("disclosures", "7. Disclosures"),
]

_YES_NO_NA = ["—", "Yes", "No", "N/A"]

# Every question is grounded in the CSSF Feedback Report's own description
# of what it observed/expects for that real SAQ sub-topic (see module
# docstring), plus the underlying legal provision(s) it cites in that
# section. "options" defaults to a Yes/No/N/A self-assessment answer unless
# overridden (accounting_standard is a real multiple-choice item).
SAQ_QUESTIONS: list[dict] = [
    # 1. Organisation of the Fund
    {
        "key": "formal_meetings", "section": "organisation",
        "question": "Do the dirigeants hold formal meetings at a frequency adequate for the UCI's activity "
                     "(at least quarterly for open-ended UCIs), covering all key oversight topics (portfolio "
                     "management, oversight of delegates/IFM, valuation, capital transactions, conflicts of "
                     "interest, regulatory developments, relationship with depositary)?",
        "citation": "Feedback Report §1.2.1 (Formal meetings of the dirigeants of UCIs)",
    },
    {
        "key": "conflicts_of_interest", "section": "organisation",
        "question": "Does the UCI have an effective conflicts of interest policy and procedures in place — "
                     "taking into account the policies of the appointed IFM where applicable — to identify and "
                     "manage conflicts of interest entailing a material risk of damage to the UCI or its investors?",
        "citation": "Feedback Report §1.2.2 (Conflicts of interest); CSSF Reg. 10-4 Art. 20; CDR 231/2013 Art. 31",
    },
    {
        "key": "well_informed_investors", "section": "organisation",
        "question": "For SIFs/SICARs: are procedures in place to verify that all investors — including in "
                     "closed-ended sub-funds — qualify as well-informed investors?",
        "citation": "Feedback Report §1.2.3 (Investors in UCIs, SIFs and SICARs); SIF Law Art. 2; SICAR Law Art. 2",
    },
    # 2. Investment Compliance
    {
        "key": "breach_policy", "section": "investment_compliance",
        "question": "Is there a formalised policy covering the treatment of active and passive investment "
                     "breaches that may occur at (sub-)fund level?",
        "citation": "Feedback Report §2.1 (Treatment of active and passive breaches); Circular CSSF 24/856",
    },
    {
        "key": "compliance_control_framework", "section": "investment_compliance",
        "question": "Is there a materialised (standardised and/or IT-backed manual or automated) ex-post "
                     "investment compliance control framework covering all legal, regulatory and contractual "
                     "investment restrictions applicable to the UCI, including SFDR investment rules?",
        "citation": "Feedback Report §2.2 (Investment compliance control framework)",
    },
    {
        "key": "trash_ratio_controls", "section": "investment_compliance",
        "question": "For UCITS investing in securities under the 'trash ratio' (Article 41(2)(a) UCI Law): are "
                     "documented pre-trade liquidity analyses and forecasts performed, and compliance verified, "
                     "before investing in such securities?",
        "citation": "Feedback Report §2.3 (Eligibility requirements for investments by UCITS); UCI Law Art. 41(2)(a); CSSF Reg. 10-4 Art. 26",
    },
    # 3. Valuation
    {
        "key": "valuation_policy_approval", "section": "valuation",
        "question": "Have the dirigeants formally approved (e.g. board minutes/resolution) the valuation "
                     "policies and procedures applicable to the UCI, going beyond the mere approval of the "
                     "prospectus provisions?",
        "citation": "Feedback Report §3.1.1 (Formal approval of the valuation policy/procedures)",
    },
    {
        "key": "valuation_escalation", "section": "valuation",
        "question": "Is there a formal escalation process to the dirigeants for significant (UCI-specific or "
                     "market-driven) valuation issues that may impact investors' interests?",
        "citation": "Feedback Report §3.1.2 (Escalation process of material valuation issues)",
    },
    {
        "key": "valuation_frequency_alignment", "section": "valuation",
        "question": "For open-ended UCIs: is the valuation frequency of investments aligned with the frequency "
                     "of the net asset value determination?",
        "citation": "Feedback Report §3.1.3 (Valuation frequency of investments of the UCIs); CDR 231/2013 Art. 74",
    },
    {
        "key": "arms_length_transactions", "section": "valuation",
        "question": "Is there a documented procedure ensuring that transactions on quoted and unquoted "
                     "investments (including FDIs) concluded with related parties to the UCI are done on an "
                     "arm's length basis?",
        "citation": "Feedback Report §3.1.4 (Arm's length character of transactions)",
    },
    {
        "key": "independent_valuation_source", "section": "valuation",
        "question": "For investments valued on the basis of prices/valuations obtained from a source which is "
                     "not independent (e.g. issuer-provided prices for structured products): are cross-checks "
                     "or reasonableness tests performed to ensure a reliable, independent valuation?",
        "citation": "Feedback Report §3.1.5 (Independent valuation source)",
    },
    {
        "key": "modified_audit_opinion", "section": "valuation",
        "question": "Did the statutory auditor issue a modified audit opinion and/or raise management letter "
                     "observations for this UCI in the reporting period?",
        "citation": "Feedback Report §3.2 (Modified audit opinions and Management letter observations); Circular CSSF 21/790 §2.2",
    },
    # 4. NAV determination
    {
        "key": "accounting_standard", "section": "nav_determination",
        "question": "Which accounting standard does the UCI apply for the preparation of its annual report?",
        "citation": "Feedback Report §4.1 (Accounting standards)",
        "options": ["—", "Lux GAAP", "IFRS", "Other"],
    },
    {
        "key": "market_timing_assessment", "section": "nav_determination",
        "question": "Has a specific, documented assessment of market timing risk been performed for each "
                     "active sub-fund — upon launch or upon material changes to its exposure profile — beyond "
                     "general coverage of the risk in the prospectus?",
        "citation": "Feedback Report §4.2 (Market timing); Circular CSSF 04/146",
    },
    {
        "key": "lmt_policy", "section": "nav_determination",
        "question": "Does the UCI have a documented internal policy/procedure for each Liquidity Management "
                     "Tool available to it (anti-dilution levy, swing pricing, lock-up, redemption gating, "
                     "redemption deferral, redemption in kind, side pocket, dual pricing, temporary suspension)?",
        "citation": "Feedback Report §4.3 (Liquidity Management Tools)",
    },
    # 5. Expenses
    {
        "key": "cost_assessment", "section": "expenses",
        "question": "Is there a formalised assessment verifying that costs/fees — together with the level of "
                     "ORC/TER of the UCI's different share classes — are proportionate to market standards, "
                     "discussed at least annually in a formal meeting of the dirigeants?",
        "citation": "Feedback Report §5.1 (ORC/TER and formalised assessment of costs/fees)",
    },
    {
        "key": "epm_sft_costs", "section": "expenses",
        "question": "For UCITS concluding EPM/SFT transactions: is there a comprehensive, documented "
                     "assessment justifying the ratio of gross revenues to direct and indirect operational "
                     "costs/fees arising per EPM/SFT?",
        "citation": "Feedback Report §5.2 (EPM/SFT operational costs/fees); CSSF FAQ — Use of SFTs by UCITS",
    },
    # 6. Relationship with depositary
    {
        "key": "depositary_oversight", "section": "depositary",
        "question": "Are robust processes in place with the depositary (reconciliation and safekeeping of "
                     "assets, cash-flow monitoring) and an active process to follow up on irregularities "
                     "escalated by the depositary?",
        "citation": "Feedback Report §6 (Relationship with depositary)",
    },
    # 7. Disclosures
    {
        "key": "disclosure_compliance", "section": "disclosures",
        "question": "Does the annual report comply with applicable disclosure requirements — SFDR Article 8/9 "
                     "Annex IV (including the fossil gas/nuclear energy question), ESMA performance fee "
                     "disclosure guidelines at share-class level, and securities financing transactions "
                     "disclosures — where applicable to this UCI?",
        "citation": "Feedback Report §7 (Disclosures)",
    },
]


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp to the last valid day of the target month (e.g. 31 Jan + 1
    # month -> 28/29 Feb, not an invalid 31 Feb).
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def compute_deadline(uci_type: str, financial_year_end: date) -> date | None:
    """Real deadline rule from Section 2.1 of Circular CSSF 21/790: 3 months
    after financial year-end for UCITS, 4 months for Part II UCIs/SIFs/
    SICARs."""
    entry = UCI_TYPES.get(uci_type)
    if not entry or financial_year_end is None:
        return None
    _, months = entry
    return _add_months(financial_year_end, months)


@dataclass
class SaqSubmission:
    entity_name: str
    uci_type: str
    financial_year_end: date
    dirigeant_reviewed: bool = False
    answers: dict[str, str] = field(default_factory=dict)  # SAQ_QUESTIONS key -> selected option
    comments: dict[str, str] = field(default_factory=dict)  # SAQ_QUESTIONS key -> free-text comment

    @property
    def deadline(self) -> date | None:
        return compute_deadline(self.uci_type, self.financial_year_end)

    def validation_errors(self) -> list[str]:
        errors = []
        if not self.entity_name:
            errors.append("Entity name is required.")
        if self.uci_type not in UCI_TYPES:
            errors.append("UCI type must be one of " + ", ".join(UCI_TYPES) + ".")
        if not self.financial_year_end:
            errors.append("Financial year-end is required.")
        if not self.dirigeant_reviewed:
            errors.append(
                "The UCI's dirigeants must review and validate the self-assessment questionnaire's "
                "content before submission (Circular CSSF 21/790, Section 2.1)."
            )
        return errors


def build_saq_summary_workbook(sub: SaqSubmission) -> bytes:
    """Internal self-assessment summary (entity/period/deadline + one row
    per real SAQ sub-topic, with the self-assessed answer and any comment)
    for four-eyes review and record-keeping — not the SAQ itself, which is
    filed directly on CSSF's eDesk portal."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    fill = PatternFill("solid", fgColor="0A2647")

    ws1 = wb.active
    ws1.title = "Summary"
    rows = [
        ("Entity name", sub.entity_name),
        ("UCI type", UCI_TYPES.get(sub.uci_type, (sub.uci_type, 0))[0]),
        ("Financial year-end", sub.financial_year_end.isoformat() if sub.financial_year_end else ""),
        ("Submission deadline", sub.deadline.isoformat() if sub.deadline else ""),
        ("Dirigeants reviewed & validated", "Yes" if sub.dirigeant_reviewed else "No"),
    ]
    for r, (label, value) in enumerate(rows, start=1):
        c1 = ws1.cell(row=r, column=1, value=label)
        c1.font = Font(bold=True, color="FFFFFF")
        c1.fill = fill
        ws1.cell(row=r, column=2, value=value)
    ws1.column_dimensions["A"].width = 32
    ws1.column_dimensions["B"].width = 50

    ws2 = wb.create_sheet("Self-Assessment")
    section_labels = dict(SAQ_SECTIONS)
    header_cols = ["section", "question", "answer", "comment", "source"]
    for idx, col in enumerate(header_cols, start=1):
        cell = ws2.cell(row=1, column=idx, value=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        ws2.column_dimensions[cell.column_letter].width = {1: 26, 2: 80, 3: 12, 4: 50, 5: 55}[idx]
    for r, q in enumerate(SAQ_QUESTIONS, start=2):
        ws2.cell(row=r, column=1, value=section_labels.get(q["section"], q["section"]))
        ws2.cell(row=r, column=2, value=q["question"])
        ws2.cell(row=r, column=3, value=sub.answers.get(q["key"], ""))
        ws2.cell(row=r, column=4, value=sub.comments.get(q["key"], ""))
        ws2.cell(row=r, column=5, value=q["citation"])
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_saq_template_workbook() -> bytes:
    """Ingestion template mirroring build_saq_summary_workbook()'s layout,
    with an empty 'Entity_Info' header row plus one row per real SAQ
    sub-topic (key/section/question already filled in, answer/comment
    blank) to fill in."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    fill = PatternFill("solid", fgColor="0A2647")

    ws1 = wb.active
    ws1.title = "Entity_Info"
    cols = ["entity_name", "uci_type", "financial_year_end", "dirigeant_reviewed"]
    for idx, col in enumerate(cols, start=1):
        cell = ws1.cell(row=1, column=idx, value=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        ws1.column_dimensions[cell.column_letter].width = max(20, len(col) + 2)
    ws1.freeze_panes = "A2"

    ws2 = wb.create_sheet("Self_Assessment")
    section_labels = dict(SAQ_SECTIONS)
    header_cols = ["key", "section", "question", "answer", "comment"]
    for idx, col in enumerate(header_cols, start=1):
        cell = ws2.cell(row=1, column=idx, value=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        ws2.column_dimensions[cell.column_letter].width = {1: 28, 2: 26, 3: 80, 4: 12, 5: 50}[idx]
    for r, q in enumerate(SAQ_QUESTIONS, start=2):
        ws2.cell(row=r, column=1, value=q["key"])
        ws2.cell(row=r, column=2, value=section_labels.get(q["section"], q["section"]))
        ws2.cell(row=r, column=3, value=q["question"])
        ws2.cell(row=r, column=4, value=None)
        ws2.cell(row=r, column=5, value=None)
    ws2.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_saq_workbook(file_bytes: bytes) -> tuple[dict, dict, dict, list[str]]:
    """Parses a workbook built from build_saq_template_workbook() back into
    (entity_info dict, answers dict keyed by SAQ_QUESTIONS key, comments
    dict keyed by SAQ_QUESTIONS key, errors)."""
    import io as _io

    import pandas as pd

    errors: list[str] = []
    try:
        xls = pd.ExcelFile(_io.BytesIO(file_bytes))
    except Exception as exc:
        return {}, {}, {}, [f"Could not read this workbook: {exc}"]

    entity_info: dict = {}
    if "Entity_Info" in xls.sheet_names:
        df = xls.parse("Entity_Info")
        if not df.empty:
            entity_info = {k: v for k, v in df.iloc[0].to_dict().items() if pd.notna(v)}
    else:
        errors.append("Sheet 'Entity_Info' not found.")

    answers: dict[str, str] = {}
    comments: dict[str, str] = {}
    if "Self_Assessment" in xls.sheet_names:
        df = xls.parse("Self_Assessment")
        for row in df.to_dict("records"):
            key = row.get("key")
            if not key:
                continue
            answer = row.get("answer")
            if pd.notna(answer) and str(answer).strip():
                answers[str(key)] = str(answer).strip()
            comment = row.get("comment")
            if pd.notna(comment) and str(comment).strip():
                comments[str(key)] = str(comment).strip()
    else:
        errors.append("Sheet 'Self_Assessment' not found.")

    return entity_info, answers, comments, errors
