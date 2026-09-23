import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import {
    classifyFatca, fatcaTemplateUrl, fetchFilerCategories, fetchPreparers, inspectFilingFile,
} from "@api/reportingApi"
import DraftsPanel from "@components/DraftsPanel"
import IngestionPanel, { FORM_ANCHOR } from "@components/IngestionPanel"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import { useChain } from "@hooks/useChain"
import { useDrafts } from "@hooks/useDrafts"
import { setIngestion } from "@store/chainSlice"
import { keepFile } from "@store/fileVault"
import type { FatcaClassification, InspectionResult } from "src/types/reportingType"

export type FatcaParameters = {
    crs_fatca: "CRS" | "FATCA"
    report_type: "Data Report" | "Zero Report"
    selection: "Initial" | "Correction"
    version: string
    filer_category: string | null
    preparer: string
}

/**
 * FATCA & CRS ingestion: the reporting parameters, and the workbook the
 * accounts are classified from.
 *
 * The parameters are not cosmetic — the regime, report type and selection
 * together pick which of the AEOI documents the generator builds, so they
 * are captured before the workbook rather than after it.
 */
const FatcaIngestion: React.FC = () => {
    const { chain, dispatch } = useChain("fatca")
    const stored = chain.ingestion as { parameters?: FatcaParameters; classification?: FatcaClassification } | null

    const [preparers, setPreparers] = useState<string[]>([])
    const [categories, setCategories] = useState<string[]>([])
    const [parameters, setParameters] = useState<FatcaParameters>(stored?.parameters ?? {
        crs_fatca: "CRS", report_type: "Data Report", selection: "Initial",
        version: "1", filer_category: null, preparer: "",
    })
    const [busy, setBusy] = useState(false)
    const [formOpen, setFormOpen] = useState(true)
    const [inspection, setInspection] = useState<InspectionResult | null>(null)
    const drafts = useDrafts<FatcaParameters>("fatca", setParameters,
        () => setFormOpen(true))

    useEffect(() => {
        fetchPreparers()
            .then((found) => {
                const names = Object.keys(found)
                setPreparers(names)
                setParameters((current) =>
                    current.preparer || !names.length ? current : { ...current, preparer: names[0] })
            })
            .catch(() => setPreparers([]))
        fetchFilerCategories().then(setCategories).catch(() => setCategories([]))
    }, [])

    // A zero report has nothing to correct and carries no version.
    const zero = parameters.report_type === "Zero Report"

    const upload = async (file: File) => {
        setBusy(true)
        try {
            const classification = await classifyFatca(file, {
                ...parameters, version: zero ? "0" : parameters.version,
            })
            keepFile("fatca", file)
            dispatch(setIngestion({ module: "fatca", data: { parameters, classification } }))
            toast.success("Workbook classified.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const openFiling = async (file: File) => {
        setBusy(true)
        try {
            const found = await inspectFilingFile("fatca", file)
            setInspection(found)
            if (found.recognised) {
                toast.info(`Identified as ${found.label}. No schema is bundled to check it against.`)
            } else {
                toast.error("This file could not be read as an AEOI return.")
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const set = <K extends keyof FatcaParameters>(key: K, value: FatcaParameters[K]) =>
        setParameters((current) => ({ ...current, [key]: value }))

    const classification = stored?.classification
    const counts = classification?.counts ?? {}

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="FATCA & CRS — Ingestion"
                subtitle="The reporting parameters this filing is built under, and the data report
                          workbook the accounts are classified from." />

            <section className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
                <IngestionPanel regime="FATCA & CRS" busy={busy} actions={[
                    { label: "Download template", href: fatcaTemplateUrl(),
                      hint: "the real template used by the reporting team" },
                    { label: busy ? "Classifying\u2026" : "Import a filled-in workbook",
                      accept: ".xlsx,.xlsm", onFile: upload, primary: true,
                      hint: "every account is classified on the way in" },
                    { label: "Open an existing XML filing", accept: ".xml", onFile: openFiling,
                      hint: "read back and identified; the AEOI schemas are not bundled" },
                    { label: "Saved drafts", onClick: () => drafts.setPanelOpen(true),
                      hint: "re-open the reporting parameters saved earlier" },
                ]}
                    formOpen={formOpen} onToggleForm={() => setFormOpen(!formOpen)}>
                    {inspection?.recognised && (
                        <div className="flex flex-col gap-2 border-t border-slate-100 pt-3">
                            <p className="text-sm text-slate-700">
                                Identified as <strong>{inspection.label}</strong>
                                <span className="ml-2 text-xs text-slate-500">
                                    {inspection.schema_validation.detail}
                                </span>
                            </p>
                        </div>
                    )}

                    <p className="text-xs text-slate-500">
                        The classification codes (Active NFE, Passive NFE, Controlling Person,
                        Individual), the reference-ID generation and the AEOI XML structure are reused
                        verbatim from the reporting team's production engine. The rules engine step shows
                        the classification in detail before anything is generated.
                    </p>
                </IngestionPanel>

                {formOpen && (
                <div id={FORM_ANCHOR}
                    className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                    <h2 className="text-sm font-semibold text-slate-900">Reporting parameters</h2>

                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Preparer</span>
                        {preparers.length === 0 ? (
                            <span className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs
                                             text-amber-800">
                                None configured yet — add one at the configuration step.
                            </span>
                        ) : (
                            <select value={parameters.preparer}
                                onChange={(event) => set("preparer", event.target.value)}
                                className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                           focus:border-[#0A2647]">
                                {preparers.map((name) => <option key={name} value={name}>{name}</option>)}
                            </select>
                        )}
                    </label>

                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Regime</span>
                        <select value={parameters.crs_fatca}
                            onChange={(event) => set("crs_fatca", event.target.value as "CRS" | "FATCA")}
                            className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                       focus:border-[#0A2647]">
                            <option value="CRS">CRS</option>
                            <option value="FATCA">FATCA</option>
                        </select>
                    </label>

                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Type of report</span>
                        <select value={parameters.report_type}
                            onChange={(event) => {
                                const value = event.target.value as FatcaParameters["report_type"]
                                setParameters((current) => ({
                                    ...current, report_type: value,
                                    // A zero report is always an initial one.
                                    selection: value === "Zero Report" ? "Initial" : current.selection,
                                }))
                            }}
                            className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                       focus:border-[#0A2647]">
                            <option value="Data Report">Data Report</option>
                            <option value="Zero Report">Zero Report</option>
                        </select>
                    </label>

                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Selection</span>
                        <select value={parameters.selection} disabled={zero}
                            onChange={(event) => set("selection", event.target.value as "Initial" | "Correction")}
                            className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                       focus:border-[#0A2647] disabled:bg-slate-50">
                            <option value="Initial">Initial</option>
                            {!zero && <option value="Correction">Correction</option>}
                        </select>
                    </label>

                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Version</span>
                        <input value={zero ? "0" : parameters.version} disabled={zero}
                            onChange={(event) => set("version", event.target.value)}
                            placeholder="e.g. 1, 2A, 3C"
                            className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                       focus:border-[#0A2647] disabled:bg-slate-50" />
                    </label>

                    {parameters.crs_fatca === "FATCA" && (
                        <label className="flex flex-col gap-1 text-sm">
                            <span className="font-medium text-slate-700">FI filer category</span>
                            <select value={parameters.filer_category ?? ""}
                                onChange={(event) => set("filer_category", event.target.value || null)}
                                className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                           focus:border-[#0A2647]">
                                <option value="">—</option>
                                {categories.map((name) => <option key={name} value={name}>{name}</option>)}
                            </select>
                        </label>
                    )}
                    <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3">
                        <input value={drafts.name} onChange={(event) => drafts.setName(event.target.value)}
                            placeholder="Name this draft"
                            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm
                                       outline-none focus:border-[#0A2647]" />
                        <button type="button" onClick={() => drafts.save(parameters)}
                            className="rounded-md border border-[#0A2647] px-3 py-2 text-sm font-medium
                                       text-[#0A2647] transition hover:bg-slate-100">
                            Save
                        </button>
                    </div>
                </div>
                )}
            </section>

            {drafts.panelOpen && (
                <DraftsPanel moduleKey="fatca" moduleLabel="FATCA & CRS"
                    onOpen={drafts.open} onClose={() => drafts.setPanelOpen(false)} />
            )}

            {classification && (
                <>
                    <KpiRow items={Object.entries(counts).map(([label, value]) => ({
                        label: label.replace(/_/g, " "), value: String(value),
                    }))} />

                    {classification.warnings.length > 0 && (
                        <section className="flex flex-col gap-1">
                            <h2 className="text-sm font-semibold text-slate-900">Warnings</h2>
                            {classification.warnings.map((message, index) => (
                                <p key={index} className="rounded-md border border-amber-200 bg-amber-50
                                                          px-3 py-2 text-sm text-amber-800">
                                    {message}
                                </p>
                            ))}
                        </section>
                    )}
                </>
            )}
        </section>
    )
}

export default FatcaIngestion
