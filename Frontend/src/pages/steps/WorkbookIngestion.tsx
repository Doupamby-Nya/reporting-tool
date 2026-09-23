import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import {
    fetchBclCodes, fetchFilingForm, filingTemplateUrl, inspectFilingFile, parseFilingWorkbook,
} from "@api/reportingApi"
import DraftsPanel from "@components/DraftsPanel"
import IngestionPanel, { FORM_ANCHOR } from "@components/IngestionPanel"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import SchemaForm, { type FormValues } from "@components/SchemaForm"
import { useChain, useModule } from "@hooks/useChain"
import { useDrafts } from "@hooks/useDrafts"
import { setIngestion } from "@store/chainSlice"
import type { FormSchema, InspectionResult } from "src/types/reportingType"

/**
 * The ingestion step of the workbook-driven regimes: U 1.1, O 4.1, ESEF and
 * SAQ.
 *
 * Two ways in, one destination. A workbook filled offline is read straight
 * into the form, and the form itself is filled in here — both end at the
 * same submission, so whichever route a preparer takes, what the generator
 * will receive is visible and correctable in one place.
 *
 * The form is not written here: the API derives it from the regime's own
 * engine, so a field the regulator adds appears without this screen
 * changing, and a field renamed in the engine cannot silently stop reaching
 * the filing.
 */
const WorkbookIngestion: React.FC = () => {
    const module = useModule()
    const { chain, dispatch } = useChain(module.key)

    const [schema, setSchema] = useState<FormSchema | null>(null)
    const [countries, setCountries] = useState<[string, string][]>([])
    const [busy, setBusy] = useState(false)
    const [formOpen, setFormOpen] = useState(false)
    const [problems, setProblems] = useState<string[]>([])
    const [inspection, setInspection] = useState<InspectionResult | null>(null)

    const values = (chain.ingestion as FormValues) ?? {}
    const drafts = useDrafts<FormValues>(module.key,
        (data) => dispatch(setIngestion({ module: module.key, data })),
        () => setFormOpen(true))

    useEffect(() => {
        setProblems([])
        fetchFilingForm(module.key)
            .then(setSchema)
            .catch((error: Error) => toast.error(error.message))
    }, [module.key])

    useEffect(() => {
        // The country list is BCL's, but ISO 3166 is ISO 3166 — every regime
        // that asks for a country draws on the same list.
        fetchBclCodes()
            .then((codes) => setCountries(
                ((codes.countries as string[]) ?? []).map((code): [string, string] => [code, code])))
            .catch(() => setCountries([]))
    }, [])

    const update = (next: FormValues) =>
        dispatch(setIngestion({ module: module.key, data: next }))

    const upload = async (file: File) => {
        setBusy(true)
        try {
            const parsed = await parseFilingWorkbook(module.key, file)
            const { errors, ...data } = parsed as Record<string, unknown>
            const found = (errors as string[] | undefined) ?? []
            setProblems(found)
            // The workbook's parts are merged onto whatever was already
            // captured, so an upload completes a form rather than wiping it.
            update({ ...values, ...data })
            if (found.length) toast.warning(`Workbook read, with ${found.length} problem(s) to fix.`)
            else toast.success("Workbook read into the form below.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    /** Regimes whose filing is an XML document can be read back in; O 4.1 is
     *  EDIFACT and SAQ is a workbook, so neither offers it. */
    const readsXml = ["urr", "esef"].includes(module.key)

    const openFiling = async (file: File) => {
        setBusy(true)
        try {
            const found = await inspectFilingFile(module.key, file)
            setInspection(found)
            if (!found.recognised) {
                toast.error(`This file is not a ${module.label} filing.`)
            } else if (found.schema_validation.available && found.schema_validation.valid) {
                toast.success(`Identified as ${found.label}, valid against the regulator's schema.`)
            } else if (found.schema_validation.available) {
                toast.warning(`Identified as ${found.label}, but it does not satisfy the schema.`)
            } else {
                toast.info(`Identified as ${found.label}. No schema is bundled to check it against.`)
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title={`${module.title} — Ingestion`}
                subtitle={schema?.description
                    ?? "Fill the form in directly, or bring a workbook you have already filled."} />

            <IngestionPanel regime={module.label} busy={busy} actions={[
                { label: "Download template", href: filingTemplateUrl(module.key),
                  hint: "the standardised template for this regime" },
                { label: "Import a filled-in workbook", accept: ".xlsx,.xlsm", onFile: upload,
                  primary: true, hint: "read straight into the form below" },
                ...(readsXml ? [{
                    label: "Open an existing XML filing", accept: ".xml,.xhtml", onFile: openFiling,
                    hint: "identified, and checked against the regulator's schema where one exists",
                }] : []),
                { label: "Saved drafts", onClick: () => drafts.setPanelOpen(true),
                  hint: "re-open a submission saved earlier" },
            ]}
                formOpen={formOpen} onToggleForm={() => setFormOpen(!formOpen)}>
                {inspection?.recognised && (
                    <div className="flex flex-col gap-2 border-t border-slate-100 pt-3">
                        <p className="text-sm text-slate-700">
                            Identified as <strong>{inspection.label}</strong>
                            {!inspection.schema_validation.available && (
                                <span className="ml-2 text-xs text-slate-500">
                                    {inspection.schema_validation.detail}
                                </span>
                            )}
                        </p>
                        {inspection.schema_validation.available && (
                            <ValidationReport validation={{
                                valid: inspection.schema_validation.valid,
                                errors: inspection.schema_validation.valid ? [] :
                                    inspection.schema_validation.errors.map((message) => ({
                                        level: "error" as const, code: "XSD", message,
                                    })),
                                warnings: [],
                            }} />
                        )}
                    </div>
                )}

                {problems.length > 0 && (
                    <div className="flex flex-col gap-1 border-t border-slate-100 pt-3">
                        <p className="text-sm font-semibold text-slate-900">
                            {problems.length} problem(s) in the workbook
                        </p>
                        {problems.slice(0, 12).map((message, index) => (
                            <p key={index} className="rounded-md border border-amber-200 bg-amber-50 px-3
                                                      py-1.5 text-xs text-amber-900">
                                {message}
                            </p>
                        ))}
                        {problems.length > 12 && (
                            <p className="text-xs text-slate-500">…and {problems.length - 12} more.</p>
                        )}
                    </div>
                )}
            </IngestionPanel>

            {formOpen && (
                <div id={FORM_ANCHOR} className="flex flex-col gap-6">
                    {schema
                        ? <SchemaForm schema={schema} values={values} onChange={update}
                            countries={countries} />
                        : <p className="text-sm text-slate-500">Loading the form…</p>}

                    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
                        <input value={drafts.name} onChange={(event) => drafts.setName(event.target.value)}
                            placeholder="Name this draft"
                            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none
                                       focus:border-[#0A2647]" />
                        <button type="button" onClick={() => drafts.save(values)}
                            className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                                       text-[#0A2647] transition hover:bg-slate-100">
                            Save this submission as a draft
                        </button>
                    </div>
                </div>
            )}

            {drafts.panelOpen && (
                <DraftsPanel moduleKey={module.key} moduleLabel={module.title}
                    onOpen={drafts.open} onClose={() => drafts.setPanelOpen(false)} />
            )}
        </section>
    )
}

export default WorkbookIngestion
