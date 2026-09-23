import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { fetchBclReports, generateBclReport, inspectBclFile, recordGenerated } from "@api/reportingApi"
import FileDownload from "@components/FileDownload"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import { useCurrentUser } from "@hooks/useCurrentUser"
import { setGeneration } from "@store/chainSlice"
import type {
    BclChartLine, BclReport, GenerationResult, InspectionResult,
} from "src/types/reportingType"
import type { BclDraft, ItemRows } from "./Ingestion"
import { dateOrNull, numberOrNull } from "./forms/fields"

const MODULE_KEY = "bcl"

/**
 * The rows the preparer actually reported, flattened into the lines BCL
 * expects.
 *
 * An item can carry several rows — one per country, currency, sector or
 * maturity it is broken down over — and each is a line of its own in the
 * filing. An item with no rows is absent: BCL reads an absent line as "not
 * reported", which is not the same statement as a zero.
 *
 * The total line is the exception. It is always sent, and computed, because
 * the regulator rejects a report whose total does not match its detail.
 */
function buildLines(
    chart: BclChartLine[] | undefined, rows: ItemRows, totalItem: string, total: number,
) {
    const lines = (chart ?? [])
        .filter((line) => line.item !== totalItem)
        .flatMap((line) => (rows[line.item] ?? [])
            .filter((row) => row.amount !== "")
            .map((row) => ({
                item: line.item,
                country: row.country, currency: row.currency,
                sector: row.sector, maturity: row.maturity,
                amount: Number.parseFloat(row.amount),
            })))
    if (!lines.length) return []

    const totalLine = (chart ?? []).find((line) => line.item === totalItem)
    return totalLine
        ? [...lines, {
            item: totalLine.item, country: totalLine.country, currency: totalLine.currency,
            sector: totalLine.sector, maturity: totalLine.maturity, amount: total,
        }]
        : lines
}

/**
 * One unit/share class, typed the way the API declares it.
 *
 * The form keeps every field as a string, because that is what an input
 * holds. The model does not: the specific-instrument items are flags, the
 * investor base and the reason for closing are codes, and an unreported
 * amount is null rather than zero — so the conversion happens once, here,
 * at the boundary.
 */
const SHARE_CLASS_FLAGS = ["spec_instr_fx", "spec_instr_interest_rate", "spec_instr_other"]
const SHARE_CLASS_CODES = ["investor_base", "reason_for_closing"]
const SHARE_CLASS_DATES = ["launch_date", "closing_date"]
const SHARE_CLASS_TEXT = ["cssf_code", "name", "base_currency", "isin"]

function shareClassPayload(row: Record<string, string>): Record<string, unknown> {
    return Object.fromEntries(Object.entries(row).map(([key, value]) => {
        if (SHARE_CLASS_FLAGS.includes(key)) return [key, value === "true"]
        if (SHARE_CLASS_CODES.includes(key)) {
            return [key, value === "" ? null : Number.parseInt(value, 10)]
        }
        if (SHARE_CLASS_DATES.includes(key)) return [key, dateOrNull(value)]
        if (SHARE_CLASS_TEXT.includes(key)) return [key, value]
        return [key, numberOrNull(value)]
    }))
}

const sumOf = (chart: BclChartLine[] | undefined, rows: ItemRows, totalItem: string) =>
    (chart ?? [])
        .filter((line) => line.item !== totalItem)
        .flatMap((line) => rows[line.item] ?? [])
        .reduce((total, row) => total + (Number.parseFloat(row.amount) || 0), 0)

/**
 * Builds the XML of the report captured at the ingestion step, validated
 * against BCL's own XSD and its compendium of verification rules before it
 * can be downloaded.
 */
const BclGeneration: React.FC = () => {
    const { name: user } = useCurrentUser()
    const { chain, dispatch } = useChain(MODULE_KEY)
    const draft = chain.ingestion as BclDraft | null

    const [reports, setReports] = useState<BclReport[]>([])
    const [outcome, setOutcome] = useState<GenerationResult | null>(null)
    const [inspection, setInspection] = useState<InspectionResult | null>(null)
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        fetchBclReports()
            .then((response) => setReports(response.reports))
            .catch((error: Error) => toast.error(error.message))
    }, [])

    const report = reports.find((candidate) => candidate.key === draft?.report_key)

    /** The six reports take six different payloads. Each one is assembled
     *  from the draft the capture screen kept for that report, so switching
     *  reports never sends one report's data under another's shape. */
    const payloadFor = (key: string) => {
        if (key === "s44") {
            const s44 = draft?.s44
            return {
                header: s44?.header ?? {},
                marketing_countries: (s44?.marketing_countries ?? [])
                    .filter((row) => row.country && row.amount !== "")
                    .map((row) => ({ item: "2-004000", country: row.country,
                                     amount: numberOrNull(row.amount) })),
            }
        }
        if (key === "tptobs") {
            const tptobs = draft?.tptobs
            return {
                header: tptobs?.header ?? {},
                securities: (tptobs?.securities ?? []).map((row) => ({
                    ...row,
                    nominal_amount: numberOrNull(row.nominal_amount ?? ""),
                    number_of_units: numberOrNull(row.number_of_units ?? ""),
                    reported_amount: numberOrNull(row.reported_amount ?? ""),
                    pool_factor: numberOrNull(row.pool_factor ?? ""),
                    coupon_rate: numberOrNull(row.coupon_rate ?? ""),
                    distributed_amount: numberOrNull(row.distributed_amount ?? ""),
                    split_ratio: numberOrNull(row.split_ratio ?? ""),
                    date_of_issue: dateOrNull(row.date_of_issue ?? ""),
                    date_of_final_maturity: dateOrNull(row.date_of_final_maturity ?? ""),
                    last_coupon_payment_date: dateOrNull(row.last_coupon_payment_date ?? ""),
                    split_date: dateOrNull(row.split_date ?? ""),
                })),
            }
        }
        if (key === "s220") {
            const s220 = draft?.s220
            const scalars = s220?.scalars ?? {}
            // The model types each item; an empty field means "not reported"
            // rather than zero, so it is sent as null and not as "".
            const NUMERIC = new Set(Object.keys(scalars).filter((name) =>
                /^(nav_|units_|total_|dividends|interest|bank_|other_|rental|commission|charges|advisory|depositary|administration|audit|distribution|subscription|performance|personnel|amortisation|net_)/
                    .test(name)))
            const DATES = new Set(["valuation_date", "launch_date", "closing_date"])
            const INTEGERS = new Set(["nav_freq", "nav_redemption_freq", "open_closed_end",
                                      "reason_for_closing"])
            const coerced = Object.fromEntries(Object.entries(scalars).map(([name, value]) => {
                if (DATES.has(name)) return [name, dateOrNull(value)]
                if (INTEGERS.has(name)) return [name, value === "" ? null : Number.parseInt(value, 10)]
                if (NUMERIC.has(name)) return [name, numberOrNull(value)]
                return [name, value]
            }))
            return {
                ...coerced,
                sender_employees: s220?.sender_employees ?? [],
                share_classes: (s220?.share_classes ?? []).map(shareClassPayload),
            }
        }
        const assetsTotal = sumOf(report?.assets, draft?.assets ?? {}, "1-000000")
        const liabilitiesTotal = sumOf(report?.liabilities, draft?.liabilities ?? {}, "2-000000")
        return {
            header: draft?.header ?? {},
            assets: buildLines(report?.assets, draft?.assets ?? {}, "1-000000", assetsTotal),
            liabilities: buildLines(report?.liabilities, draft?.liabilities ?? {},
                                    "2-000000", liabilitiesTotal),
        }
    }

    const run = async () => {
        if (!draft || !report) return
        setBusy(true)
        try {
            const produced = await generateBclReport(draft.report_key, payloadFor(draft.report_key))
            setOutcome(produced)
            dispatch(setGeneration({
                module: MODULE_KEY, files: produced.files, validation: produced.validation,
            }))

            if (produced.generated) {
                const file = produced.files[0]
                if (user) await recordGenerated(MODULE_KEY, file.filename, file.label, user)
                toast.success(`${report.label} generated.`)
            } else {
                toast.error(`${produced.validation.errors.length} control(s) would reject this filing.`)
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const inspect = async (file: File) => {
        try {
            const found = await inspectBclFile(file)
            setInspection(found)
            if (found.recognised) toast.success(`Identified as ${found.label}.`)
            else toast.error("This file is not one of the six BCL reports.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="BCL statistical reports — XML Generation"
                subtitle="Builds the report captured at the ingestion step, validated against BCL's own
                          schema and its verification rules before it can be downloaded." />

            {!draft || !report ? (
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    Nothing has been captured yet. Pick a report and fill it in at the ingestion step first.
                </p>
            ) : (
                <>
                    <article className="rounded-lg border border-slate-200 bg-white p-5">
                        <h2 className="font-semibold text-slate-900">{report.label}</h2>
                        <p className="text-sm text-slate-600">{report.description}</p>
                        <p className="mt-1 text-xs text-slate-500">
                            {report.frequency} · root <code>{report.root}</code> · layout {report.layout}
                        </p>
                    </article>

                    {!user && (
                        <p className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm
                                      text-amber-800">
                            Enter your name in the header — a generated filing is registered in the audit
                            trail against whoever prepared it.
                        </p>
                    )}

                    <button type="button" onClick={run} disabled={busy}
                        className="w-fit rounded-md bg-[#0A2647] px-5 py-2.5 text-sm font-medium text-white
                                   transition hover:bg-[#123A6B] disabled:opacity-50">
                        {busy ? "Generating…" : `Generate ${report.label} XML`}
                    </button>
                </>
            )}

            {outcome && (
                <section className="flex flex-col gap-3">
                    <h2 className="text-sm font-semibold text-slate-900">Validation</h2>
                    <ValidationReport validation={outcome.validation} />
                    {outcome.files.map((file) => <FileDownload key={file.key} file={file} />)}
                </section>
            )}

            <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-slate-900">Check an existing filing</h2>
                <p className="text-sm text-slate-600">
                    Upload an XML file to identify which of the six reports it is and validate it against
                    that report's own schema.
                </p>
                <input type="file" accept=".xml" className="text-sm"
                    onChange={(event) => event.target.files?.[0] && inspect(event.target.files[0])} />
                {inspection && (
                    <div className="flex flex-col gap-2">
                        <p className="text-sm text-slate-700">
                            {inspection.recognised
                                ? <>Identified as <strong>{inspection.label}</strong>.</>
                                : "Not recognised as a BCL report."}
                        </p>
                        {inspection.recognised && (
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
            </section>
        </section>
    )
}

export default BclGeneration
