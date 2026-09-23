import { useEffect, useMemo, useState } from "react"
import { toast } from "react-toastify"

import { bclReferenceUrl, fetchBclCodes, fetchBclReports, inspectBclFile } from "@api/reportingApi"
import DraftsPanel from "@components/DraftsPanel"
import IngestionPanel, { FORM_ANCHOR } from "@components/IngestionPanel"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import { useDrafts } from "@hooks/useDrafts"
import { setIngestion } from "@store/chainSlice"
import type {
    BclChartLine, BclCodes, BclReport, InspectionResult,
} from "src/types/reportingType"
import S220Form, { emptyS220, type S220Draft } from "./bcl/S220Form"
import S44Form, { emptyS44, type S44Draft } from "./bcl/S44Form"
import TptobsForm, { emptyTptobs, type TptobsDraft } from "./bcl/TptobsForm"

const MODULE_KEY = "bcl"
const LEDGER_KEYS = ["s13", "s213", "s16"]

/**
 * BCL prints "(1)" in a chart-of-accounts cell to mean "this amount must be
 * broken down over this dimension". It is an instruction, not a code: a line
 * sent with "(1)" as its country is rejected (LED-005) and the whole report
 * refused.
 *
 * So a chart line is a template, not a row. An item whose country is "(1)"
 * is reported as one row per country the fund is exposed to, each with its
 * own amount; an item with fixed codes everywhere is reported once. That is
 * what this screen captures.
 */
const BREAK = "(1)"

export type HeaderState = {
    end_month_date: string
    closing_date: string
    reporter_type: string
    reporter_code: string
    declarant_type: string
    declarant_code: string
    reporting_currency: string
}

const EMPTY_HEADER: HeaderState = {
    end_month_date: "", closing_date: "", reporter_type: "", reporter_code: "",
    declarant_type: "", declarant_code: "", reporting_currency: "EUR",
}

/** One reported row: the four dimension codes, and the amount. */
export type BreakdownRow = {
    country: string
    currency: string
    sector: string
    maturity: string
    amount: string
}

/** Every row captured against a chart item, keyed by item code. */
export type ItemRows = Record<string, BreakdownRow[]>

/**
 * One draft per report, all carried together.
 *
 * The six reports have nothing in common beyond their header: three are
 * balance sheets against a chart of accounts, one is a list of marketing
 * countries, one a list of securities and one a description of the fund. So
 * each keeps its own shape, and switching reports never discards what was
 * captured for another.
 */
export type BclDraft = {
    report_key: string
    header: HeaderState
    assets: ItemRows
    liabilities: ItemRows
    s44?: S44Draft
    tptobs?: TptobsDraft
    s220?: S220Draft
}

/** A fresh row starts from the chart line, so the dimensions BCL fixes are
 *  already right and only the ones it asks to be broken down are empty. */
const rowFor = (line: BclChartLine): BreakdownRow => ({
    country: line.country === BREAK ? "" : line.country,
    currency: line.currency === BREAK ? "" : line.currency,
    sector: line.sector === BREAK ? "" : line.sector,
    maturity: line.maturity === BREAK ? "" : line.maturity,
    amount: "",
})

const sumOf = (rows: ItemRows, lines: BclChartLine[] | undefined, totalItem: string) =>
    (lines ?? [])
        .filter((line) => line.item !== totalItem)
        .flatMap((line) => rows[line.item] ?? [])
        .reduce((total, row) => total + (Number.parseFloat(row.amount) || 0), 0)

const BclIngestion: React.FC = () => {
    const { chain, dispatch } = useChain(MODULE_KEY)
    const saved = chain.ingestion as BclDraft | null

    const [reports, setReports] = useState<BclReport[]>([])
    const [codes, setCodes] = useState<BclCodes | null>(null)
    const [reportKey, setReportKey] = useState(saved?.report_key ?? "s13")
    const [header, setHeader] = useState<HeaderState>(saved?.header ?? EMPTY_HEADER)
    const [assets, setAssets] = useState<ItemRows>(saved?.assets ?? {})
    const [liabilities, setLiabilities] = useState<ItemRows>(saved?.liabilities ?? {})
    const [s44, setS44] = useState<S44Draft>(saved?.s44 ?? emptyS44())
    const [tptobs, setTptobs] = useState<TptobsDraft>(saved?.tptobs ?? emptyTptobs())
    const [s220, setS220] = useState<S220Draft>(saved?.s220 ?? emptyS220())
    const [inspection, setInspection] = useState<InspectionResult | null>(null)
    const [busy, setBusy] = useState(false)
    const [formOpen, setFormOpen] = useState(false)

    /** Re-opening a draft restores the whole capture state, whichever of the
     *  six reports it was captured for. */
    const drafts = useDrafts<BclDraft>(MODULE_KEY, (data) => {
        if (data.report_key) setReportKey(data.report_key)
        if (data.header) setHeader(data.header)
        setAssets(data.assets ?? {})
        setLiabilities(data.liabilities ?? {})
        if (data.s44) setS44(data.s44)
        if (data.tptobs) setTptobs(data.tptobs)
        if (data.s220) setS220(data.s220)
    }, () => setFormOpen(true))

    useEffect(() => {
        Promise.all([fetchBclReports(), fetchBclCodes()])
            .then(([reportsResponse, codesResponse]) => {
                setReports(reportsResponse.reports)
                setCodes(codesResponse)
            })
            .catch((error: Error) => toast.error(error.message))
    }, [])

    const report = useMemo(
        () => reports.find((candidate) => candidate.key === reportKey), [reports, reportKey])
    const isLedger = LEDGER_KEYS.includes(reportKey)
    const hasMaturity = report?.has_maturity !== false

    const assetsTotal = sumOf(assets, report?.assets, "1-000000")
    const liabilitiesTotal = sumOf(liabilities, report?.liabilities, "2-000000")

    /** What the generation step will build from. The captured form is put on
     *  the chain as it is edited, rather than behind a save button: a step
     *  the preparer navigated away from must not lose what they typed. */
    useEffect(() => {
        dispatch(setIngestion({
            module: MODULE_KEY,
            data: { report_key: reportKey, header, assets, liabilities, s44, tptobs, s220 },
        }))
    }, [dispatch, reportKey, header, assets, liabilities, s44, tptobs, s220])


    /**
     * Re-open a filing produced earlier.
     *
     * BCL reports are filed as XML straight to eDesk rather than round-tripped
     * through a workbook, so this is how an existing filing comes back in: it
     * is identified and validated against that report's own XSD on the spot,
     * and the chain switches to whichever of the six it turns out to be.
     */
    const openFiling = async (file: File) => {
        setBusy(true)
        try {
            const found = await inspectBclFile(file)
            setInspection(found)
            if (!found.recognised) {
                toast.error("This file is not one of the six BCL reports.")
                return
            }
            if (found.report_key) setReportKey(found.report_key)
            if (found.schema_validation.valid) {
                toast.success(`Identified as ${found.label}, valid against the BCL schema.`)
            } else {
                toast.warning(`Identified as ${found.label}, but it does not satisfy the BCL schema.`)
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const field = (label: string, key: keyof HeaderState, type = "text", hint?: string) => (
        <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{label}</span>
            <input type={type} value={header[key]}
                onChange={(event) => setHeader({ ...header, [key]: event.target.value })}
                className="rounded-md border border-slate-300 px-3 py-2 outline-none
                           focus:border-[#0A2647]" />
            {hint && <span className="text-xs text-slate-500">{hint}</span>}
        </label>
    )

    const countryOptions: [string, string][] = useMemo(() => {
        const iso = ((codes?.countries as string[]) ?? []).map((code): [string, string] => [code, code])
        const special = Object.entries(codes?.special_countries ?? {})
            .map(([code, label]): [string, string] => [code, `${code} — ${label}`])
        return [...special, ...iso]
    }, [codes])

    const currencyOptions: [string, string][] = useMemo(
        () => ((codes?.currencies as string[]) ?? []).map((code): [string, string] => [code, code]), [codes])

    const sectorOptions: [string, string][] = useMemo(
        () => Object.entries(codes?.sectors ?? {})
            .map(([code, label]): [string, string] => [code, `${code} — ${label}`]), [codes])

    const maturityOptions: [string, string][] = useMemo(
        () => Object.entries(codes?.maturities ?? {})
            .map(([code, label]): [string, string] => [code, `${code} — ${label}`]), [codes])

    /** A dimension cell: a picker where BCL asks for a breakdown, the fixed
     *  code shown plainly where it does not. */
    const dimension = (
        line: BclChartLine, row: BreakdownRow, name: "country" | "currency" | "sector" | "maturity",
        options: [string, string][], onChange: (next: BreakdownRow) => void,
    ) => {
        if (line[name] !== BREAK) {
            return <span className="font-mono text-xs text-slate-500">{row[name] || "—"}</span>
        }
        return (
            <select value={row[name]} onChange={(event) => onChange({ ...row, [name]: event.target.value })}
                className={[
                    "w-full rounded-md border px-2 py-1 font-mono text-xs outline-none",
                    row[name] ? "border-slate-300" : "border-amber-400 bg-amber-50",
                ].join(" ")}>
                <option value="">choose…</option>
                {options.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
        )
    }

    const amountTable = (
        lines: BclChartLine[] | undefined, rows: ItemRows,
        setRows: (next: ItemRows) => void, title: string, totalItem: string, total: number,
    ) => (
        <section className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full table-fixed text-sm" style={{ minWidth: 1080 }}>
                    {/* Fixed widths: a line gaining or losing its breakdown
                        pickers must not resize the grid under the pointer. */}
                    <colgroup>
                        <col style={{ width: 96 }} />
                        <col />
                        <col style={{ width: 150 }} />
                        <col style={{ width: 120 }} />
                        <col style={{ width: 150 }} />
                        <col style={{ width: 150 }} />
                        <col style={{ width: 170 }} />
                        <col style={{ width: 104 }} />
                    </colgroup>
                    <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                        <tr>
                            <th className="px-3 py-2">Line</th>
                            <th className="px-3 py-2">Item</th>
                            <th className="px-3 py-2">Country</th>
                            <th className="px-3 py-2">Currency</th>
                            <th className="px-3 py-2">Sector</th>
                            <th className="px-3 py-2">Maturity</th>
                            <th className="px-3 py-2 text-right">Amount</th>
                            <th className="px-3 py-2" />
                        </tr>
                    </thead>
                    <tbody>
                        {(lines ?? []).flatMap((line) => {
                            if (line.item === totalItem) {
                                return [(
                                    <tr key={line.item} className="border-t-2 border-slate-300 bg-slate-50">
                                        <td className="px-3 py-2 font-mono text-xs">{line.item}</td>
                                        <td className="px-3 py-2 font-semibold">{line.label}</td>
                                        {([line.country, line.currency, line.sector,
                                           hasMaturity ? line.maturity : "n/a"]).map((code, position) => (
                                            <td key={position}
                                                className="px-3 py-2 font-mono text-xs text-slate-500">
                                                {code}
                                            </td>
                                        ))}
                                        <td className="px-3 py-2 text-right font-semibold">
                                            {total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                            <span className="ml-2 text-xs font-normal text-slate-500">
                                                computed
                                            </span>
                                        </td>
                                        <td />
                                    </tr>
                                )]
                            }

                            const captured = rows[line.item] ?? []
                            const needsBreakdown =
                                [line.country, line.currency, line.sector, line.maturity].includes(BREAK)

                            const update = (index: number, next: BreakdownRow) => {
                                const copy = [...captured]
                                copy[index] = next
                                setRows({ ...rows, [line.item]: copy })
                            }
                            const add = () => setRows({ ...rows, [line.item]: [...captured, rowFor(line)] })
                            const drop = (index: number) =>
                                setRows({ ...rows, [line.item]: captured.filter((_, i) => i !== index) })

                            if (captured.length === 0) {
                                return [(
                                    <tr key={line.item} className="border-t border-slate-100">
                                        <td className="px-3 py-2 font-mono text-xs">{line.item}</td>
                                        <td className="px-3 py-2">
                                            <span className="block truncate" title={line.label}>
                                                {line.label}
                                            </span>
                                        </td>
                                        {([line.country, line.currency, line.sector,
                                           hasMaturity ? line.maturity : "n/a"]).map((code, position) => (
                                            <td key={position} className="px-3 py-2 font-mono text-xs">
                                                {code === BREAK
                                                    ? <span className="text-amber-700">breakdown</span>
                                                    : <span className="text-slate-400">{code}</span>}
                                            </td>
                                        ))}
                                        <td className="px-3 py-2 text-right text-xs text-slate-400">
                                            Not reported
                                        </td>
                                        <td className="px-3 py-2 text-right">
                                            <button type="button" onClick={add}
                                                className="rounded-md border border-slate-300 px-2 py-1 text-xs
                                                           transition hover:border-[#0A2647]">
                                                Report
                                            </button>
                                        </td>
                                    </tr>
                                )]
                            }

                            return captured.map((row, index) => (
                                <tr key={`${line.item}-${index}`} className="border-t border-slate-100">
                                    <td className="px-3 py-2 font-mono text-xs">
                                        {index === 0 ? line.item : ""}
                                    </td>
                                    <td className="px-3 py-2">
                                        {index === 0 && (
                                            <span className="block truncate" title={line.label}>
                                                {line.label}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-3 py-2">
                                        {dimension(line, row, "country", countryOptions,
                                            (next) => update(index, next))}
                                    </td>
                                    <td className="px-3 py-2">
                                        {dimension(line, row, "currency", currencyOptions,
                                            (next) => update(index, next))}
                                    </td>
                                    <td className="px-3 py-2">
                                        {dimension(line, row, "sector", sectorOptions,
                                            (next) => update(index, next))}
                                    </td>
                                    <td className="px-3 py-2">
                                        {hasMaturity
                                            ? dimension(line, row, "maturity", maturityOptions,
                                                (next) => update(index, next))
                                            : <span className="text-xs text-slate-400">n/a</span>}
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                        <input type="number" step="0.01" value={row.amount}
                                            onChange={(event) =>
                                                update(index, { ...row, amount: event.target.value })}
                                            className="w-full rounded-md border border-slate-300 px-2 py-1
                                                       text-right outline-none focus:border-[#0A2647]" />
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right">
                                        {needsBreakdown && index === captured.length - 1 && (
                                            <button type="button" onClick={add}
                                                className="mr-1 rounded-md border border-slate-300 px-2 py-1
                                                           text-xs transition hover:border-[#0A2647]">
                                                + row
                                            </button>
                                        )}
                                        <button type="button" onClick={() => drop(index)}
                                            aria-label="Remove this row"
                                            className="px-1 text-xs text-slate-400 hover:text-red-700">×</button>
                                    </td>
                                </tr>
                            ))
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    )

    const difference = Math.round((assetsTotal - liabilitiesTotal) * 100) / 100
    const incomplete = [...Object.values(assets), ...Object.values(liabilities)]
        .flat()
        .filter((row) => !row.country || !row.currency || !row.sector
            || (hasMaturity && !row.maturity)).length

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="BCL statistical reports — Ingestion"
                subtitle="Pick the report, then capture its header and its chart of accounts. What is
                          entered here is what the generation step builds from." />

            <IngestionPanel regime="BCL" busy={busy} actions={[
                ...(report ? [
                    { label: "Download template", href: bclReferenceUrl(report.key, "report"),
                      hint: "the official chart of accounts this form reproduces" },
                ] : []),
                { label: "Open an existing XML filing", accept: ".xml", onFile: openFiling,
                  primary: true,
                  hint: "identified and validated against its own BCL schema on the spot" },
                { label: "Saved drafts", onClick: () => drafts.setPanelOpen(true),
                  hint: "re-open a capture saved earlier" },
            ]}
                formOpen={formOpen} onToggleForm={() => setFormOpen(!formOpen)}>
                <p className="text-xs text-slate-500">
                    BCL reports are filed as XML directly to eDesk — unlike AIFMD there is no fillable
                    workbook to round-trip, which is why the entry points here are the official reference
                    documents and an existing filing.
                </p>

                {inspection && inspection.recognised && (
                    <div className="flex flex-col gap-2 border-t border-slate-100 pt-3">
                        <p className="text-sm text-slate-700">
                            Identified as <strong>{inspection.label}</strong>
                            {inspection.filename && (
                                <span className="ml-2 font-mono text-xs text-slate-500">
                                    {inspection.filename}
                                </span>
                            )}
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

            <div className="flex flex-wrap gap-2">
                {reports.map((candidate) => (
                    <button key={candidate.key} type="button" onClick={() => setReportKey(candidate.key)}
                        className={[
                            "rounded-md border px-3 py-2 text-sm font-medium transition",
                            candidate.key === reportKey
                                ? "border-[#0A2647] bg-[#0A2647] text-white"
                                : "border-slate-300 bg-white text-slate-700 hover:border-[#0A2647]",
                        ].join(" ")}>
                        {candidate.label}
                    </button>
                ))}
            </div>

            {report && (
                <article className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5">
                    <div>
                        <h2 className="font-semibold text-slate-900">{report.label}</h2>
                        <p className="text-sm text-slate-600">{report.description}</p>
                        <p className="mt-1 text-xs text-slate-500">
                            {report.frequency} · root <code>{report.root}</code> · layout {report.layout}
                        </p>
                    </div>
                </article>
            )}

            {formOpen && isLedger && report && (
                <div id={FORM_ANCHOR} className="flex flex-col gap-6">
                    <section className="grid gap-4 rounded-lg border border-slate-200 bg-white p-5
                                        md:grid-cols-3">
                        {field("End of period date", "end_month_date", "date", "header/endMonthDate")}
                        {field("Last NAV calculation", "closing_date", "date", "header/closingDate")}
                        {field("Reporting currency", "reporting_currency", "text", "ISO 4217")}
                        {field("Reporter type", "reporter_type", "text", "2-digit BCL code")}
                        {field("Reporter code", "reporter_code")}
                        {field("Declarant type", "declarant_type", "text", "2-digit BCL code")}
                        {field("Declarant code", "declarant_code")}
                    </section>

                    {report.assets?.every((line) => ![line.country, line.currency, line.sector,
                                                        line.maturity].includes(BREAK)) && (
                        <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm
                                      text-slate-600">
                            {report.label} asks for no breakdown: every line is reported against the
                            regulator&apos;s &quot;no breakdown&quot; codes (XX, XXX, 90000, I999-999),
                            which is why those columns are fixed. Only the amount is yours to report.
                        </p>
                    )}

                    <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                        A chart line is a template rather than a row. Where BCL asks for a breakdown the cell
                        is a picker: report the item once per country, currency, sector or maturity the fund
                        is exposed to, each with its own amount. Where BCL fixes the code it is shown plainly
                        and cannot be changed. An item left unreported is not the same as one reported at
                        zero, so an untouched line is simply absent from the filing.
                    </p>

                    {amountTable(report.assets, assets, setAssets, "1. Assets", "1-000000", assetsTotal)}
                    {amountTable(report.liabilities, liabilities, setLiabilities, "2. Liabilities",
                        "2-000000", liabilitiesTotal)}

                    {incomplete > 0 && (
                        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm
                                      text-amber-900">
                            {incomplete} reported row(s) are missing a breakdown code. BCL rejects a line
                            whose country, currency, sector or maturity is not a valid code.
                        </p>
                    )}

                    {(assetsTotal > 0 || liabilitiesTotal > 0) && report.key !== "s16" && (
                        <p className={[
                            "rounded-md border px-3 py-2 text-sm",
                            Math.abs(difference) < 0.005
                                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                                : "border-amber-300 bg-amber-50 text-amber-900",
                        ].join(" ")}>
                            {Math.abs(difference) < 0.005
                                ? `Balance sheet balanced — assets and liabilities both total ${assetsTotal.toLocaleString()}.`
                                : `Balance sheet not balanced — difference ${difference.toLocaleString()}. BCL requires line 1-000000 to equal line 2-000000.`}
                        </p>
                    )}
                </div>
            )}

            {formOpen && (
            <div id={FORM_ANCHOR} className="flex flex-col gap-6">
            {reportKey === "s44" && <S44Form draft={s44} onChange={setS44} codes={codes} />}

            {reportKey === "tptobs" && (
                <TptobsForm draft={tptobs} onChange={setTptobs} codes={codes} report={report} />
            )}

            {reportKey === "s220" && <S220Form draft={s220} onChange={setS220} codes={codes} />}
            </div>
            )}

            {formOpen && (
                <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
                    <input value={drafts.name} onChange={(event) => drafts.setName(event.target.value)}
                        placeholder="Name this draft"
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none
                                   focus:border-[#0A2647]" />
                    <button type="button"
                        onClick={() => drafts.save({ report_key: reportKey, header, assets,
                                                     liabilities, s44, tptobs, s220 })}
                        className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                                   text-[#0A2647] transition hover:bg-slate-100">
                        Save this capture as a draft
                    </button>
                </div>
            )}

            {drafts.panelOpen && (
                <DraftsPanel moduleKey={MODULE_KEY} moduleLabel="BCL statistical reports"
                    onOpen={drafts.open} onClose={() => drafts.setPanelOpen(false)} />
            )}

            {!isLedger && !["s44", "tptobs", "s220"].includes(reportKey) && report && (
                <p className="rounded-md border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {report.label} has no capture screen yet.
                </p>
            )}
        </section>
    )
}

export default BclIngestion
