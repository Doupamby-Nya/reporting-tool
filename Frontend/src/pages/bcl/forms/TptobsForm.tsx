import { useState } from "react"

import { Field, Section, Select, toOptions } from "./fields"
import type { BclCodes, BclReport } from "src/types/reportingType"

/** One security held or issued, as TPTOBS reports it. */
export type SecurityRow = Record<string, string>

export type TptobsDraft = {
    header: Record<string, string>
    securities: SecurityRow[]
}

export const emptyTptobs = (): TptobsDraft => ({
    header: {
        end_month_date: "", closing_date: "", reporter_type: "", reporter_code: "",
        declarant_type: "", declarant_code: "", reporting_currency: "EUR",
    },
    securities: [],
})

const newSecurity = (lineItem: string): SecurityRow => ({
    line_item: lineItem, code_type: "1", isin: "", other_code: "", security_name: "",
    security_currency: "", issuer_lei: "", issuer_nationalid_type: "", issuer_nationalid_code: "",
    issuer_country: "", issuer_sector: "", hold_security_type: "", quotation_type: "percent",
    nominal_amount: "", nominal_currency: "", number_of_units: "", reported_amount: "",
    date_of_issue: "", date_of_final_maturity: "", pool_factor: "", coupon_type: "",
    coupon_frequency: "", last_coupon_payment_date: "", coupon_rate: "", cssf_class_code: "",
    issue_currency: "", distributed_amount: "", split_date: "", split_ratio: "",
})

/**
 * TPTOBS Layout 3 — security by security.
 *
 * Unlike the balance sheets, TPTOBS is not captured as amounts against a
 * chart of accounts: each security is reported individually, and BCL derives
 * the line totals from them. The line totals are therefore not on this
 * screen at all — the API computes them, which is the only way they can be
 * guaranteed to match the securities behind them.
 */
const TptobsForm: React.FC<{
    draft: TptobsDraft
    onChange: (next: TptobsDraft) => void
    codes: BclCodes | null
    report: BclReport | undefined
}> = ({ draft, onChange, codes, report }) => {
    const [open, setOpen] = useState<number | null>(null)

    const rows = draft.securities
    const setHeader = (key: string, value: string) =>
        onChange({ ...draft, header: { ...draft.header, [key]: value } })
    const setRows = (next: SecurityRow[]) => onChange({ ...draft, securities: next })
    const update = (index: number, key: string, value: string) =>
        setRows(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)))

    const lineItems: [string, string][] = [
        ...(report?.assets ?? []), ...(report?.liabilities ?? []),
    ].map((line) => [line.item, `${line.item} ${line.label}`])

    const countries: [string, string][] = [
        ...Object.entries(codes?.special_countries ?? {}).map(([code, label]): [string, string] =>
            [code, `${code} ${label}`]),
        ...(((codes?.countries as string[]) ?? []).map((code): [string, string] => [code, code])),
    ]
    const currencies: [string, string][] =
        ((codes?.currencies as string[]) ?? []).map((code) => [code, code])
    const sectors: [string, string][] =
        Object.entries(codes?.sectors ?? {}).map(([code, label]) => [code, `${code} ${label}`])
    const holdTypes = toOptions(codes?.hold_security_types)
    const couponTypes = toOptions(codes?.coupon_types)
    const couponFrequencies = toOptions(codes?.coupon_frequencies)
    const codeTypes = toOptions(codes?.security_code_types)
    const quotationTypes = toOptions(codes?.quotation_types)

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

            <Section title={`Securities reported (${rows.length})`}
                hint="One row per security. BCL derives each reported line's total from the securities
                      attached to it, so the totals are computed rather than entered.">
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                            <tr>
                                <th className="px-3 py-2">Reported line</th>
                                <th className="px-3 py-2">Identification</th>
                                <th className="px-3 py-2">Name</th>
                                <th className="px-3 py-2">Issuer country</th>
                                <th className="px-3 py-2 text-right">Reported amount</th>
                                <th className="px-3 py-2" />
                            </tr>
                        </thead>
                        <tbody>
                            {rows.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-3 py-3 text-sm text-slate-500">
                                        No security reported yet.
                                    </td>
                                </tr>
                            ) : rows.map((row, index) => (
                                <tr key={index} className="border-t border-slate-100 align-top">
                                    <td className="px-3 py-2">
                                        <select value={row.line_item}
                                            onChange={(event) => update(index, "line_item", event.target.value)}
                                            className="w-56 rounded-md border border-slate-300 px-2 py-1
                                                       font-mono text-xs outline-none">
                                            {lineItems.map(([code, label]) => (
                                                <option key={code} value={code}>{label}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="px-3 py-2">
                                        <div className="flex gap-1">
                                            <select value={row.code_type}
                                                onChange={(event) =>
                                                    update(index, "code_type", event.target.value)}
                                                className="rounded-md border border-slate-300 px-1 py-1
                                                           text-xs outline-none">
                                                {codeTypes.map(([code, label]) => (
                                                    <option key={code} value={code}>{label}</option>
                                                ))}
                                            </select>
                                            <input
                                                value={row.code_type === "1" ? row.isin : row.other_code}
                                                onChange={(event) => update(
                                                    index, row.code_type === "1" ? "isin" : "other_code",
                                                    event.target.value)}
                                                placeholder={row.code_type === "1" ? "ISIN" : "code"}
                                                className="w-32 rounded-md border border-slate-300 px-2 py-1
                                                           font-mono text-xs outline-none" />
                                        </div>
                                    </td>
                                    <td className="px-3 py-2">
                                        <input value={row.security_name}
                                            onChange={(event) =>
                                                update(index, "security_name", event.target.value)}
                                            className="w-40 rounded-md border border-slate-300 px-2 py-1
                                                       text-xs outline-none" />
                                    </td>
                                    <td className="px-3 py-2">
                                        <select value={row.issuer_country}
                                            onChange={(event) =>
                                                update(index, "issuer_country", event.target.value)}
                                            className="w-28 rounded-md border border-slate-300 px-2 py-1
                                                       font-mono text-xs outline-none">
                                            <option value="">Select</option>
                                            {countries.map(([code, label]) => (
                                                <option key={code} value={code}>{label}</option>
                                            ))}
                                        </select>
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                        <input type="number" step="0.01" value={row.reported_amount}
                                            onChange={(event) =>
                                                update(index, "reported_amount", event.target.value)}
                                            className="w-32 rounded-md border border-slate-300 px-2 py-1
                                                       text-right text-xs outline-none" />
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right">
                                        <button type="button"
                                            onClick={() => setOpen(open === index ? null : index)}
                                            className="mr-1 rounded-md border border-slate-300 px-2 py-1
                                                       text-xs transition hover:border-[#0A2647]">
                                            {open === index ? "Hide" : "Details"}
                                        </button>
                                        <button type="button"
                                            onClick={() => setRows(rows.filter((_, i) => i !== index))}
                                            aria-label="Remove this security"
                                            className="px-1 text-xs text-slate-400 hover:text-red-700">×</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {open !== null && rows[open] && (
                    <div className="rounded-lg border border-[#0A2647] bg-slate-50 p-4">
                        <h3 className="mb-3 text-sm font-semibold text-slate-900">
                            Full detail of {rows[open].security_name || `security ${open + 1}`}
                        </h3>
                        <div className="grid gap-4 md:grid-cols-3">
                            <Select label="Issuer sector" value={rows[open].issuer_sector}
                                onChange={(value) => update(open, "issuer_sector", value)}
                                options={sectors} />
                            <Field label="Issuer LEI" value={rows[open].issuer_lei}
                                onChange={(value) => update(open, "issuer_lei", value)} />
                            <Field label="Issuer national ID type" value={rows[open].issuer_nationalid_type}
                                onChange={(value) => update(open, "issuer_nationalid_type", value)} />
                            <Field label="Issuer national ID code" value={rows[open].issuer_nationalid_code}
                                onChange={(value) => update(open, "issuer_nationalid_code", value)} />
                            <Select label="Security currency" value={rows[open].security_currency}
                                onChange={(value) => update(open, "security_currency", value)}
                                options={currencies} />
                            <Select label="Type of holding" value={rows[open].hold_security_type}
                                onChange={(value) => update(open, "hold_security_type", value)}
                                options={holdTypes} />
                            <Select label="Quotation" value={rows[open].quotation_type}
                                onChange={(value) => update(open, "quotation_type", value)}
                                options={quotationTypes.length ? quotationTypes
                                    : [["percent", "In percent"], ["currency", "In currency"]]} />
                            <Field label="Nominal amount" type="number" value={rows[open].nominal_amount}
                                onChange={(value) => update(open, "nominal_amount", value)} />
                            <Select label="Nominal currency" value={rows[open].nominal_currency}
                                onChange={(value) => update(open, "nominal_currency", value)}
                                options={currencies} />
                            <Field label="Number of units" type="number" value={rows[open].number_of_units}
                                onChange={(value) => update(open, "number_of_units", value)} />
                            <Field label="Date of issue" type="date" value={rows[open].date_of_issue}
                                onChange={(value) => update(open, "date_of_issue", value)} />
                            <Field label="Final maturity" type="date"
                                value={rows[open].date_of_final_maturity}
                                onChange={(value) => update(open, "date_of_final_maturity", value)} />
                            <Field label="Pool factor" type="number" value={rows[open].pool_factor}
                                onChange={(value) => update(open, "pool_factor", value)} />
                            <Select label="Coupon type" value={rows[open].coupon_type}
                                onChange={(value) => update(open, "coupon_type", value)}
                                options={couponTypes} />
                            <Select label="Coupon frequency" value={rows[open].coupon_frequency}
                                onChange={(value) => update(open, "coupon_frequency", value)}
                                options={couponFrequencies} />
                            <Field label="Last coupon payment" type="date"
                                value={rows[open].last_coupon_payment_date}
                                onChange={(value) => update(open, "last_coupon_payment_date", value)} />
                            <Field label="Coupon rate" type="number" value={rows[open].coupon_rate}
                                onChange={(value) => update(open, "coupon_rate", value)} />
                            <Field label="CSSF class code" value={rows[open].cssf_class_code}
                                onChange={(value) => update(open, "cssf_class_code", value)} />
                            <Select label="Issue currency" value={rows[open].issue_currency}
                                onChange={(value) => update(open, "issue_currency", value)}
                                options={currencies} />
                            <Field label="Distributed amount" type="number"
                                value={rows[open].distributed_amount}
                                onChange={(value) => update(open, "distributed_amount", value)} />
                            <Field label="Split date" type="date" value={rows[open].split_date}
                                onChange={(value) => update(open, "split_date", value)} />
                            <Field label="Split ratio" type="number" value={rows[open].split_ratio}
                                onChange={(value) => update(open, "split_ratio", value)} />
                        </div>
                    </div>
                )}

                <button type="button"
                    onClick={() => {
                        setRows([...rows, newSecurity(lineItems[0]?.[0] ?? "")])
                        setOpen(rows.length)
                    }}
                    disabled={lineItems.length === 0}
                    className="w-fit rounded-md border border-[#0A2647] px-3 py-1.5 text-sm font-medium
                               text-[#0A2647] transition hover:bg-slate-100 disabled:opacity-40">
                    Add a security
                </button>
            </Section>
        </>
    )
}

export default TptobsForm
