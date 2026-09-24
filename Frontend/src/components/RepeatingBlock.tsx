import { useState } from "react"

import type { FormColumn } from "src/types/reportingType"

/**
 * A repeating block of a filing — share classes, principal markets, prime
 * brokers, the ten largest exposures.
 *
 * A flat grid works while a block has two or three fields and becomes
 * unusable past that: eight narrow columns scrolling sideways, no room for a
 * label, and no way to tell which record you are in. So a block with more
 * than three fields is edited one record at a time — the records listed down
 * the side, the selected one opened as a proper labelled form — while the
 * short ones stay an inline grid, which is genuinely quicker for them.
 */
export type Row = Record<string, unknown>

const INPUT = "w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none " +
    "focus:border-[#0A2647]"

const inputType = (type: string) =>
    type === "date" ? "date" : type === "number" || type === "integer" ? "number" : "text"

/** The one line that identifies a record in the list: its first filled
 *  text-ish value, falling back to its position. */
const summarise = (row: Row, columns: FormColumn[], index: number): string => {
    for (const column of columns) {
        const value = row[column.key]
        if (value !== undefined && value !== null && String(value).trim() !== "") {
            return String(value)
        }
    }
    return `Record ${index + 1}`
}

const Cell: React.FC<{
    column: FormColumn
    value: unknown
    onChange: (next: string) => void
    countries: [string, string][]
}> = ({ column, value, onChange, countries }) => {
    if (column.type === "country") {
        return (
            <select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}
                className={INPUT}>
                <option value="">Select</option>
                {countries.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
        )
    }
    return (
        <input type={inputType(column.type)} value={String(value ?? "")}
            onChange={(event) => onChange(event.target.value)} className={INPUT} />
    )
}

const RepeatingBlock: React.FC<{
    title: string
    hint?: string
    columns: FormColumn[]
    rows: Row[]
    onChange: (rows: Row[]) => void
    countries?: [string, string][]
}> = ({ title, hint, columns, rows, onChange, countries = [] }) => {
    const [selected, setSelected] = useState(0)
    const inline = columns.length <= 3

    const update = (index: number, key: string, value: string) =>
        onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)))

    const add = () => {
        onChange([...rows, {}])
        setSelected(rows.length)
    }

    const duplicate = (index: number) => {
        const copy = [...rows]
        copy.splice(index + 1, 0, { ...rows[index] })
        onChange(copy)
        setSelected(index + 1)
    }

    const remove = (index: number) => {
        onChange(rows.filter((_, i) => i !== index))
        setSelected((current) => Math.max(0, current > index ? current - 1 : current))
    }

    const header = (
        <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
                <h3 className="text-sm font-semibold text-slate-900">
                    {title}
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal
                                     text-slate-600">
                        {rows.length}
                    </span>
                </h3>
                {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
            </div>
            <button type="button" onClick={add}
                className="rounded-md bg-[#0A2647] px-3 py-1.5 text-sm font-medium text-white
                           transition hover:bg-[#123A6B]">
                Add
            </button>
        </div>
    )

    if (rows.length === 0) {
        return (
            <div className="flex flex-col gap-3 rounded-lg border border-dashed border-slate-300
                            bg-slate-50/60 p-4">
                {header}
                <p className="text-sm text-slate-500">
                    None reported. Nothing is sent for this block until you add one.
                </p>
            </div>
        )
    }

    if (inline) {
        return (
            <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
                {header}
                <div className="flex flex-col gap-2">
                    {rows.map((row, index) => (
                        <div key={index} className="flex items-end gap-2">
                            <span className="w-6 shrink-0 pb-2 text-xs text-slate-400">{index + 1}</span>
                            {columns.map((column) => (
                                <label key={column.key} className="flex flex-1 flex-col gap-1">
                                    {index === 0 && (
                                        <span className="text-xs font-medium text-slate-600">
                                            {column.label}
                                        </span>
                                    )}
                                    <Cell column={column} value={row[column.key]} countries={countries}
                                        onChange={(next) => update(index, column.key, next)} />
                                </label>
                            ))}
                            <button type="button" onClick={() => remove(index)}
                                aria-label={`Remove ${summarise(row, columns, index)}`}
                                className="shrink-0 px-2 pb-2 text-sm text-slate-400 hover:text-red-700">
                                ×
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    const current = rows[Math.min(selected, rows.length - 1)]
    const index = Math.min(selected, rows.length - 1)

    return (
        <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
            {header}
            <div className="grid gap-4 md:grid-cols-[220px_1fr]">
                <ul className="flex max-h-80 flex-col gap-1 overflow-auto">
                    {rows.map((row, position) => (
                        <li key={position}>
                            <button type="button" onClick={() => setSelected(position)}
                                className={[
                                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left",
                                    "text-sm transition",
                                    position === index
                                        ? "bg-[#0A2647] text-white"
                                        : "text-slate-700 hover:bg-slate-100",
                                ].join(" ")}>
                                <span className={position === index ? "text-white/60" : "text-slate-400"}>
                                    {position + 1}
                                </span>
                                <span className="truncate">{summarise(row, columns, position)}</span>
                            </button>
                        </li>
                    ))}
                </ul>

                <div className="flex flex-col gap-3 rounded-md border border-slate-200 bg-slate-50 p-4">
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {columns.map((column) => (
                            <label key={column.key} className="flex flex-col gap-1 text-sm">
                                <span className="font-medium text-slate-700">{column.label}</span>
                                <Cell column={column} value={current[column.key]} countries={countries}
                                    onChange={(next) => update(index, column.key, next)} />
                            </label>
                        ))}
                    </div>
                    <div className="flex gap-2 border-t border-slate-200 pt-3">
                        <button type="button" onClick={() => duplicate(index)}
                            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs
                                       text-slate-700 transition hover:border-[#0A2647]">
                            Duplicate
                        </button>
                        <button type="button" onClick={() => remove(index)}
                            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs
                                       text-slate-700 transition hover:border-red-400 hover:text-red-700">
                            Remove
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default RepeatingBlock
