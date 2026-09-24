import { useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "react-toastify"

import { fetchAuditLog, fetchDocuments, transitionDocument } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import { useModule } from "@hooks/useChain"
import type { AuditEntry, TrackedDocument } from "src/types/reportingType"

/**
 * The lifecycle a filing moves through, in order. Drawing it as an order
 * rather than a set is what lets the screen say where a filing is and what
 * has to happen next, instead of only what state it is in.
 */
const LIFECYCLE = ["Generated", "Under review", "Approved", "Published"] as const

/** Which states a filing may move to next, mirroring the API's own rules so
 *  the screen only offers a transition the API would accept. */
const NEXT_STATUS: Record<string, string[]> = {
    "Generated": ["Under review"],
    "Under review": ["Approved", "Rejected"],
    "Approved": ["Published"],
    "Rejected": ["Generated"],
    "Published": [],
}

/** What the preparer actually has to do next, in their words. */
const NEXT_STEP: Record<string, string> = {
    "Generated": "Send for four-eyes review.",
    "Under review": "A second pair of eyes approves or rejects it.",
    "Approved": "Publish it, then file it with the regulator.",
    "Rejected": "Correct the submission and generate it again.",
    "Published": "Filed. Nothing further.",
}

const STATUS_STYLES: Record<string, string> = {
    "Generated": "bg-slate-100 text-slate-700 border-slate-300",
    "Under review": "bg-amber-100 text-amber-900 border-amber-300",
    "Approved": "bg-emerald-100 text-emerald-900 border-emerald-300",
    "Rejected": "bg-red-100 text-red-900 border-red-300",
    "Published": "bg-[#0A2647] text-white border-[#0A2647]",
}

const when = (timestamp: string) => timestamp.slice(0, 16).replace("T", " ")

/** How far along the lifecycle a filing is, as a row of dots. A rejected
 *  filing is off the line entirely, which is the point of showing it. */
const Progress: React.FC<{ status: string }> = ({ status }) => {
    if (status === "Rejected") {
        return <span className="text-xs font-medium text-red-700">sent back</span>
    }
    const reached = LIFECYCLE.indexOf(status as typeof LIFECYCLE[number])
    return (
        <span className="flex items-center gap-1" title={`${status}, step ${reached + 1} of 4`}>
            {LIFECYCLE.map((step, index) => (
                <span key={step} aria-hidden="true"
                    className={[
                        "h-2 w-2 rounded-full",
                        index < reached ? "bg-[#1F5FA8]"
                            : index === reached ? "bg-[#1F5FA8] ring-2 ring-[#1F5FA8]/25"
                                : "bg-slate-200",
                    ].join(" ")} />
            ))}
            <span className="ml-1 text-xs text-slate-500">{reached + 1}/4</span>
        </span>
    )
}

/**
 * The four-eyes review of one module, and the trail every transition is
 * written to.
 *
 * This is the platform's shared control layer: the same screen serves all
 * eight modules, scoped by the chain it is opened from. It answers three
 * questions a reviewer actually has — what is outstanding, who is it waiting
 * on, and what happens next — rather than listing rows and leaving the
 * reader to work it out.
 */
const ControlsAudit: React.FC = () => {
    const module = useModule()

    const [documents, setDocuments] = useState<Record<string, TrackedDocument>>({})
    const [entries, setEntries] = useState<AuditEntry[]>([])
    const [comment, setComment] = useState("")
    const [search, setSearch] = useState("")
    const [status, setStatus] = useState("")
    const [preparer, setPreparer] = useState("")
    const [expanded, setExpanded] = useState<string | null>(null)

    const refresh = useCallback(async () => {
        try {
            const [found, log] = await Promise.all([
                fetchDocuments(module.key), fetchAuditLog(200, module.key),
            ])
            setDocuments(found)
            setEntries(log)
        } catch (error) {
            toast.error((error as Error).message)
        }
    }, [module.key])

    useEffect(() => {
        setSearch("")
        setStatus("")
        setPreparer("")
        setExpanded(null)
        void refresh()
    }, [refresh])

    const move = async (documentId: string, next: string) => {
        try {
            await transitionDocument(module.key, documentId, next, comment)
            toast.success(`${documentId} is now ${next.toLowerCase()}.`)
            setComment("")
            await refresh()
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const rows = useMemo(() => Object.entries(documents), [documents])

    const preparers = useMemo(
        () => Array.from(new Set(rows.map(([, item]) => item.last_generated_by).filter(Boolean))).sort(),
        [rows])

    const filtered = useMemo(() => {
        const needle = search.trim().toLowerCase()
        return rows.filter(([documentId, item]) => {
            if (status && item.status !== status) return false
            if (preparer && item.last_generated_by !== preparer) return false
            if (!needle) return true
            return `${documentId} ${item.label}`.toLowerCase().includes(needle)
        })
    }, [rows, search, status, preparer])

    const counts = useMemo(() => {
        const tally: Record<string, number> = {}
        for (const [, item] of rows) tally[item.status] = (tally[item.status] ?? 0) + 1
        return tally
    }, [rows])

    const awaitingReview = (counts["Generated"] ?? 0) + (counts["Under review"] ?? 0)

    const filteredEntries = useMemo(() => {
        const needle = search.trim().toLowerCase()
        return entries.filter((entry) => {
            if (preparer && entry.user !== preparer) return false
            if (!needle) return true
            return `${entry.subject} ${entry.action} ${entry.detail}`.toLowerCase().includes(needle)
        })
    }, [entries, search, preparer])

    const select = "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none " +
        "focus:border-[#0A2647]"

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow={module.title} title="Controls & audit"
                subtitle="Every generated filing stays under four-eyes review until it is published, and
                          every transition is written to one trail." />

            <KpiRow items={[
                { label: "Filings", value: String(rows.length), hint: "generated for this module" },
                { label: "Awaiting review", value: String(awaitingReview),
                  hint: "outstanding work" },
                { label: "Approved", value: String(counts["Approved"] ?? 0), hint: "ready to publish" },
                { label: "Published", value: String(counts["Published"] ?? 0), hint: "filed" },
            ]} />

            {(counts["Rejected"] ?? 0) > 0 && (
                <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
                    {counts["Rejected"]} filing(s) were sent back. They return to the preparer: correct
                    the submission and generate again.
                </p>
            )}

            <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4">
                <h2 className="text-sm font-semibold text-slate-900">Filters</h2>
                <div className="flex flex-wrap items-end gap-3">
                    <label className="flex min-w-60 flex-1 flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Entity or file</span>
                        <input value={search} onChange={(event) => setSearch(event.target.value)}
                            placeholder="Search the file name or its label" className={select} />
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Status</span>
                        <select value={status} onChange={(event) => setStatus(event.target.value)}
                            className={select}>
                            <option value="">Any</option>
                            {[...LIFECYCLE, "Rejected"].map((name) => (
                                <option key={name} value={name}>
                                    {name}{counts[name] ? ` (${counts[name]})` : ""}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">Prepared by</span>
                        <select value={preparer} onChange={(event) => setPreparer(event.target.value)}
                            className={select}>
                            <option value="">Anyone</option>
                            {preparers.map((name) => <option key={name} value={name}>{name}</option>)}
                        </select>
                    </label>
                    {(search || status || preparer) && (
                        <button type="button"
                            onClick={() => { setSearch(""); setStatus(""); setPreparer("") }}
                            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700
                                       transition hover:border-[#0A2647]">
                            Clear
                        </button>
                    )}
                    <span className="ml-auto text-xs text-slate-500">
                        {filtered.length} of {rows.length} filing(s)
                    </span>
                </div>
            </section>

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Filings</h2>
                {rows.length === 0 ? (
                    <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                        Nothing has been generated for this module yet.
                    </p>
                ) : filtered.length === 0 ? (
                    <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                        No filing matches these filters.
                    </p>
                ) : (
                    <div className="flex flex-col gap-2">
                        {filtered.map(([documentId, item]) => {
                            const open = expanded === documentId
                            return (
                                <article key={documentId}
                                    className="rounded-lg border border-slate-200 bg-white">
                                    <div className="flex flex-wrap items-center gap-4 p-4">
                                        <div className="min-w-60 flex-1">
                                            <p className="font-medium text-slate-900">{item.label}</p>
                                            <p className="font-mono text-xs text-slate-500">
                                                {documentId} · v{item.version}
                                            </p>
                                        </div>

                                        <div className="flex flex-col gap-1">
                                            <span className={`w-fit rounded-full border px-2.5 py-1 text-xs
                                                font-medium ${STATUS_STYLES[item.status]
                                                ?? "border-slate-300 bg-slate-100 text-slate-700"}`}>
                                                {item.status}
                                            </span>
                                            <Progress status={item.status} />
                                        </div>

                                        <div className="min-w-56 flex-1">
                                            <p className="text-xs font-medium uppercase tracking-wide
                                                          text-slate-500">
                                                Next step
                                            </p>
                                            <p className="text-sm text-slate-700">
                                                {NEXT_STEP[item.status] ?? ""}
                                            </p>
                                        </div>

                                        <div className="text-right text-xs text-slate-500">
                                            <p>{when(item.last_generated)}</p>
                                            <p>{item.last_generated_by || "unsigned"}</p>
                                        </div>

                                        <div className="flex flex-wrap items-center gap-1">
                                            {(NEXT_STATUS[item.status] ?? []).map((next) => (
                                                <button key={next} type="button"
                                                    onClick={() => move(documentId, next)}
                                                    className={[
                                                        "rounded-md px-3 py-1.5 text-xs font-medium transition",
                                                        next === "Rejected"
                                                            ? "border border-slate-300 text-slate-700 hover:border-red-400 hover:text-red-700"
                                                            : "bg-[#0A2647] text-white hover:bg-[#123A6B]",
                                                    ].join(" ")}>
                                                    {next}
                                                </button>
                                            ))}
                                            <button type="button"
                                                onClick={() => setExpanded(open ? null : documentId)}
                                                aria-expanded={open}
                                                className="rounded-md border border-slate-300 px-2 py-1.5
                                                           text-xs text-slate-600 transition
                                                           hover:border-[#0A2647]">
                                                {open ? "Hide history" : "History"}
                                            </button>
                                        </div>
                                    </div>

                                    {open && (
                                        <ol className="flex flex-col gap-2 border-t border-slate-100
                                                       bg-slate-50/70 p-4">
                                            {item.history.length === 0 ? (
                                                <li className="text-sm text-slate-500">
                                                    No transition recorded yet.
                                                </li>
                                            ) : item.history.map((event, index) => (
                                                <li key={index} className="flex flex-wrap gap-x-3 text-sm">
                                                    <span className="font-mono text-xs text-slate-500">
                                                        {when(event.timestamp)}
                                                    </span>
                                                    <span className="font-medium text-slate-800">
                                                        v{event.version} · {event.status}
                                                    </span>
                                                    <span className="text-slate-600">{event.user}</span>
                                                    {event.comment && (
                                                        <span className="italic text-slate-500">
                                                            “{event.comment}”
                                                        </span>
                                                    )}
                                                </li>
                                            ))}
                                        </ol>
                                    )}
                                </article>
                            )
                        })}
                    </div>
                )}

                {rows.length > 0 && (
                    <label className="mt-1 flex flex-col gap-1 text-sm">
                        <span className="font-medium text-slate-700">
                            Comment recorded with the next transition
                        </span>
                        <input value={comment} onChange={(event) => setComment(event.target.value)}
                            placeholder="Why it was approved, or what has to be corrected"
                            className={select} />
                    </label>
                )}
            </section>

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">
                    Audit trail
                    <span className="ml-2 text-xs font-normal text-slate-500">
                        {filteredEntries.length} of {entries.length} entries
                    </span>
                </h2>
                <div className="max-h-[420px] overflow-auto rounded-lg border border-slate-200 bg-white">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase
                                          tracking-wide text-slate-500">
                            <tr>
                                <th className="px-3 py-2">When</th>
                                <th className="px-3 py-2">Action</th>
                                <th className="px-3 py-2">Subject</th>
                                <th className="px-3 py-2">User</th>
                                <th className="px-3 py-2">Detail</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredEntries.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-3 py-3 text-sm text-slate-500">
                                        {entries.length === 0
                                            ? "No action has been logged for this module yet."
                                            : "No entry matches these filters."}
                                    </td>
                                </tr>
                            ) : filteredEntries.map((entry, index) => (
                                <tr key={index} className="border-t border-slate-100">
                                    <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                                        {when(entry.timestamp)}
                                    </td>
                                    <td className="px-3 py-2">{entry.action}</td>
                                    <td className="px-3 py-2 font-mono text-xs">{entry.subject}</td>
                                    <td className="px-3 py-2">{entry.user}</td>
                                    <td className="px-3 py-2 text-slate-600">{entry.detail}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </section>
    )
}

export default ControlsAudit
