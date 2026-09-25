/** Shapes the regulatory reporting API returns. */

/** Every route answers with this envelope. */
/** A module the signed-in user can use; `valid_until` is null for a platform administrator. */
export type ModuleGrant = {
    key: string
    valid_until: string | null
}

export type Me = {
    email: string
    name: string
    role: "platform_admin" | "org_admin" | "user"
    organisation: string
    modules: ModuleGrant[]
}

export type ApiEnvelope<T> = {
    success: boolean
    result?: T
    message?: string
}

/** One validation finding, carrying the regulator's own control code. */
export type Issue = {
    level: "error" | "warning"
    code: string
    message: string
}

export type ValidationResult = {
    valid: boolean
    errors: Issue[]
    warnings: Issue[]
}

/** The outcome of checking a produced document against the regulator's XSD. */
export type SchemaResult = {
    available: boolean
    valid: boolean
    errors: string[]
    detail?: string | null
}

export type GeneratedFile = {
    key: string
    label: string
    filename: string
    content: string
    schema_validation: SchemaResult
    /** AIFMD only: a file must carry exactly one reporting record. */
    record_count?: number | null
}

export type GenerationResult = {
    generated: boolean
    validation: ValidationResult
    files: GeneratedFile[]
}

/** A regulatory module the platform supports. */
export type RegulatoryModule = {
    key: string
    label: string
    authority: string
    description: string
    outputs: string[]
}

/** A regulator document bundled with a module. */
export type RegulationDocument = {
    index: number
    title: string
    issuer: string
    description: string
    filename: string
    url?: string | null
    downloadable: boolean
}

/** One BCL report and its chart of accounts. */
export type BclReport = {
    key: string
    label: string
    root: string
    namespace: string
    layout: number
    file_code: string
    frequency: string
    description: string
    assets?: BclChartLine[]
    liabilities?: BclChartLine[]
    has_maturity?: boolean
    chart_of_accounts?: { item: string; label: string }[]
}

/** One line of a BCL chart of accounts. "(1)" means the amount must be
 *  broken down over that dimension; any other value is the fixed code. */
export type BclChartLine = {
    item: string
    label: string
    country: string
    currency: string
    sector: string
    maturity: string
}

export type BclReportsResponse = {
    reports: BclReport[]
    breakdown_marker: string
}

export type BclCodes = {
    sectors: Record<string, string>
    maturities: Record<string, string>
    /** ISO 3166 and ISO 4217, for the breakdown pickers. */
    countries: string[]
    currencies: string[]
    /** BCL's own country codes for international organisations and the like. */
    special_countries: Record<string, string>
    no_breakdown: Record<string, string>
    schema_validation_available: boolean
    [key: string]: unknown
}

/** The result of identifying and schema-validating an uploaded filing. */
export type InspectionResult = {
    recognised: boolean
    report_key?: string | null
    file_key?: string | null
    label?: string | null
    filename?: string | null
    record_count?: number
    schema_validation: SchemaResult
    /**
     * The filing read back into the form that would produce it, where the
     * regime supports it. This is what lets an upload re-open the work
     * rather than only report on it.
     */
    data?: Record<string, unknown> | null
    root?: string | null
    namespace?: string | null
}

/** A generated filing as the workflow tracks it. */
export type TrackedDocument = {
    version: number
    label: string
    status: string
    last_generated: string
    last_generated_by: string
    history: {
        version: number
        status: string
        timestamp: string
        user: string
        comment: string
    }[]
}

export type AuditEntry = {
    timestamp: string
    action: string
    subject: string
    user: string
    detail: string
}

/**
 * A saved draft, described well enough to be recognised without opening it:
 * a preparer coming back a week later remembers the fund and the period,
 * not the name they typed.
 */
export type DraftSummary = {
    name: string
    saved_at: string
    saved_by: string
    /** The entity the draft is for, wherever that regime keeps its name. */
    entity?: string
    /** The reporting period, wherever that regime keeps it. */
    period?: string
    /** An identifying code — CSSF code, national number, LEI. */
    code?: string
    /** Roughly how much has been captured, to tell a stub from a near-final. */
    fields_filled?: number
}

/** A regime whose chain starts from a workbook template. */
export type FilingRegime = {
    key: string
    label: string
    authority: string
    output_label: string
    template_filename: string
}

/**
 * What a regime's generator returns. A filing is either text (XML, EDIFACT,
 * iXBRL) or binary (a workbook, a ZIP package), never both — which is why
 * exactly one of `content` / `content_base64` is filled.
 */
export type FilingOutput = {
    filename: string
    label: string
    media_type: string
    content?: string | null
    content_base64?: string | null
}

/**
 * What a workbook-driven regime's /generate answers. A submission that fails
 * the engine's own checks is refused rather than turned into a filing:
 * `generated` is then false, `errors` says why, and there is no file.
 */
export type FilingResult =
    | ({ generated: true; errors: string[] } & FilingOutput)
    | { generated: false; errors: string[] }

/** One row of a rules-engine mapping table. */
export type RulesRow = {
    key: string
    label: string
    /** The regulator element the field is tagged to. */
    path: string
    filled: boolean
    code?: string
    period_type?: string
    balance?: string
    fact_type?: string
}

export type RulesTable = {
    title: string
    /** Heading of the mapping column, which differs per regime. */
    column: string
    rows: RulesRow[]
    note?: string
}

export type RulesCatalogue = {
    title: string
    description: string
    coverage: { label: string; value: string; hint: string }[]
    tables: RulesTable[]
    /** Cross-check failures, where the regime has arithmetic to check. */
    errors: string[]
    note: string
}

export type FatcaClassification = {
    counts: Record<string, number>
    accounts: Record<string, unknown>[]
    messages: string[]
    warnings: string[]
}

export type FatcaGeneration = {
    counts: Record<string, number>
    /** Problems the generator raised; a filing with any of these is refused. */
    errors: string[]
    files: FilingOutput[]
}

/**
 * One fund or share class under mandate — the registry the PRIIPs chain
 * works from and the global summary reports on. The engine reads far more
 * fields than these off a record; the ones named here are those the
 * platform's own screens display, so a record carries whatever else the
 * workbook held.
 */
export type Fund = {
    fund_id: string
    fund_name: string
    share_class: string
    isin: string
    regime: string
    manco: string
    category?: string
    [field: string]: unknown
}

/** One field of a capture form, as the API describes it. */
export type FormField = {
    key: string
    label: string
    /** text | date | number | integer | boolean | select | country */
    type: string
    /** Present when the field is a code the regulator enumerates. */
    options?: Record<string, string>
    hint?: string
}

export type FormColumn = { key: string; label: string; type: string }

export type FormGroup = { title: string; fields: FormField[] }

/**
 * A section of a capture form. `key` says where its values live in the
 * submission: "" writes at the top level, anything else inside that nested
 * object — which is how the form's shape matches the engine's.
 */
export type FormSection = {
    key: string
    title: string
    /** fields | amounts | texts | questions | table */
    kind: string
    hint?: string
    fields?: FormField[]
    groups?: FormGroup[]
    columns?: FormColumn[]
    choices?: string[]
    comments_key?: string
}

export type FormSchema = {
    title: string
    description: string
    sections: FormSection[]
    /** AIFMD: the four templates of ESMA's consolidated workbook. */
    templates?: Record<string, string>
    /** Which of them a filing must fill, and the field that decides it. */
    template_rule?: {
        field: string
        label: string
        options: Record<string, string>
        applies: Record<string, string[]>
    }
}

/** One official document bundled for a BCL report. */
export type BclReference = {
    kind: "instructions" | "rules" | "report"
    filename: string
    size: number
    format: string
}

/** One cell of a previewed workbook: its displayed value, bold, fill. */
export type SheetCell = { v: string; b?: 1; bg?: string } | null

/** A sheet as the API reads it for the in-page viewer. `merges` holds
 *  [row, col, rowSpan, colSpan], zero-based. `widths` are in characters. */
export type SheetPreview = {
    name: string
    rows: SheetCell[][]
    cols: number
    merges: [number, number, number, number][]
    widths: number[]
    truncated: boolean
}

export type WorkbookPreview = {
    filename: string
    sheets: SheetPreview[]
    default_sheet: number
}

// --- activity -----------------------------------------------------------------

export type ActivityAction =
    | "generated" | "reviewed" | "validated" | "ingested" | "drafted" | "deleted"
    | "consulted" | "downloaded" | "configured" | "signed_in" | "administered"

export type ActivitySubject = { module: string; subject: string; at: string }

export type ActivityGroup = {
    action: ActivityAction
    count: number
    modules: { module: string; count: number }[]
    subjects: ActivitySubject[]
}

export type ActivityUserRow = {
    user_id: number
    name: string
    email: string
    count: number
    active_days: number
    generated: number
    reviewed: number
    top_module: string
    modules: { module: string; count: number }[]
    last_active: string
}

/** Everything a usage dashboard draws, for one scope and one period. */
export type ActivitySummary = {
    range: { from: string; to: string }
    timezone: string
    years: number[]
    day: string | null
    total: number
    /** [ISO date, count], days without activity left out. */
    days: [string, number][]
    active_days: number
    current_streak: number
    longest_streak: number
    busiest_day: { date: string; count: number } | null
    /** What is under the calendar: all of it, or the day picked on it. */
    shown_total: number
    by_module: { module: string; count: number }[]
    by_action: { action: ActivityAction; count: number }[]
    /** Weekday (Monday first) × hour. */
    by_hour: number[][]
    by_user: ActivityUserRow[]
    by_organisation: { organisation_id: number; name: string; count: number; users: number }[]
    months: { month: string; total: number; groups: ActivityGroup[] }[]
    recent: { at: string; module: string; action: ActivityAction; subject: string | null; user: string | null }[]
}

export type ActivityScope = {
    id: number
    name: string
    kind: string
    users: { id: number; name: string; email: string; active: boolean }[]
}

export type ActivityFilters = {
    year?: number | null
    day?: string | null
    module?: string | null
    action?: string | null
    organisation_id?: number | null
    user_id?: number | null
}
