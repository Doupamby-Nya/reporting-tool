import { useEffect, useMemo, useState } from "react"
import { toast } from "react-toastify"

import { deleteDraft, listDrafts } from "@api/reportingApi"
import type { DraftSummary } from "src/types/reportingType"

/**
 * The saved drafts of one module, as something a preparer can actually
 * search.
 *
 * A filing is rarely finished in one sitting, and a week later nobody
 * remembers the name they typed — they remember the fund and the period. So
 * each draft is listed by what it contains, not only by its name, and the
 * list can be narrowed by entity, by who saved it and by how recently.
 *
 * It opens as a dialog over the form because choosing a draft is a decision
 * taken before working, not alongside it.
 */
const RECENCY = [
    { key: "", label: "Any time" },
    { key: "1", label: "Last 24 hours" },
    { key: "7", label: "Last 7 days" },
    { key: "30", label: "Last 30 days" },
] as const

const when = (timestamp: string) => timestamp.slice(0, 16).replace("T", " ")

/** How long ago, in the words someone would actually use. */
const ago = (timestamp: string): string => {
    const saved = Date.parse(timestamp)
    if (Number.isNaN(saved)) return ""
    const hours = (Date.now() - saved) / 36e5
    if (hours < 1) return "just now"
    if (hours < 24) return `${Math.floor(hours)} h ago`
    const days = Math.floor(hours / 24)
    return days === 1 ? "yesterday" : `${days} days ago`
}

const DraftsPanel: React.FC<{
    moduleKey: string
    moduleLabel: string
    onOpen: (name: string) => void | Promise<void>
    onClose: () => void
}> = ({ moduleKey, moduleLabel, onOpen, onClose }) => {
    const [drafts, setDrafts] = useState<DraftSummary[] | null>(null)
    const [search, setSearch] = useState("")
    const [savedBy, setSavedBy] = useState("")
    const [recency, setRecency] = useState("")
    const [busy, setBusy] = useState(false)

    const load = async () => {
        try {
            setDrafts(await listDrafts(moduleKey))
        } catch (error) {
            toast.error((error as Error).message)
            setDrafts([])
        }
    }

    useEffect(() => { void load() }, [moduleKey])

    // Escape closes it, as a dialog should.
    useEffect(() => {
        const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose() }
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [onClose])

    const authors = useMemo(
        () => Array.from(new Set((drafts ?? []).map((d) => d.saved_by).filter(Boolean))).sort(),
        [drafts])

    const filtered = useMemo(() => {
        const needle = search.trim().toLowerCase()
        const cutoff = recency ? Date.now() - Number(recency) * 864e5 : 0
        return (drafts ?? []).filter((draft) => {
            if (savedBy && draft.saved_by !== savedBy) return false
            if (cutoff && Date.parse(draft.saved_at) < cutoff) return false
            if (!needle) return true
            return [draft.name, draft.entity, draft.code, draft.period]
                .some((value) => String(value ?? "").toLowerCase().includes(needle))
        })
    }, [drafts, search, savedBy, recency])

    const open = async (name: string) => {
        setBusy(true)
        try {
            await onOpen(name)
            onClose()
        } finally {
            setBusy(false)
        }
    }

    const remove = async (name: string) => {
        try {
            await deleteDraft(moduleKey, name)
            toast.success(`Draft “${name}” deleted.`)
            await load()
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const control = "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none " +
        "focus:border-[#0A2647]"

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-slate-900/40
                        p-4 pt-16"
            role="dialog" aria-modal="true" aria-label={`Saved drafts — ${moduleLabel}`}
            onClick={onClose}>
            <div className="w-full max-w-4xl rounded-lg border border-slate-200 bg-white shadow-xl"
                onClick={(event) => event.stopPropagation()}>

                <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
                    <div>
                        <h2 className="text-base font-semibold text-slate-900">Saved drafts</h2>
                        <p className="mt-0.5 text-sm text-slate-600">
                            {moduleLabel} — a submission parked part-way through, to pick up later.
                        </p>
                    </div>
                    <button type="button" onClick={onClose} aria-label="Close"
                        className="rounded-md px-2 py-1 text-xl leading-none text-slate-400
                                   transition hover:bg-slate-100 hover:text-slate-700">
                        ×
                    </button>
                </header>

                {drafts === null ? (
                    <p className="p-5 text-sm text-slate-500">Loading…</p>
                ) : drafts.length === 0 ? (
                    <div className="flex flex-col items-start gap-2 p-8">
                        <p className="text-sm font-medium text-slate-900">
                            No draft has been saved for {moduleLabel} yet.
                        </p>
                        <p className="max-w-lg text-sm text-slate-600">
                            Fill the form in, give it a name at the bottom of the page and save it. It
                            will be listed here with its entity and period so you can find it again
                            without remembering the name.
                        </p>
                        <button type="button" onClick={onClose}
                            className="mt-2 rounded-md bg-[#0A2647] px-4 py-2 text-sm font-medium
                                       text-white transition hover:bg-[#123A6B]">
                            Back to the form
                        </button>
                    </div>
                ) : (
                    <>
                        <div className="flex flex-wrap items-end gap-3 border-b border-slate-200
                                        bg-slate-50 p-4">
                            <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm">
                                <span className="font-medium text-slate-700">Search</span>
                                <input value={search} onChange={(e) => setSearch(e.target.value)}
                                    placeholder="Name, entity, code or period" className={control} />
                            </label>
                            <label className="flex flex-col gap-1 text-sm">
                                <span className="font-medium text-slate-700">Saved by</span>
                                <select value={savedBy} onChange={(e) => setSavedBy(e.target.value)}
                                    className={control}>
                                    <option value="">Anyone</option>
                                    {authors.map((name) => (
                                        <option key={name} value={name}>{name}</option>
                                    ))}
                                </select>
                            </label>
                            <label className="flex flex-col gap-1 text-sm">
                                <span className="font-medium text-slate-700">Saved</span>
                                <select value={recency} onChange={(e) => setRecency(e.target.value)}
                                    className={control}>
                                    {RECENCY.map((option) => (
                                        <option key={option.key} value={option.key}>{option.label}</option>
                                    ))}
                                </select>
                            </label>
                            {(search || savedBy || recency) && (
                                <button type="button"
                                    onClick={() => { setSearch(""); setSavedBy(""); setRecency("") }}
                                    className="rounded-md border border-slate-300 px-3 py-2 text-sm
                                               text-slate-700 transition hover:border-[#0A2647]">
                                    Clear
                                </button>
                            )}
                            <span className="ml-auto text-xs text-slate-500">
                                {filtered.length} of {drafts.length}
                            </span>
                        </div>

                        <div className="max-h-[50vh] overflow-auto p-4">
                            {filtered.length === 0 ? (
                                <p className="px-2 py-6 text-sm text-slate-500">
                                    No draft matches these filters.
                                </p>
                            ) : (
                                <ul className="flex flex-col gap-2">
                                    {filtered.map((draft) => (
                                        <li key={draft.name}
                                            className="flex flex-wrap items-center gap-4 rounded-lg border
                                                       border-slate-200 p-3 transition
                                                       hover:border-[#0A2647]">
                                            <div className="min-w-52 flex-1">
                                                <p className="font-medium text-slate-900">{draft.name}</p>
                                                <p className="text-sm text-slate-600">
                                                    {draft.entity || <span className="italic
                                                        text-slate-400">no entity captured yet</span>}
                                                    {draft.code && (
                                                        <span className="ml-2 font-mono text-xs
                                                                         text-slate-500">
                                                            {draft.code}
                                                        </span>
                                                    )}
                                                </p>
                                            </div>

                                            <div className="text-sm">
                                                <p className="text-xs uppercase tracking-wide
                                                              text-slate-500">Period</p>
                                                <p className="text-slate-700">{draft.period || "—"}</p>
                                            </div>

                                            <div className="text-sm">
                                                <p className="text-xs uppercase tracking-wide
                                                              text-slate-500">Filled</p>
                                                <p className="text-slate-700">
                                                    {draft.fields_filled ?? 0} value(s)
                                                </p>
                                            </div>

                                            <div className="text-right text-xs text-slate-500">
                                                <p title={when(draft.saved_at)}>{ago(draft.saved_at)}</p>
                                                <p>{draft.saved_by || "unsigned"}</p>
                                            </div>

                                            <div className="flex gap-1">
                                                <button type="button" disabled={busy}
                                                    onClick={() => open(draft.name)}
                                                    className="rounded-md bg-[#0A2647] px-3 py-1.5 text-xs
                                                               font-medium text-white transition
                                                               hover:bg-[#123A6B] disabled:opacity-50">
                                                    Open
                                                </button>
                                                <button type="button" onClick={() => remove(draft.name)}
                                                    className="rounded-md border border-slate-300 px-3
                                                               py-1.5 text-xs text-slate-700 transition
                                                               hover:border-red-400 hover:text-red-700">
                                                    Delete
                                                </button>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}

export default DraftsPanel
