import { useState } from "react"

import { Field, Money, Section, Select, isBreakdownLabel, toOptions } from "./fields"
import type { BclCodes } from "src/types/reportingType"

export type ShareClassRow = Record<string, string>
export type ContactRow = { name: string; phone: string; email: string }

export type S220Draft = {
    scalars: Record<string, string>
    sender_employees: ContactRow[]
    share_classes: ShareClassRow[]
}

/** Section 6 — investment income and expenses, items 6010 to 6100, in the
 *  order and wording BCL prints them. */
const INCOME_FIELDS: [string, string, string][] = [
    ["dividends_on_shares", "Dividends on shares", "6010"],
    ["dividends_on_shares_lu", "…of which from Luxembourg", "6011"],
    ["dividends_on_uci_units", "Dividends on UCI units/shares", "6020"],
    ["dividends_on_uci_units_lu", "…of which from Luxembourg", "6021"],
    ["interest_bonds", "Interest on bonds and debt securities", "6030"],
    ["interest_bonds_lu", "…of which from Luxembourg", "6031"],
    ["interest_loans_banks", "Interest on loans, banks and bearing accounts", "6040"],
    ["bank_interest", "Bank interest", "6050"],
    ["bank_interest_lu", "…of which from Luxembourg", "6051"],
    ["other_interest", "Other interest", "6060"],
    ["other_interest_lu", "…of which from Luxembourg", "6061"],
    ["other_income", "Other income", "6070"],
    ["rental_income", "…rental income", "6071"],
    ["commission_income", "…commission income", "6072"],
    ["other_income_other", "…other", "6073"],
]

const EXPENSE_FIELDS: [string, string, string][] = [
    ["charges", "Charges", "6080"],
    ["advisory_management_fees", "…advisory and management fees", "6081"],
    ["depositary_bank_fees", "…depositary bank fees", "6082"],
    ["administration_fees", "…administration fees", "6083"],
    ["audit_inspection_fees", "…audit and inspection fees", "6084"],
    ["distribution_fees", "…distribution fees", "6085"],
    ["other_administrative_expenses", "…other administrative expenses", "6086"],
    ["subscription_tax", "…subscription tax", "6087"],
    ["other_taxes", "…other taxes", "6088"],
    ["performance_fees", "Performance fees", "6090"],
    ["other_expenses", "Other expenses", "6095"],
    ["interest_paid", "…interest paid", "6096"],
    ["personnel_expenses", "…personnel expenses", "6097"],
    ["rental_expenses", "…rental expenses", "6098"],
    ["amortisation", "…amortisation", "6099"],
    ["other_expenses_other", "…other", "6100"],
]

const RESULT_FIELDS: [string, string, string][] = [
    ["net_realised", "Net realised result", "6110"],
    ["net_unrealised", "Net unrealised result", "6120"],
]

/** The columns kept in the table itself — enough to tell one class from
 *  another. Every other item is in the detail panel, because BCL asks for
 *  22 of them and a 22-column table cannot be filled in. */
const SHARE_CLASS_SUMMARY: [string, string][] = [
    ["cssf_code", "CSSF code (4010)"],
    ["name", "Name"],
    ["base_currency", "Currency"],
    ["isin", "ISIN"],
    ["units_outstanding", "Units outstanding"],
]

/** Every item of a unit/share class, with the BCL item number. `kind`
 *  decides the input: a date, a picked code, a flag or an amount. */
const SHARE_CLASS_FIELDS: { key: string; label: string; item: string;
                            kind: "text" | "date" | "number" | "flag" | "investor" | "closing" }[] = [
    { key: "cssf_code", label: "CSSF code", item: "4010", kind: "text" },
    { key: "name", label: "Name", item: "4020", kind: "text" },
    { key: "base_currency", label: "Base currency", item: "4030", kind: "text" },
    { key: "isin", label: "ISIN", item: "4040", kind: "text" },
    { key: "launch_date", label: "Launch date", item: "4050", kind: "date" },
    { key: "closing_date", label: "Closing date", item: "4060", kind: "date" },
    { key: "reason_for_closing", label: "Reason for closing", item: "4070", kind: "closing" },
    { key: "spec_instr_fx", label: "Specific instrument: FX", item: "4080", kind: "flag" },
    { key: "spec_instr_interest_rate", label: "Specific instrument: interest rate", item: "4090",
      kind: "flag" },
    { key: "spec_instr_other", label: "Specific instrument: other", item: "4100", kind: "flag" },
    { key: "investor_base", label: "Investor base", item: "4110", kind: "investor" },
    { key: "units_outstanding", label: "Units outstanding", item: "5010", kind: "number" },
    { key: "nav_per_unit_fund_currency", label: "NAV per unit, fund currency", item: "5020",
      kind: "number" },
    { key: "nav_per_unit_shareclass_currency", label: "NAV per unit, class currency", item: "5030",
      kind: "number" },
    { key: "net_return", label: "Net return per unit", item: "5040", kind: "number" },
    { key: "units_issued", label: "Units issued", item: "5050", kind: "number" },
    { key: "units_redeemed", label: "Units redeemed", item: "5060", kind: "number" },
    { key: "distributions", label: "Distributions", item: "5070", kind: "number" },
    { key: "distributions_per_unit_fund_currency", label: "Distribution per unit, fund currency",
      item: "5080", kind: "number" },
    { key: "distributions_per_unit_shareclass_currency", label: "Distribution per unit, class currency",
      item: "5090", kind: "number" },
    { key: "income_fund_currency", label: "Income, fund currency", item: "5100", kind: "number" },
    { key: "expenses_fund_currency", label: "Expenses, fund currency", item: "5110", kind: "number" },
]

export const emptyS220 = (): S220Draft => ({
    scalars: {
        reference_month: "", reporting_status: "final report", sender_cssf_code: "",
        sender_type: "", sender_code: "",
        uci_cssf_code: "", declarant_type: "42", declarant_code: "", uci_name: "",
        uci_base_currency: "EUR", uci_lei: "", valuation_date: "", nav_freq: "",
        launch_date: "", closing_date: "", reason_for_closing: "", nav_redemption_freq: "",
        open_closed_end: "", uci_comment: "",
        nav_preceding_ref_month: "", nav_ref_month: "", units_issued: "", units_redeemed: "",
        total_distributions: "",
        ...Object.fromEntries([...INCOME_FIELDS, ...EXPENSE_FIELDS, ...RESULT_FIELDS]
            .map(([key]) => [key, ""])),
    },
    sender_employees: [],
    share_classes: [],
})

const newShareClass = (): ShareClassRow =>
    Object.fromEntries(SHARE_CLASS_FIELDS.map(({ key, kind }) => [key, kind === "flag" ? "false" : ""]))

/**
 * S 2.20 Layout L — quarterly financial information, items 1010 to 6100.
 *
 * The largest of the six reports, and the only one that is not a balance
 * sheet: it describes the fund itself, its share classes and its investment
 * income and expenses. The item numbers are shown next to every field
 * because that is how a preparer cross-checks the screen against the BCL
 * instructions.
 */
const S220Form: React.FC<{
    draft: S220Draft
    onChange: (next: S220Draft) => void
    codes: BclCodes | null
}> = ({ draft, onChange, codes }) => {
    const [openClass, setOpenClass] = useState<number | null>(null)
    const s220 = (codes?.s220 ?? {}) as Record<string, unknown>
    const pairs = (name: string): [string, string][] => toOptions(s220[name])
    const statuses: [string, string][] = pairs("reporting_statuses")

    const set = (key: string, value: string) =>
        onChange({ ...draft, scalars: { ...draft.scalars, [key]: value } })
    /** A schedule renders as a run, so each line knows whether the next one
     *  is its own breakdown and can be shaded as the total it is. */
    const schedule = (rows: [string, string, string][]) => (
        <div className="flex flex-col">
            {rows.map(([key, label, item], index) => {
                const child = isBreakdownLabel(label)
                const consolidating = !child && isBreakdownLabel(rows[index + 1]?.[1] ?? label)
                return (
                    <Money key={key} label={label} item={item} value={draft.scalars[key] ?? ""}
                        consolidating={consolidating} child={child}
                        onChange={(value) => set(key, value)} />
                )
            })}
        </div>
    )
    const money = (key: string, label: string, item: string) => (
        <Money key={key} label={label} item={item} value={draft.scalars[key] ?? ""}
            onChange={(value) => set(key, value)} />
    )

    const contacts = draft.sender_employees
    const classes = draft.share_classes
    const setClass = (index: number, key: string, value: string) =>
        onChange({
            ...draft,
            share_classes: classes.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
        })

    return (
        <>
            <Section title="1. Sender" hint="Items 1010 to 1050. At least one contact is mandatory.">
                <div className="grid gap-4 md:grid-cols-3">
                    <Field label="Reference month" item="1010" value={draft.scalars.reference_month}
                        onChange={(value) => set("reference_month", value)} hint="YYYYMM" />
                    <Select label="Reporting status" item="1020" value={draft.scalars.reporting_status}
                        onChange={(value) => set("reporting_status", value)} options={statuses} />
                    <Field label="Sender CSSF code" value={draft.scalars.sender_cssf_code}
                        onChange={(value) => set("sender_cssf_code", value)} />
                    <Field label="Sender type" item="1031" value={draft.scalars.sender_type}
                        onChange={(value) => set("sender_type", value)} />
                    <Field label="Sender code" item="1032" value={draft.scalars.sender_code}
                        onChange={(value) => set("sender_code", value)} />
                </div>

                <div className="flex flex-col gap-2">
                    {contacts.map((contact, index) => (
                        <div key={index} className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
                            {(["name", "phone", "email"] as const).map((key) => (
                                <input key={key} value={contact[key]} placeholder={key}
                                    onChange={(event) => onChange({
                                        ...draft,
                                        sender_employees: contacts.map((row, i) =>
                                            i === index ? { ...row, [key]: event.target.value } : row),
                                    })}
                                    className="rounded-md border border-slate-300 px-3 py-2 text-sm
                                               outline-none focus:border-[#0A2647]" />
                            ))}
                            <button type="button" aria-label="Remove this contact"
                                onClick={() => onChange({
                                    ...draft,
                                    sender_employees: contacts.filter((_, i) => i !== index),
                                })}
                                className="px-2 text-xs text-slate-400 hover:text-red-700">×</button>
                        </div>
                    ))}
                    <button type="button"
                        onClick={() => onChange({
                            ...draft,
                            sender_employees: [...contacts, { name: "", phone: "", email: "" }],
                        })}
                        className={[
                            "w-fit rounded-md border px-3 py-1.5 text-sm font-medium transition",
                            contacts.length === 0
                                ? "border-amber-400 bg-amber-50 text-amber-900"
                                : "border-[#0A2647] text-[#0A2647] hover:bg-slate-100",
                        ].join(" ")}>
                        {contacts.length === 0 ? "Add the mandatory contact" : "Add a contact"}
                    </button>
                </div>
            </Section>

            <Section title="2. The fund" hint="Items 2010 to 2110.">
                <div className="grid gap-4 md:grid-cols-3">
                    <Field label="UCI CSSF code" item="2010" value={draft.scalars.uci_cssf_code}
                        onChange={(value) => set("uci_cssf_code", value)} />
                    <Field label="Declarant type" item="2011" value={draft.scalars.declarant_type}
                        onChange={(value) => set("declarant_type", value)} hint="always 42 for a NAF" />
                    <Field label="Declarant code" item="2012" value={draft.scalars.declarant_code}
                        onChange={(value) => set("declarant_code", value)} hint="14 digits" />
                    <Field label="UCI name" item="2020" value={draft.scalars.uci_name}
                        onChange={(value) => set("uci_name", value)} />
                    <Field label="Base currency" item="2030" value={draft.scalars.uci_base_currency}
                        onChange={(value) => set("uci_base_currency", value)} />
                    <Field label="LEI" item="2040" value={draft.scalars.uci_lei}
                        onChange={(value) => set("uci_lei", value)} />
                    <Field label="Valuation date" item="2050" type="date" value={draft.scalars.valuation_date}
                        onChange={(value) => set("valuation_date", value)} />
                    <Select label="NAV frequency" item="2060" value={draft.scalars.nav_freq}
                        onChange={(value) => set("nav_freq", value)} options={pairs("nav_frequencies")} />
                    <Field label="Launch date" item="2070" type="date" value={draft.scalars.launch_date}
                        onChange={(value) => set("launch_date", value)} />
                    <Field label="Closing date" item="2080" type="date" value={draft.scalars.closing_date}
                        onChange={(value) => set("closing_date", value)} />
                    <Select label="Reason for closing" item="2090" value={draft.scalars.reason_for_closing}
                        onChange={(value) => set("reason_for_closing", value)}
                        options={pairs("reason_for_closing_uci")} />
                    <Select label="Redemption frequency" item="2100"
                        value={draft.scalars.nav_redemption_freq}
                        onChange={(value) => set("nav_redemption_freq", value)}
                        options={pairs("nav_redemption_frequencies")} />
                    <Select label="Open / closed end" item="2110" value={draft.scalars.open_closed_end}
                        onChange={(value) => set("open_closed_end", value)}
                        options={pairs("open_closed_end")} />
                    <Field label="Comment" value={draft.scalars.uci_comment}
                        onChange={(value) => set("uci_comment", value)} />
                </div>
            </Section>

            <Section title="3. Financial information" hint="Items 3010 to 3050.">
                <div className="flex flex-col">
                    {money("nav_preceding_ref_month", "NAV at the preceding reference month", "3010")}
                    {money("nav_ref_month", "NAV at the reference month", "3020")}
                    {money("units_issued", "Units or shares issued", "3030")}
                    {money("units_redeemed", "Units or shares redeemed", "3040")}
                    {money("total_distributions", "Total distributions", "3050")}
                </div>
            </Section>

            <Section title={`4. Share classes (${classes.length})`}
                hint="Items 4010 to 5110. The table identifies each class; open its detail to fill in
                      every item BCL asks for.">
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                            <tr>
                                {SHARE_CLASS_SUMMARY.map(([key, label]) => (
                                    <th key={key} className="whitespace-nowrap px-2 py-2">{label}</th>
                                ))}
                                <th className="px-2 py-2" />
                            </tr>
                        </thead>
                        <tbody>
                            {classes.length === 0 ? (
                                <tr>
                                    <td colSpan={SHARE_CLASS_SUMMARY.length + 1}
                                        className="px-3 py-3 text-sm text-slate-500">
                                        No share class reported yet.
                                    </td>
                                </tr>
                            ) : classes.map((row, index) => (
                                <tr key={index} className="border-t border-slate-100">
                                    {SHARE_CLASS_SUMMARY.map(([key]) => (
                                        <td key={key} className="px-2 py-1">
                                            <input value={row[key] ?? ""}
                                                onChange={(event) => setClass(index, key, event.target.value)}
                                                className="w-32 rounded-md border border-slate-300 px-2 py-1
                                                           text-xs outline-none focus:border-[#0A2647]" />
                                        </td>
                                    ))}
                                    <td className="whitespace-nowrap px-2 py-1 text-right">
                                        <button type="button"
                                            onClick={() => setOpenClass(openClass === index ? null : index)}
                                            className="mr-1 rounded-md border border-slate-300 px-2 py-1
                                                       text-xs transition hover:border-[#0A2647]">
                                            {openClass === index ? "Hide" : "Details"}
                                        </button>
                                        <button type="button" aria-label="Remove this share class"
                                            onClick={() => {
                                                onChange({ ...draft,
                                                    share_classes: classes.filter((_, i) => i !== index) })
                                                setOpenClass(null)
                                            }}
                                            className="px-1 text-xs text-slate-400 hover:text-red-700">×</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {openClass !== null && classes[openClass] && (
                    <div className="rounded-lg border border-[#0A2647] bg-slate-50 p-4">
                        <h3 className="mb-3 text-sm font-semibold text-slate-900">
                            Every item of {classes[openClass].name || `share class ${openClass + 1}`}
                        </h3>
                        <div className="grid gap-4 md:grid-cols-3">
                            {SHARE_CLASS_FIELDS.map(({ key, label, item, kind }) => {
                                const value = classes[openClass][key] ?? ""
                                const change = (next: string) => setClass(openClass, key, next)
                                if (kind === "flag") {
                                    return (
                                        <label key={key}
                                            className="flex items-center gap-2 self-end py-2 text-sm">
                                            <input type="checkbox" checked={value === "true"}
                                                onChange={(event) =>
                                                    change(event.target.checked ? "true" : "false")} />
                                            <span className="text-slate-700">
                                                {label}
                                                <span className="ml-2 font-mono text-xs text-slate-400">
                                                    {item}
                                                </span>
                                            </span>
                                        </label>
                                    )
                                }
                                if (kind === "investor" || kind === "closing") {
                                    return (
                                        <Select key={key} label={label} item={item} value={value}
                                            onChange={change}
                                            options={pairs(kind === "investor"
                                                ? "investor_base" : "reason_for_closing_share_class")} />
                                    )
                                }
                                return (
                                    <Field key={key} label={label} item={item} value={value}
                                        onChange={change}
                                        type={kind === "date" ? "date" : kind === "number" ? "number" : "text"} />
                                )
                            })}
                        </div>
                    </div>
                )}

                <button type="button"
                    onClick={() => {
                        onChange({ ...draft, share_classes: [...classes, newShareClass()] })
                        setOpenClass(classes.length)
                    }}
                    className="w-fit rounded-md border border-[#0A2647] px-3 py-1.5 text-sm font-medium
                               text-[#0A2647] transition hover:bg-slate-100">
                    Add a share class
                </button>
            </Section>

            <Section title="6. Investment income" hint="Items 6010 to 6073.">
                {schedule(INCOME_FIELDS)}
            </Section>

            <Section title="6. Expenses" hint="Items 6080 to 6100.">
                {schedule(EXPENSE_FIELDS)}
            </Section>

            <Section title="6. Result">
                {schedule(RESULT_FIELDS)}
            </Section>
        </>
    )
}

export default S220Form
