import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { bclReferenceUrl, fetchBclCodes, fetchBclReports, runBclCrossChecks } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import type { BclCodes, BclReport, ValidationResult } from "src/types/reportingType"
import type { BclDraft } from "./Ingestion"

const MODULE_KEY = "bcl"

/** "(1)" in a chart of accounts means the amount must be broken down over
 *  that dimension rather than carrying a fixed code. */
const BREAKDOWN = "(1)"

/**
 * The rules BCL checks a report against: the code lists a breakdown must
 * draw from, the chart of accounts of the selected report, and the
 * cross-checks that run between reports rather than inside one.
 */
const BclRules: React.FC = () => {
    const { chain } = useChain(MODULE_KEY)
    const draft = chain.ingestion as BclDraft | null

    const [reports, setReports] = useState<BclReport[]>([])
    const [codes, setCodes] = useState<BclCodes | null>(null)
    const [crossChecks, setCrossChecks] = useState<ValidationResult | null>(null)

    useEffect(() => {
        Promise.all([fetchBclReports(), fetchBclCodes()])
            .then(([reportsResponse, codesResponse]) => {
                setReports(reportsResponse.reports)
                setCodes(codesResponse)
            })
            .catch((error: Error) => toast.error(error.message))
    }, [])

    const report = reports.find((candidate) => candidate.key === (draft?.report_key ?? "s13"))
    const lines = [...(report?.assets ?? []), ...(report?.liabilities ?? [])]
    /** An item counts as captured once it carries at least one reported row.
     *  An item broken down over several countries is still one chart line. */
    const filled = new Set(
        Object.entries({ ...(draft?.assets ?? {}), ...(draft?.liabilities ?? {}) })
            .filter(([, rows]) => (rows ?? []).some((row) => row.amount !== ""))
            .map(([item]) => item))

    const check = async () => {
        try {
            setCrossChecks(await runBclCrossChecks(draft ?? {}))
            toast.success("Cross-checks run.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="BCL statistical reports — Rules Engine"
                subtitle="The code lists a breakdown must draw from, the chart of accounts of the report
                          being captured, and the checks BCL runs between reports." />

            {codes && (
                <KpiRow items={[
                    { label: "Economic sector codes", value: String(Object.keys(codes.sectors).length),
                      hint: "BCL 2015 classification" },
                    { label: "Initial maturity codes", value: String(Object.keys(codes.maturities).length),
                      hint: "" },
                    { label: "Chart of accounts", value: String(lines.length),
                      hint: `${filled.size} line(s) captured` },
                    { label: "Schema validation",
                      value: codes.schema_validation_available ? "Available" : "Unavailable",
                      hint: "against BCL's own XSD" },
                ]} />
            )}

            {report && (
                <section className="flex flex-col gap-3">
                    <h2 className="text-sm font-semibold text-slate-900">
                        {report.label} — the regulator's own documents
                    </h2>
                    <div className="flex flex-wrap gap-2">
                        {([
                            ["instructions", "Instructions", "BCL's own filing instructions for this report"],
                            ["rules", "Verification rules", "the compendium the generation step checks against"],
                            ["report", "Chart of accounts", "the official sheet the capture form reproduces"],
                        ] as const).map(([kind, label, hint]) => (
                            <a key={kind} href={bclReferenceUrl(report.key, kind)} title={hint}
                                className="flex flex-col rounded-md border border-slate-300 px-3 py-2
                                           transition hover:border-[#0A2647]">
                                <span className="text-xs font-semibold text-slate-800">{label}</span>
                                <span className="text-[11px] text-slate-500">{hint}</span>
                            </a>
                        ))}
                    </div>
                </section>
            )}

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">
                    Chart of accounts — {report?.label ?? "—"}
                </h2>
                <div className="max-h-[520px] overflow-auto rounded-lg border border-slate-200 bg-white">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase
                                          tracking-wide text-slate-500">
                            <tr>
                                <th className="px-3 py-2">Item</th>
                                <th className="px-3 py-2">Label</th>
                                <th className="px-3 py-2">Country</th>
                                <th className="px-3 py-2">Currency</th>
                                <th className="px-3 py-2">Sector</th>
                                <th className="px-3 py-2">Maturity</th>
                                <th className="px-3 py-2 text-center">Captured</th>
                            </tr>
                        </thead>
                        <tbody>
                            {lines.map((line) => (
                                <tr key={line.item} className="border-t border-slate-100">
                                    <td className="px-3 py-2 font-mono text-xs">{line.item}</td>
                                    <td className="px-3 py-2">{line.label}</td>
                                    {([line.country, line.currency, line.sector, line.maturity]).map(
                                        (code, index) => (
                                            <td key={index} className="px-3 py-2 font-mono text-xs">
                                                {code === BREAKDOWN
                                                    ? <span className="text-amber-700">breakdown</span>
                                                    : <span className="text-slate-500">{code}</span>}
                                            </td>
                                        ))}
                                    <td className="px-3 py-2 text-center">
                                        {filled.has(line.item)
                                            ? <span className="text-emerald-600">✓</span>
                                            : <span className="text-slate-300">—</span>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                <p className="text-xs text-slate-500">
                    A dimension marked “breakdown” means the amount must be split over that dimension
                    rather than reported against a single fixed code.
                </p>
            </section>

            <section className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-slate-900">Cross-report checks</h2>
                <p className="text-sm text-slate-600">
                    Some of BCL's rules compare one report against another — the balance sheet against
                    TPTOBS, and against S 2.20 — so they cannot be checked from a single report alone.
                </p>
                <button type="button" onClick={check} disabled={!draft}
                    className="w-fit rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                               text-[#0A2647] transition hover:bg-slate-100 disabled:opacity-40">
                    Run the cross-checks
                </button>
                {crossChecks && <ValidationReport validation={crossChecks} />}
            </section>
        </section>
    )
}

export default BclRules
