import { Field, Section } from "./fields"
import type { BclCodes } from "src/types/reportingType"

/** One marketing country and the share of units sold into it. */
export type MarketingRow = { country: string; amount: string }

export type S44Draft = {
    header: Record<string, string>
    marketing_countries: MarketingRow[]
}

export const emptyS44 = (): S44Draft => ({
    header: {
        end_month_date: "", closing_date: "", reporter_type: "", reporter_code: "",
        declarant_type: "", declarant_code: "", reporting_currency: "EUR",
    },
    marketing_countries: [],
})

/**
 * S 4.4 Layout 0 — where the fund's units are marketed.
 *
 * One line per country, each carrying the share of units sold into it. The
 * shares are percentages and BCL requires them to total exactly 100, so the
 * running total is shown against that rule rather than left to be found out
 * at generation.
 */
const S44Form: React.FC<{
    draft: S44Draft
    onChange: (next: S44Draft) => void
    codes: BclCodes | null
}> = ({ draft, onChange, codes }) => {
    const rows = draft.marketing_countries
    const total = rows.reduce((sum, row) => sum + (Number.parseFloat(row.amount) || 0), 0)
    const balanced = Math.abs(total - 100) < 0.005

    const setHeader = (key: string, value: string) =>
        onChange({ ...draft, header: { ...draft.header, [key]: value } })
    const setRows = (next: MarketingRow[]) => onChange({ ...draft, marketing_countries: next })
    const update = (index: number, next: MarketingRow) =>
        setRows(rows.map((row, i) => (i === index ? next : row)))

    const countries: [string, string][] = [
        ...Object.entries(codes?.special_countries ?? {}).map(([code, label]): [string, string] =>
            [code, `${code} — ${label}`]),
        ...(((codes?.countries as string[]) ?? []).map((code): [string, string] => [code, code])),
    ]

    return (
        <>
            <Section title="Header" hint="Identifies the reporting entity and the period.">
                <div className="grid gap-4 md:grid-cols-3">
                    <Field label="End of period date" item="header/endMonthDate" type="date"
                        value={draft.header.end_month_date}
                        onChange={(value) => setHeader("end_month_date", value)} />
                    <Field label="Last NAV calculation" item="header/closingDate" type="date"
                        value={draft.header.closing_date}
                        onChange={(value) => setHeader("closing_date", value)} />
                    <Field label="Reporting currency" item="ISO 4217"
                        value={draft.header.reporting_currency}
                        onChange={(value) => setHeader("reporting_currency", value)} />
                    <Field label="Reporter type" item="2-digit BCL code" value={draft.header.reporter_type}
                        onChange={(value) => setHeader("reporter_type", value)} />
                    <Field label="Reporter code" value={draft.header.reporter_code}
                        onChange={(value) => setHeader("reporter_code", value)} />
                    <Field label="Declarant type" item="2-digit BCL code" value={draft.header.declarant_type}
                        onChange={(value) => setHeader("declarant_type", value)} />
                    <Field label="Declarant code" value={draft.header.declarant_code}
                        onChange={(value) => setHeader("declarant_code", value)} />
                </div>
            </Section>

            <Section title="Marketing countries"
                hint="Item 2-004000 — the share of units marketed into each country. The shares must total 100 %.">
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                            <tr>
                                <th className="px-3 py-2">Country</th>
                                <th className="px-3 py-2 text-right">Share (%)</th>
                                <th className="px-3 py-2" />
                            </tr>
                        </thead>
                        <tbody>
                            {rows.length === 0 ? (
                                <tr>
                                    <td colSpan={3} className="px-3 py-3 text-sm text-slate-500">
                                        No marketing country reported yet.
                                    </td>
                                </tr>
                            ) : rows.map((row, index) => (
                                <tr key={index} className="border-t border-slate-100">
                                    <td className="px-3 py-2">
                                        <select value={row.country}
                                            onChange={(event) =>
                                                update(index, { ...row, country: event.target.value })}
                                            className={[
                                                "w-full rounded-md border px-2 py-1 font-mono text-xs outline-none",
                                                row.country ? "border-slate-300" : "border-amber-400 bg-amber-50",
                                            ].join(" ")}>
                                            <option value="">choose…</option>
                                            {countries.map(([code, label]) => (
                                                <option key={code} value={code}>{label}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                        <input type="number" step="0.01" value={row.amount}
                                            onChange={(event) =>
                                                update(index, { ...row, amount: event.target.value })}
                                            className="w-32 rounded-md border border-slate-300 px-2 py-1
                                                       text-right outline-none focus:border-[#0A2647]" />
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                        <button type="button"
                                            onClick={() => setRows(rows.filter((_, i) => i !== index))}
                                            aria-label="Remove this country"
                                            className="px-1 text-xs text-slate-400 hover:text-red-700">×</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    <button type="button"
                        onClick={() => setRows([...rows, { country: "", amount: "" }])}
                        className="rounded-md border border-[#0A2647] px-3 py-1.5 text-sm font-medium
                                   text-[#0A2647] transition hover:bg-slate-100">
                        Add a country
                    </button>
                    {rows.length > 0 && (
                        <span className={[
                            "rounded-md border px-3 py-1.5 text-sm",
                            balanced
                                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                                : "border-amber-300 bg-amber-50 text-amber-900",
                        ].join(" ")}>
                            Total {total.toFixed(2)} %{balanced ? "" : " — BCL requires exactly 100 %"}
                        </span>
                    )}
                </div>
            </Section>
        </>
    )
}

export default S44Form
