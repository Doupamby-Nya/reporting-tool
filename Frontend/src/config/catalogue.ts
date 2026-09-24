/**
 * How the platform presents itself: the home page, the module cards and the
 * user guide are all built from this, so a module is described once.
 *
 * Kept apart from navigation.ts, which is the product's structure; this is
 * its copy.
 */

export type ModulePitch = {
    /** One sentence: what the module produces and for whom. */
    pitch: string
    /** Three or four capabilities, shown on the module card and in the guide. */
    highlights: string[]
    /** A limit the preparer must know before relying on the output, if any. */
    limitation?: string
    /** The module's logo: a monogram on its own colour. */
    monogram: string
    color: string
}

export const PITCHES: Record<string, ModulePitch> = {
    priips: {
        pitch: "Key Information Documents for UCITS and AIFs, from the fund registry to the signed PDF.",
        highlights: [
            "SRI, cost and performance-scenario calculations of the RTS",
            "Three KID layouts, with your organisation's name and logo",
            "One fund registry, filled from a standard workbook",
        ],
        limitation: "The calculation methodology is simplified and configurable: calibrate it before any production use.",
        monogram: "KID", color: "#1F5FA8",
    },
    fatca: {
        pitch: "FATCA and CRS returns for the Luxembourg tax authority, with the classification that precedes them.",
        highlights: [
            "Account-holder classification made visible, code by code",
            "XML returns validated against the ACD schema",
            "GDPR notification letters for reported holders",
        ],
        monogram: "AEOI", color: "#0E7490",
    },
    urr: {
        pitch: "The monthly U 1.1 filing on undertakings for collective investment (Circular CSSF 15/627).",
        highlights: [
            "Standard workbook in, CSSF XML out",
            "Cross-checks before generation, not after rejection",
            "Saved drafts for a filing prepared over several days",
        ],
        monogram: "U 1.1", color: "#7C3AED",
    },
    o41: {
        pitch: "The O 4.1 balance-sheet return of Circular IML 97/136, filed as EDIFACT.",
        highlights: [
            "Workbook capture with the regulator's own item codes",
            "Balance and consistency controls before the file is built",
            "EDIFACT output named as the regulator expects",
        ],
        monogram: "O 4.1", color: "#B45309",
    },
    esef: {
        pitch: "Annual financial reports in Inline XBRL, packaged as an ESEF report package.",
        highlights: [
            "iXBRL document and ESEF ZIP package",
            "Mandatory tagging checked before generation",
            "Preview of the produced document",
        ],
        limitation: "The output has not been run through an XBRL processor against ESMA's conformance suite.",
        monogram: "ESEF", color: "#047857",
    },
    aifmd: {
        pitch: "AIFMD Annex IV reporting: the manager's DATMAN and the fund's DATAIF files.",
        highlights: [
            "ESMA's consolidated template, imported as it is",
            "The CSSF technical guidance controls, with their own codes",
            "Both files validated against ESMA's XSD",
        ],
        monogram: "AIF", color: "#BE185D",
    },
    saq: {
        pitch: "The Circular CSSF 21/790 self-assessment questionnaire, reviewed and kept on record.",
        highlights: [
            "Answers captured and checked for completeness",
            "A summary for review ahead of the eDesk filing",
            "Four-eyes review and audit trail like every other module",
        ],
        limitation: "The SAQ is filed on CSSF's eDesk portal: this module prepares and tracks, it does not file.",
        monogram: "SAQ", color: "#4338CA",
    },
    bcl: {
        pitch: "The six BCL statistical reports: S 1.3, S 2.13, S 1.6, S 2.20, S 4.4 and TPTOBS.",
        highlights: [
            "BCL's compendium of verification rules, code by code",
            "Cross-checks between the balance sheet, TPTOBS and S 2.20",
            "An existing filing can be read back and checked",
        ],
        monogram: "BCL", color: "#0A2647",
    },
}

/** What each step of a production chain is for, as the guide explains it. */
export const STEP_HELP: Record<string, string> = {
    ingestion: "Download the standard workbook, fill it in offline and upload it back — or open a saved draft. "
        + "What was read is shown exactly as the generator will receive it.",
    engine: "Run the calculations: the summary risk indicator, the costs over each holding period and the four "
        + "performance scenarios.",
    rules: "The regulator's own controls applied to your submission: what is filled, what is missing, which "
        + "cross-checks fail — each with the regulator's control code.",
    generation: "The filing is built, then validated against the regulator's schema. Nothing that fails can be "
        + "downloaded.",
    preview: "Read the produced document and correct it if needed. An edit replaces the filing only once saved.",
    notification: "Prepare the letters owed to the account holders who were reported.",
    controls: "Four-eyes review: someone other than the preparer approves or rejects the filing. Every step is "
        + "written to the audit trail with the account that took it.",
    configuration: "Your organisation's own settings: preparers, name and logo on the documents you produce.",
}

/** The platform's promise, in four facts — shown on the home page. */
export const PROMISES: { title: string; text: string }[] = [
    { title: "Checked twice before it leaves",
      text: "Against the regulator's own business rules, then against its XML schema. A filing that fails either cannot be downloaded." },
    { title: "Four eyes, for real",
      text: "The person who approves a filing is never the one who prepared it — enforced by the platform, not by habit." },
    { title: "Every action on record",
      text: "Generation, review, approval, deletion: each is written to an audit trail against the account that did it." },
    { title: "Your data stays yours",
      text: "Each organisation works in its own space. No client sees another's funds, drafts or filings." },
]
