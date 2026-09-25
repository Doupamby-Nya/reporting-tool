import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import {
    aifmdTemplateUrl, fetchFilingForm, inspectAifmdFile, parseAifmdTemplate,
} from "@api/reportingApi"
import DraftsPanel from "@components/DraftsPanel"
import IngestionPanel, { FORM_ANCHOR } from "@components/IngestionPanel"
import Notice, { NoticeList } from "@components/Notice"
import PageTitle from "@components/PageTitle"
import SchemaForm, { type FormValues } from "@components/SchemaForm"
import TemplateGuide from "@components/TemplateGuide"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import { useDrafts } from "@hooks/useDrafts"
import { setIngestion } from "@store/chainSlice"
import type { FormSchema, InspectionResult } from "src/types/reportingType"

const MODULE_KEY = "aifmd"

const PLACEHOLDER = [
    "{",
    '  "period_start": "2025-10-01",',
    '  "period_end": "2025-12-31",',
    '  "aifm_info": { "aifm_national_code": "A12345678", "aifm_name": "..." },',
    '  "aif_info": { "aif_name": "Fund", "aif_domicile": "LU" }',
    "}",
].join("\n")

type Submission = {
    period_start?: string
    period_end?: string
    aifm_info?: Record<string, unknown>
    aif_info?: Record<string, unknown>
}

/**
 * AIFMD Annex IV ingestion.
 *
 * Three ways in, and all three end at the same place — the two dictionaries
 * the engine reads, `aifm_info` and `aif_info`:
 *
 *  - ESMA's consolidated template, filled offline and read back here;
 *  - a filing produced earlier, re-opened and checked against the schema;
 *  - the submission typed directly, which is also what the other two
 *    produce, so whatever route was taken the result is reviewable and
 *    correctable in one place.
 */
const AifmdIngestion: React.FC = () => {
    const { chain, dispatch } = useChain(MODULE_KEY)
    const [text, setText] = useState(() =>
        chain.ingestion ? JSON.stringify(chain.ingestion, null, 2) : "")
    const [inspection, setInspection] = useState<InspectionResult | null>(null)
    const [parseErrors, setParseErrors] = useState<string[]>([])
    const [busy, setBusy] = useState(false)
    const [schema, setSchema] = useState<FormSchema | null>(null)
    const [showJson, setShowJson] = useState(false)
    const [formOpen, setFormOpen] = useState(false)

    useEffect(() => {
        fetchFilingForm(MODULE_KEY)
            .then(setSchema)
            .catch((error: Error) => toast.error(error.message))
    }, [])

    const submission = chain.ingestion as Submission | null
    const drafts = useDrafts<Submission>(MODULE_KEY,
        (data) => dispatch(setIngestion({ module: MODULE_KEY, data })),
        () => setFormOpen(true))

    const keep = (next: unknown, message: string) => {
        dispatch(setIngestion({ module: MODULE_KEY, data: next }))
        setText(JSON.stringify(next, null, 2))
        toast.success(message)
    }

    const save = () => {
        try {
            dispatch(setIngestion({ module: MODULE_KEY, data: JSON.parse(text || "{}") }))
            toast.success("Submission saved to the chain.")
        } catch (error) {
            toast.error(`This is not valid JSON: ${(error as Error).message}`)
        }
    }

    const readTemplate = async (file: File) => {
        setBusy(true)
        setParseErrors([])
        try {
            const parsed = await parseAifmdTemplate(file)
            setParseErrors(parsed.errors ?? [])
            // The reporting period is not in the workbook, so whatever was
            // already captured for it is kept rather than blanked.
            keep({
                period_start: submission?.period_start ?? "",
                period_end: submission?.period_end ?? "",
                aifm_info: parsed.aifm_info ?? {},
                aif_info: parsed.aif_info ?? {},
            }, parsed.errors?.length
                ? `Workbook read, with ${parsed.errors.length} problem(s) to fix.`
                : "Workbook read.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const openFiling = async (file: File) => {
        setBusy(true)
        try {
            const found = await inspectAifmdFile(file)
            setInspection(found)
            if (!found.recognised) {
                toast.error("This file is not an AIFMD Annex IV filing.")
                return
            }
            if (found.schema_validation.valid) {
                toast.success(`Identified as ${found.label}, valid against ESMA's schema.`)
            } else {
                toast.warning(`Identified as ${found.label}, but it does not satisfy ESMA's schema.`)
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const counts = submission
        ? [
            ["AIFM items", Object.keys(submission.aifm_info ?? {}).length],
            ["AIF items", Object.keys(submission.aif_info ?? {}).length],
        ] as [string, number][]
        : []

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow="AIFMD Annex IV" title="Ingestion"
                subtitle="The two dictionaries the engine reads, aifm_info and aif_info, plus the
                          reporting period. Dates are ISO strings." />

            <IngestionPanel regime="AIFMD Annex IV" busy={busy} actions={[
                { label: "Download template", href: aifmdTemplateUrl(),
                  hint: "the blank workbook, 38 AIFM items and 301 AIF items" },
                { label: "Import a filled-in workbook", accept: ".xlsx,.xlsm", onFile: readTemplate,
                  primary: true, hint: "read straight into the submission below" },
                { label: "Open an existing XML filing", accept: ".xml", onFile: openFiling,
                  hint: "identified and validated against ESMA's schema on the spot" },
                { label: "Saved drafts", onClick: () => drafts.setPanelOpen(true),
                  hint: "re-open a submission saved earlier" },
            ]}
                formOpen={formOpen} onToggleForm={() => setFormOpen(!formOpen)}>
                {parseErrors.length > 0 && (
                    <div className="border-t border-slate-100 pt-1">
                        <Notice eyebrow="Workbook" title={`${parseErrors.length} problem(s) in the workbook`}>
                            <NoticeList items={parseErrors.slice(0, 15)}
                                more={Math.max(0, parseErrors.length - 15)} />
                        </Notice>
                    </div>
                )}

                {inspection?.recognised && (
                    <div className="flex flex-col gap-2 border-t border-slate-100 pt-3">
                        <p className="text-sm text-slate-700">
                            Identified as <strong>{inspection.label}</strong>, {inspection.record_count}{" "}
                            record(s).
                        </p>
                        <ValidationReport validation={{
                            valid: inspection.schema_validation.valid,
                            errors: inspection.schema_validation.valid ? [] :
                                inspection.schema_validation.errors.map((message) => ({
                                    level: "error" as const, code: "XSD", message,
                                })),
                            warnings: [],
                        }} />
                    </div>
                )}
            </IngestionPanel>

            {counts.length > 0 && (
                <div className="flex flex-wrap gap-3">
                    {counts.map(([label, count]) => (
                        <span key={label}
                            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm">
                            <span className="text-slate-600">{label}</span>{" "}
                            <span className="font-semibold text-slate-900">{count}</span> captured
                        </span>
                    ))}
                </div>
            )}

            {schema && (
                <TemplateGuide schema={schema} values={(submission ?? {}) as Record<string, unknown>} />
            )}

            {formOpen && (
                <div id={FORM_ANCHOR} className="flex flex-col gap-6">
                    {schema
                        ? (
                            <SchemaForm schema={schema} values={(submission ?? {}) as FormValues}
                                onChange={(next) =>
                                    dispatch(setIngestion({ module: MODULE_KEY, data: next }))} />
                        )
                        : <p className="text-sm text-slate-500">Loading the form…</p>}

                    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
                        <input value={drafts.name} onChange={(event) => drafts.setName(event.target.value)}
                            placeholder="Name this draft"
                            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none
                                       focus:border-[#0A2647]" />
                        <button type="button" onClick={() => drafts.save(submission ?? {})}
                            className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                                       text-[#0A2647] transition hover:bg-slate-100">
                            Save this submission as a draft
                        </button>
                    </div>
                </div>
            )}

            {drafts.panelOpen && (
                <DraftsPanel moduleKey={MODULE_KEY} moduleLabel="AIFMD Annex IV"
                    onOpen={drafts.open} onClose={() => drafts.setPanelOpen(false)} />
            )}

            <section className="flex flex-col gap-3">
                <button type="button" onClick={() => setShowJson(!showJson)}
                    className="w-fit rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700
                               transition hover:border-[#0A2647]">
                    {showJson ? "Hide" : "Show"} the submission as JSON
                </button>
                {showJson && (
                    <>
                        <p className="text-sm text-slate-600">
                            The same submission, editable as text. Useful for an item the form does not
                            reach yet, or to paste one prepared elsewhere.
                        </p>
                        <textarea value={text} onChange={(event) => setText(event.target.value)} rows={18}
                            spellCheck={false} placeholder={PLACEHOLDER}
                            className="w-full rounded-lg border border-slate-300 bg-white p-3 font-mono
                                       text-xs outline-none focus:border-[#0A2647]" />
                        <button type="button" onClick={save}
                            className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                       transition hover:bg-[#123A6B]">
                            Apply this JSON to the form
                        </button>
                    </>
                )}
            </section>

        </section>
    )
}

export default AifmdIngestion
