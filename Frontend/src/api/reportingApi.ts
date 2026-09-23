import { api } from "@api/api"
import type {
    ApiEnvelope, AuditEntry, BclCodes, BclReportsResponse, DraftSummary,
    FatcaClassification, FatcaGeneration, FilingRegime, FilingResult, FormSchema, Fund,
    GenerationResult, InspectionResult, RegulationDocument, RegulatoryModule,
    RulesCatalogue, TrackedDocument, ValidationResult,
} from "src/types/reportingType"

/**
 * One call site per endpoint of the regulatory reporting API.
 *
 * Every route answers with the same envelope, so `unwrap` turns a failure
 * into a thrown Error carrying the API's own message — which lets a page use
 * a single try/catch instead of branching on `success` everywhere.
 */
async function unwrap<T>(request: Promise<{ data: ApiEnvelope<T> }>): Promise<T> {
    try {
        const { data } = await request
        if (!data.success) throw new Error(data.message || "The request was refused by the API.")
        return data.result as T
    } catch (error) {
        // A refusal now carries its HTTP status as well as its message, so
        // axios rejects before the envelope is read. The message is still in
        // the body and is what the preparer needs to see — "Request failed
        // with status code 400" tells them nothing.
        const response = (error as { response?: { data?: ApiEnvelope<never> } }).response
        const message = response?.data?.message
        if (message) throw new Error(message)
        throw error
    }
}

/**
 * VITE_BACKEND_URL already carries the /api/v1 prefix, matching the
 * platform's existing convention, so every path below is relative to it.
 */
export function downloadUrl(path: string): string {
    const base = api.defaults.baseURL?.replace(/\/$/, "") ?? ""
    return `${base}${path}`
}

// --- reference data ----------------------------------------------------------

export const fetchModules = () =>
    unwrap<RegulatoryModule[]>(api.get(`/reference/modules`))

export const fetchRegulations = (moduleKey: string) =>
    unwrap<RegulationDocument[]>(api.get(`/reference/regulations/${moduleKey}`))

/**
 * A bundled regulator document. Shown in the page by default; `download`
 * asks for it as a file instead, which is the only difference between
 * reading a text and keeping a copy of it.
 */
export const regulationDownloadUrl = (moduleKey: string, index: number, download = false) =>
    downloadUrl(`/reference/regulations/${moduleKey}/${index}/download${download ? "?download=true" : ""}`)

// --- BCL ---------------------------------------------------------------------

export const fetchBclReports = () =>
    unwrap<BclReportsResponse>(api.get(`/bcl/reports`))

export const fetchBclCodes = () =>
    unwrap<BclCodes>(api.get(`/bcl/codes`))

export const validateBclReport = (reportKey: string, payload: unknown) =>
    unwrap<ValidationResult>(api.post(`/bcl/${reportKey}/validate`, payload))

export const generateBclReport = (reportKey: string, payload: unknown) =>
    unwrap<GenerationResult>(api.post(`/bcl/${reportKey}/generate`, payload))

export const runBclCrossChecks = (payload: unknown) =>
    unwrap<ValidationResult>(api.post(`/bcl/cross-checks`, payload))

export const inspectBclFile = (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<InspectionResult>(api.post(`/bcl/inspect`, form))
}

export const bclReferenceUrl = (reportKey: string, kind: "report" | "instructions" | "rules") =>
    downloadUrl(`/bcl/${reportKey}/reference/${kind}`)

// --- AIFMD -------------------------------------------------------------------

export const fetchAifmdMetadata = () =>
    unwrap<Record<string, unknown>>(api.get(`/aifmd/metadata`))

export const validateAifmd = (payload: unknown) =>
    unwrap<ValidationResult>(api.post(`/aifmd/validate`, payload))

export const generateAifmd = (payload: unknown) =>
    unwrap<GenerationResult>(api.post(`/aifmd/generate`, payload))

export const inspectAifmdFile = (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<InspectionResult>(api.post(`/aifmd/inspect`, form))
}

export const aifmdTemplateUrl = () => downloadUrl("/aifmd/template")

// --- the workbook-driven regimes ---------------------------------------------

export const filingTemplateUrl = (regimeKey: string) =>
    downloadUrl(`/${regimeKey}/template`)

export const parseFilingWorkbook = (regimeKey: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<Record<string, unknown>>(api.post(`/${regimeKey}/parse`, form))
}

export const generateFiling = (regimeKey: string, payload: unknown) =>
    unwrap<FilingResult>(api.post(`/${regimeKey}/generate`, payload))

// --- workflow, audit and drafts ----------------------------------------------

export const fetchDocuments = (moduleKey: string) =>
    unwrap<Record<string, TrackedDocument>>(api.get(`/documents/${moduleKey}`))

export const recordGenerated = (moduleKey: string, documentId: string, label: string, user: string) =>
    unwrap<TrackedDocument>(api.post(`/documents/${moduleKey}`,
        { document_id: documentId, label, user }))

export const transitionDocument = (
    moduleKey: string, documentId: string, status: string, user: string, comment = "",
) =>
    unwrap<TrackedDocument>(api.post(
        `/documents/${moduleKey}/${encodeURIComponent(documentId)}/status`,
        { status, user, comment }))

export const fetchAuditLog = (limit = 100, moduleKey?: string) =>
    unwrap<AuditEntry[]>(api.get(`/audit`, { params: { limit, module_key: moduleKey } }))

export const listDrafts = (moduleKey: string) =>
    unwrap<DraftSummary[]>(api.get(`/drafts/${moduleKey}`))

export const saveDraft = (moduleKey: string, name: string, data: unknown, user: string) =>
    unwrap<DraftSummary>(api.post(`/drafts/${moduleKey}`, { name, data, user }))

export const loadDraft = <T = unknown>(moduleKey: string, name: string) =>
    unwrap<{ name: string; saved_at: string; saved_by: string; data: T }>(
        api.get(`/drafts/${moduleKey}/${encodeURIComponent(name)}`))

export const deleteDraft = (moduleKey: string, name: string) =>
    unwrap<{ deleted: string }>(api.delete(`/drafts/${moduleKey}/${encodeURIComponent(name)}`))

export const fetchFilingRegimes = () =>
    unwrap<FilingRegime[]>(api.get(`/reference/regimes`))

/**
 * The rules-engine catalogue of a regime, reported against a submission.
 * The draft is posted rather than put in the URL: it is the whole captured
 * form, and the catalogue reports on it.
 */
export const fetchFilingRules = (regimeKey: string, draft: unknown) =>
    unwrap<RulesCatalogue>(api.post(`/${regimeKey}/rules`, draft ?? {}))

/**
 * Reads a filing produced earlier back in. Every regime whose output is XML
 * offers this; the answer says whether a schema was available to check it
 * against, because "well-formed" is not "valid".
 */
export const inspectFilingFile = (regimeKey: string, file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<InspectionResult>(api.post(`/${regimeKey}/inspect`, form))
}

export const generateEsefPackage = (payload: unknown) =>
    unwrap<FilingResult>(api.post(`/esef/generate`, payload, { params: { as_package: true } }))

// --- PRIIPs KID --------------------------------------------------------------

export const fetchPriipsParameters = () =>
    unwrap<Record<string, unknown>>(api.get(`/priips/parameters`))

export const fetchPriipsTemplates = () =>
    unwrap<string[]>(api.get(`/priips/templates`))

export const calculatePriips = (fund: unknown, parameters?: unknown) =>
    unwrap<Record<string, unknown>>(api.post(`/priips/calculate`, { fund, parameters }))

export const buildKid = (fund: unknown, templateName = "standard", parameters?: unknown) =>
    unwrap<Record<string, unknown>>(api.post(`/priips/kid`,
        { fund, parameters, template_name: templateName }))

/**
 * The rendered KID. This route answers with the PDF itself rather than the
 * usual envelope, so the response is taken as a blob and the filename read
 * off the Content-Disposition header the API sets.
 */
export async function renderKidPdf(kid: unknown): Promise<{ blob: Blob; filename: string }> {
    const response = await api.post(`/priips/kid/render`, { kid }, { responseType: "blob" })
    const disposition = String(response.headers["content-disposition"] ?? "")
    const match = disposition.match(/filename="?([^"]+)"?/)
    return { blob: response.data as Blob, filename: match?.[1] ?? "KID.pdf" }
}

// --- FATCA & CRS -------------------------------------------------------------

export const fetchPreparers = () =>
    unwrap<Record<string, Record<string, string>>>(api.get(`/fatca/preparers`))

export const savePreparers = (preparers: Record<string, Record<string, string>>) =>
    unwrap<Record<string, Record<string, string>>>(api.put(`/fatca/preparers`, preparers))

export const fatcaTemplateUrl = (year?: number) =>
    downloadUrl(`/fatca/template${year ? `?reporting_year=${year}` : ""}`)

export const classifyFatca = (file: File, parameters: Record<string, unknown>) => {
    const form = new FormData()
    form.append("file", file)
    form.append("parameters", JSON.stringify(parameters))
    return unwrap<FatcaClassification>(api.post(`/fatca/classify`, form))
}

export const generateFatca = (
    file: File, parameters: Record<string, unknown>, preparer: string,
) => {
    const form = new FormData()
    form.append("file", file)
    form.append("parameters", JSON.stringify(parameters))
    form.append("preparer", preparer)
    return unwrap<FatcaGeneration>(api.post(`/fatca/generate`, form))
}

export const fetchFilerCategories = () => unwrap<string[]>(api.get(`/fatca/filer-categories`))

// --- clients -----------------------------------------------------------------

export const fetchClients = () =>
    unwrap<Record<string, unknown>[]>(api.get(`/reference/clients`))

// --- the registry of funds and share classes under mandate -------------------

export const fetchFunds = () => unwrap<Fund[]>(api.get(`/funds`))

export const fundTemplateUrl = () => downloadUrl("/funds/template")

export const parseFundWorkbook = (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<{ funds: Fund[]; errors: string[] }>(api.post(`/funds/parse`, form))
}

export const addFunds = (funds: Fund[]) => unwrap<Fund[]>(api.post(`/funds`, { funds }))

export const loadDemoFunds = () => unwrap<Fund[]>(api.post(`/funds/demo`))

export const resetFunds = () => unwrap<Fund[]>(api.delete(`/funds`))

export const removeFund = (fundId: string) =>
    unwrap<Fund[]>(api.delete(`/funds/${encodeURIComponent(fundId)}`))

// --- PRIIPs configuration ------------------------------------------------------

export const fetchTemplateText = (name: string, fmt: "json" | "yaml" = "json") =>
    unwrap<{ template_name: string; format: string; text: string }>(
        api.get(`/priips/templates/${encodeURIComponent(name)}`, { params: { fmt } }))

export const saveTemplateText = (name: string, text: string, format: "json" | "yaml" = "json") =>
    unwrap<Record<string, unknown>>(
        api.put(`/priips/templates/${encodeURIComponent(name)}`, { text, format }))

export const resetTemplate = (name: string) =>
    unwrap<Record<string, unknown>>(api.post(`/priips/templates/${encodeURIComponent(name)}/reset`))

export const savePriipsParameters = (parameters: Record<string, unknown>) =>
    unwrap<Record<string, unknown>>(api.put(`/priips/parameters`, parameters))

export const resetPriipsParameters = () =>
    unwrap<Record<string, unknown>>(api.post(`/priips/parameters/reset`))

export const fetchAppSettings = () =>
    unwrap<Record<string, unknown>>(api.get(`/priips/settings`))

export const saveAppSettings = (settings: Record<string, unknown>) =>
    unwrap<Record<string, unknown>>(api.put(`/priips/settings`, settings))

/**
 * The GDPR notification letters owed to each reported account holder.
 *
 * This route answers with the ZIP itself, not the envelope, because the
 * archive carries personal data and is streamed straight to the preparer.
 * How many letters were produced — and how many of them MS Word was
 * available to convert to PDF — come back in headers.
 */
export async function generateNotifications(
    xml: string, categories: Record<string, boolean>,
): Promise<{ blob: Blob; letters: number; pdfs: number }> {
    const response = await api.post(`/fatca/notifications`, { xml, categories },
        { responseType: "blob" })

    // A refusal comes back as the JSON envelope, still typed as a blob.
    const type = String(response.headers["content-type"] ?? "")
    if (type.includes("application/json")) {
        const text = await (response.data as Blob).text()
        throw new Error((JSON.parse(text) as { message?: string }).message
            ?? "The letters could not be generated.")
    }
    return {
        blob: response.data as Blob,
        letters: Number(response.headers["x-letter-count"] ?? 0),
        pdfs: Number(response.headers["x-pdf-count"] ?? 0),
    }
}

/** A filled-in copy of ESMA's consolidated template, read back into the two
 *  dictionaries the engine works from. */
export const parseAifmdTemplate = (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return unwrap<{
        aifm_info: Record<string, unknown>
        aif_info: Record<string, unknown>
        errors: string[]
    }>(api.post(`/aifmd/template/parse`, form))
}

/** The capture form of a regime, derived by the API from its engine. */
export const fetchFilingForm = (regimeKey: string) =>
    unwrap<FormSchema>(api.get(`/${regimeKey}/form`))
