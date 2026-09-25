import { useMemo, useState } from "react"
import { FiChevronDown, FiChevronUp, FiSearch } from "react-icons/fi"

import { moduleMeta } from "@config/activity"
import type { ActivitySummary, ActivityUserRow } from "src/types/reportingType"
import { sinceWhen } from "./dates"

type SortKey = "name" | "count" | "active_days" | "generated" | "reviewed" | "last_active"

const COLUMNS: [SortKey, string, string][] = [
    ["count", "Activity", "text-left"],
    ["active_days", "Active days", "text-right"],
    ["generated", "Filings", "text-right"],
    ["reviewed", "Reviews", "text-right"],
    ["last_active", "Last active", "text-right"],
]

const initials = (name: string) => name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()

/**
 * An organisation's people, busiest first: how much each did, on how many
 * days, how many filings they produced and reviewed, in which reporting
 * mostly, and when they were last seen. Choosing someone opens their own
 * activity in the same dashboard.
 */
export const PeopleTable: React.FC<{
    rows: ActivityUserRow[]
    onPick: (userId: number) => void
}> = ({ rows, onPick }) => {
    const [query, setQuery] = useState("")
    const [sort, setSort] = useState<{ key: SortKey; down: boolean }>({ key: "count", down: true })

    const shown = useMemo(() => {
        const needle = query.trim().toLowerCase()
        const kept = rows.filter((row) => !needle
            || row.name.toLowerCase().includes(needle) || row.email.toLowerCase().includes(needle))
        return [...kept].sort((a, b) => {
            const [x, y] = [a[sort.key], b[sort.key]]
            const order = typeof x === "number" ? x - (y as number) : String(x).localeCompare(String(y))
            return sort.down ? -order : order
        })
    }, [rows, query, sort])

    const widest = Math.max(1, ...rows.map((row) => row.count))
    const header = (key: SortKey, label: string, align: string) => (
        <th key={key} scope="col" className={`px-3 py-2 font-medium ${align}`}>
            <button type="button" onClick={() => setSort({ key, down: sort.key === key ? !sort.down : true })}
                className={`inline-flex items-center gap-1 hover:text-[#0A2647] ${sort.key === key ? "text-[#0A2647]" : ""}`}>
                {label}
                {sort.key === key && (sort.down ? <FiChevronDown /> : <FiChevronUp />)}
            </button>
        </th>
    )

    return (
        <div className="flex flex-col gap-3">
            <label className="relative w-full max-w-xs">
                <FiSearch className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                <input value={query} onChange={(event) => setQuery(event.target.value)}
                    placeholder="Find a person" aria-label="Find a person"
                    className="w-full rounded-md border border-slate-300 py-1.5 pl-8 pr-3 text-sm outline-none
                               focus:border-[#0A2647] focus:ring-2 focus:ring-[#0A2647]/10" />
            </label>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full min-w-[760px] text-sm">
                    <thead className="bg-slate-50 text-xs text-slate-500">
                        <tr>
                            {header("name", "Person", "text-left")}
                            {COLUMNS.map(([key, label, align]) => header(key, label, align))}
                            <th scope="col" className="px-3 py-2 text-left font-medium">Mostly in</th>
                        </tr>
                    </thead>
                    <tbody>
                        {shown.map((row) => {
                            const main = moduleMeta(row.top_module)
                            return (
                                <tr key={row.user_id} onClick={() => onPick(row.user_id)}
                                    className="cursor-pointer border-t border-slate-100 transition hover:bg-[#0A2647]/[0.03]">
                                    <td className="px-3 py-2.5">
                                        <span className="flex items-center gap-3">
                                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full
                                                             bg-[#0A2647] text-[11px] font-bold text-white">
                                                {initials(row.name)}
                                            </span>
                                            <span className="min-w-0">
                                                <span className="block truncate font-medium text-slate-900">{row.name}</span>
                                                <span className="block truncate text-xs text-slate-500">{row.email}</span>
                                            </span>
                                        </span>
                                    </td>
                                    <td className="px-3 py-2.5">
                                        <span className="flex items-center gap-2">
                                            <span className="w-10 text-right font-semibold tabular-nums text-slate-900">
                                                {row.count.toLocaleString()}
                                            </span>
                                            <span className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-100">
                                                <span className="flex h-full">
                                                    {/* The bar is split by reporting, in their colours. */}
                                                    {row.modules.map((part) => (
                                                        <span key={part.module} className="h-full"
                                                            style={{ width: `${(part.count / widest) * 100}%`,
                                                                     backgroundColor: moduleMeta(part.module).color }} />
                                                    ))}
                                                </span>
                                            </span>
                                        </span>
                                    </td>
                                    <td className="px-3 py-2.5 text-right tabular-nums">{row.active_days}</td>
                                    <td className="px-3 py-2.5 text-right tabular-nums">{row.generated}</td>
                                    <td className="px-3 py-2.5 text-right tabular-nums">{row.reviewed}</td>
                                    <td className="px-3 py-2.5 text-right text-xs text-slate-500">{sinceWhen(row.last_active)}</td>
                                    <td className="px-3 py-2.5">
                                        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-2 py-0.5 text-xs">
                                            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: main.color }} />
                                            {main.label}
                                        </span>
                                    </td>
                                </tr>
                            )
                        })}
                        {!shown.length && (
                            <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-500">Nobody matches.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

/** For a platform administrator looking at every organisation at once. */
export const OrganisationList: React.FC<{
    rows: ActivitySummary["by_organisation"]
    onPick: (organisationId: number) => void
}> = ({ rows, onPick }) => {
    const widest = Math.max(1, ...rows.map((row) => row.count))
    return (
        <ul className="flex flex-col gap-1">
            {rows.map((row) => (
                <li key={row.organisation_id}>
                    <button type="button" onClick={() => onPick(row.organisation_id)}
                        className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md px-2
                                   py-1.5 text-left transition hover:bg-slate-50">
                        <span className="truncate text-sm font-medium text-slate-800">{row.name}</span>
                        <span className="text-xs tabular-nums text-slate-500">
                            <span className="font-semibold text-slate-800">{row.count.toLocaleString()}</span>
                            {" "}· {row.users} {row.users === 1 ? "person" : "people"}
                        </span>
                        <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                            <span className="block h-full rounded-full bg-[#0A2647]"
                                style={{ width: `${(row.count / widest) * 100}%` }} />
                        </span>
                    </button>
                </li>
            ))}
        </ul>
    )
}
