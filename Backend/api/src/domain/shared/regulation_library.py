"""Regulatory reference library — the legal/technical texts each reporting
module is built against, one folder per module under data/regulation/.

Documents with a local ``file`` were fetched from their official source
(CSSF, ESMA) and are shown as an in-app PDF preview. A few primary EU/LU
legal texts sit behind an anti-bot challenge or a JS-rendered page that
could not be fetched programmatically (EUR-Lex's PDF endpoint, Legilux) —
those are listed with a ``url`` instead, linking to the genuine official
page rather than a guessed or scraped PDF link.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from utils.paths import RESOURCES_DIR
REGULATION_DIR = RESOURCES_DIR / "regulation"


class RegDoc(NamedTuple):
    title: str
    issuer: str
    description: str
    file: str | None = None  # relative to REGULATION_DIR/<module_key>/
    url: str | None = None   # official source, used when no local file


REGULATION_LIBRARY: dict[str, list[RegDoc]] = {
    "chain": [
        RegDoc(
            "Regulation (EU) 1286/2014 (PRIIPs Regulation)", "European Parliament & Council",
            "Primary legislation requiring a Key Information Document (KID) for packaged retail and "
            "insurance-based investment products.",
            url="https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=celex:32014R1286",
        ),
        RegDoc(
            "Commission Delegated Regulation (EU) 2017/653 (PRIIPs RTS)", "European Commission",
            "Regulatory technical standards on the presentation, content, review and revision of the KID — "
            "the basis for this module's SRI, cost (RIY) and performance-scenario methodology.",
            url="https://eur-lex.europa.eu/eli/reg_del/2017/653/2023-01-01/eng",
        ),
        RegDoc(
            "Commission Delegated Regulation (EU) 2021/2268 (amending RTS)", "European Commission",
            "Amends the 2017/653 RTS — updated performance scenario and past-performance methodology.",
            url="https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32021R2268",
        ),
    ],
    "fatca": [
        RegDoc(
            "Loi du 24 juillet 2015 relative à FATCA", "Luxembourg — Legilux",
            "Luxembourg law approving the US-LU FATCA intergovernmental agreement (IGA) — legal basis "
            "for the FATCA classification and reporting obligations implemented in this module.",
            url="https://legilux.public.lu/eli/etat/leg/loi/2015/07/24/n1/jo",
        ),
        RegDoc(
            "Loi du 18 décembre 2015 concernant l'échange automatique de renseignements (CRS)", "Luxembourg — Legilux",
            "Luxembourg law transposing the OECD Common Reporting Standard (CRS/NCD) — legal basis for "
            "the CRS side of this module.",
            url="https://legilux.public.lu/eli/etat/leg/loi/2015/12/18/n4/jo",
        ),
    ],
    "urr": [
        RegDoc(
            "Guidelines on the U 1.1 reporting", "CSSF",
            "User guide to the U 1.1 monthly financial reporting for UCIs — field-by-field definitions "
            "for the schema implemented in core/urr_engine.py.",
            file="urr/CSSF_U1.1_Guidelines.pdf",
        ),
        RegDoc(
            "FAQ concerning U 1.1 Reporting", "CSSF",
            "Frequently asked questions clarifying scope, deadlines and edge cases (null reports, "
            "last reports, umbrella sub-funds) of the U 1.1 filing.",
            file="urr/CSSF_U1.1_FAQ.pdf",
        ),
    ],
    "o41": [
        RegDoc(
            "Table O 4.1 — Renseignements financiers annuels", "CSSF",
            "Technical note for the O 4.1 annual financial information table: table characteristics, "
            "line-code hierarchy, verification rules and a worked EDIFACT message example — the basis "
            "for core/o41_engine.py's EDIFACT wire-code renumbering and message structure.",
            file="o41/CSSF_O4.1_Table.pdf",
        ),
        RegDoc(
            "Circular IML 97/136 (as amended)", "CSSF",
            "The circular introducing tables O 1.1, O 4.1 and O 4.2 — Annexe B gives O 4.1's real line "
            "codes, labels and the 23 validation formulas this module's Rules Engine evaluates. Note: "
            "O 1.1 (the monthly table from this same circular) was repealed and replaced by U 1.1 "
            "(Circular CSSF 15/627) in 2016.",
            file="o41/CSSF_IML97_136_amended_EN.pdf",
        ),
    ],
    "esef": [
        RegDoc(
            "Commission Delegated Regulation (EU) 2019/815 (ESEF RTS)", "European Commission",
            "The regulatory technical standards themselves — mandates Inline XBRL (iXBRL) tagging of "
            "annual financial reports using the IFRS Accounting Taxonomy (Annex II/IV), block-tagging of "
            "notes, and the XHTML single-document packaging format this module's engine is built against.",
            url="https://eur-lex.europa.eu/eli/reg_del/2019/815/2023-01-19/eng",
        ),
        RegDoc(
            "ESEF Reporting Manual", "ESMA",
            "Guidance on preparing Inline XBRL (iXBRL) annual financial reports in the European Single "
            "Electronic Format — the basis for this module's tagging/generation scope.",
            file="esef/ESMA_ESEF_Reporting_Manual.pdf",
        ),
    ],
    "aifmd": [
        RegDoc(
            "AIFM Reporting — Technical Guidance", "CSSF",
            "Field-level technical guidance for the AIFMD Annex IV report (leverage, liquidity, "
            "concentration and market risk indicators) — the basis for this module's planned scope.",
            file="aifmd/CSSF_AIFM_Reporting_Technical_Guidance.pdf",
        ),
    ],
    "saq": [
        RegDoc(
            "Practical rules concerning the self-assessment questionnaire", "CSSF",
            "Circular CSSF 21/790 — scope, submission deadlines and topic areas of the annual "
            "self-assessment questionnaire (SAQ) for UCITS, Part II UCIs, SIFs and SICARs; also covers "
            "the management letter and separate report drawn up by the UCI's approved statutory auditor.",
            file="saq/CSSF_21_790_SAQ_Practical_Rules.pdf",
        ),
    ],
    "bcl": [
        RegDoc(
            "S 1.3 / S 2.13 — Instructions", "Banque centrale du Luxembourg",
            "Monthly (S 1.3) and quarterly (S 2.13) statistical balance sheet for money market funds and "
            "non-MMF investment funds — reporting population, deadlines and the country/currency/economic-"
            "sector/initial-maturity breakdown code lists this module's chart of accounts is built against.",
            file="bcl/s13_s213/S0103_L4_S0213_L2_instructions_2025_EN.pdf",
        ),
        RegDoc(
            "S 1.3 / S 2.13 — Compendium of verification rules", "Banque centrale du Luxembourg",
            "The internal consistency checks BCL runs on the balance sheet (total assets = total liabilities, "
            "mandatory breakdowns, which lines may carry a debit) and its cross-checks against the "
            "security-by-security and S 2.20 reports — implemented by this module's validation.",
            file="bcl/s13_s213/S0103_L4_S0213_L2_VER_2025_EN.pdf",
        ),
        RegDoc(
            "S 1.6 — Instructions", "Banque centrale du Luxembourg",
            "Information on valuation effects on the balance sheet of investment funds — which items are in "
            "scope, the 5 % of total assets threshold that triggers the report, and how a valuation effect is "
            "distinguished from a transaction.",
            file="bcl/s16/S0106_L2_instructions_2025_EN.pdf",
        ),
        RegDoc(
            "S 2.20 — Instructions", "Banque centrale du Luxembourg",
            "Quarterly financial information — fund and share-class level NAV-movement and P&L report; the "
            "field numbering (1010-6100) matches the real S220.xsd schema this module's engine is built against.",
            file="bcl/s220/S0220_L0_instructions_2025_EN.pdf",
        ),
        RegDoc(
            "S 2.20 — Compendium of verification rules", "Banque centrale du Luxembourg",
            "Every rule BCL applies to the quarterly financial information, from the file naming convention "
            "to the NAV roll-forward (item 3020) and the arithmetic of the income and expenses section.",
            file="bcl/s220/S-2_20-L0---Quarterly-financial-information---VER.pdf",
        ),
        RegDoc(
            "S 4.4 — Instructions", "Banque centrale du Luxembourg",
            "Country of marketing — the annual breakdown of item 2-004000 (units/shares issued) by country "
            "of marketing, reported as percentages with two decimals adding up to 100.",
            file="bcl/s44/S0404_L0_instructions_2025_EN.pdf",
        ),
        RegDoc(
            "S 4.4 — Compendium of verification rules", "Banque centrale du Luxembourg",
            "The internal checks on the country of marketing report: a unique valid ISO 3166 code per line, "
            "positive percentages no greater than 100, and a total of exactly 100.",
            file="bcl/s44/S0404_L0_VER_2025_EN.pdf",
        ),
        RegDoc(
            "TPTOBS Layout 3 — Instructions", "Banque centrale du Luxembourg",
            "Security-by-security look-through report for investment funds — the basis for this module's "
            "per-security field set (identifier type, type of holding, ESA 2010 security type, quotation, "
            "coupon terms and issuer identification).",
            file="bcl/tptobs/TPTOBS_L3_instructions_2025_EN.pdf",
        ),
        RegDoc(
            "TPTOBS Layout 3 — Compendium of verification rules", "Banque centrale du Luxembourg",
            "The per-security rules BCL applies: authorised lines and types of holding, ISIN validity, issuer "
            "country and sector, coupon coherence, and the reconciliation with the balance sheet and S 2.20.",
            file="bcl/tptobs/TPTOBS_L3_VER_2025_EN.pdf",
        ),
    ],
}


def docs_for(module_key: str) -> list[RegDoc]:
    return REGULATION_LIBRARY.get(module_key, [])


def doc_bytes(doc: RegDoc) -> bytes | None:
    if not doc.file:
        return None
    path = REGULATION_DIR / doc.file
    if not path.exists():
        return None
    return path.read_bytes()
