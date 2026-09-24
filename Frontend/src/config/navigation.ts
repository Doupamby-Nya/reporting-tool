/**
 * The platform's navigation, in one place.
 *
 * This mirrors `core/layout.py` of the Streamlit original: nine top-level
 * destinations, and for each reporting module a "production chain" of steps
 * shown in the left panel. The chain is the product's own structure rather
 * than data — a step only appears once the API and the page behind it exist —
 * so it is declared here and the router is generated from it, which is what
 * keeps the tab bar, the side panel and the routes from drifting apart.
 *
 * Two keys per module are deliberate and different:
 *  - `key` is the URL segment and the key the workflow/audit API tracks
 *    filings under;
 *  - `regulationKey` is the key the bundled regulatory library is filed
 *    under, which for PRIIPs is the historical "chain".
 */

export type ChainStep = {
    /** URL segment under the module, e.g. `rules` in `/bcl/rules`. */
    path: string
    label: string
}

export type ModuleNav = {
    key: string
    label: string
    /**
     * The heading each of this module's steps opens with. It is short on
     * purpose: a step appends its own name to it, so a descriptive title
     * reads as a double-barrelled heading.
     */
    title: string
    authority: string
    regulationKey: string
    /**
     * The production chain, in order. The regulatory reference is not part
     * of it: a preparer consults the texts at any point and never "completes"
     * them, so putting them on the progress line would make the chain read
     * as unfinished whenever they had not been opened.
     */
    steps: ChainStep[]
}

/** The regulator's own texts. Reachable from every module, at any time,
 *  which is exactly why it sits beside the chain rather than inside it. */
export const REFERENCE_STEP: ChainStep = { path: "regulation", label: "Regulatory reference" }

/** The steps shared by every module, so a chain declares only its order. */
const INGESTION: ChainStep = { path: "ingestion", label: "Ingestion" }
const RULES: ChainStep = { path: "rules", label: "Rules engine" }
const CONTROLS: ChainStep = { path: "controls", label: "Controls & audit" }

export const MODULES: ModuleNav[] = [
    {
        key: "priips", label: "PRIIPs KID", title: "PRIIPs KID",
        authority: "Regulation (EU) 1286/2014", regulationKey: "chain",
        steps: [
            INGESTION,
            { path: "engine", label: "Calculation engine" },
            { path: "generation", label: "KID generation" },
            CONTROLS,
            { path: "configuration", label: "Configuration" },
        ],
    },
    {
        key: "fatca", label: "FATCA", title: "FATCA & CRS",
        authority: "ACD Luxembourg", regulationKey: "fatca",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "XML generation" },
            { path: "preview", label: "XML preview" },
            { path: "notification", label: "Data notification" },
            CONTROLS,
            { path: "configuration", label: "Configuration" },
        ],
    },
    {
        key: "urr", label: "U 1.1", title: "U 1.1",
        authority: "CSSF", regulationKey: "urr",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "XML generation" },
            { path: "preview", label: "XML preview" },
            CONTROLS,
        ],
    },
    {
        // O 4.1 output is EDIFACT text, not XML — hence no preview step.
        key: "o41", label: "O 4.1", title: "O 4.1",
        authority: "CSSF / BCL", regulationKey: "o41",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "EDIFACT generation" },
            CONTROLS,
        ],
    },
    {
        key: "esef", label: "ESEF", title: "ESEF",
        authority: "ESMA", regulationKey: "esef",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "iXBRL generation" },
            { path: "preview", label: "iXBRL preview" },
            CONTROLS,
        ],
    },
    {
        key: "aifmd", label: "AIFMD", title: "AIFMD Annex IV",
        authority: "CSSF / ESMA", regulationKey: "aifmd",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "XML generation" },
            { path: "preview", label: "XML preview" },
            CONTROLS,
        ],
    },
    {
        // The self-assessment questionnaire is filed on CSSF's eDesk portal
        // rather than generated as a machine-readable report, so there is
        // nothing to preview.
        key: "saq", label: "SAQ", title: "SAQ",
        authority: "CSSF", regulationKey: "saq",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "Generation" },
            CONTROLS,
        ],
    },
    {
        key: "bcl", label: "BCL", title: "BCL statistical reports",
        authority: "Banque centrale du Luxembourg", regulationKey: "bcl",
        steps: [
            INGESTION, RULES,
            { path: "generation", label: "XML generation" },
            { path: "preview", label: "XML preview" },
            CONTROLS,
        ],
    },
]

export const moduleByKey = (key: string | undefined): ModuleNav | undefined =>
    MODULES.find((module) => module.key === key)

/** The first step of a chain, which a bare `/module` URL redirects to. */
export const firstStepOf = (module: ModuleNav): string => module.steps[0].path
