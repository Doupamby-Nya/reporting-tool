import { useCallback, useEffect, useId, useRef, useState } from "react"
import type { KeyboardEvent, ReactNode } from "react"
import { FiDownload, FiExternalLink, FiFileText, FiMaximize2, FiMinimize2 } from "react-icons/fi"

import Notice from "@components/Notice"
import SpreadsheetView from "@components/SpreadsheetView"
import type { WorkbookPreview } from "src/types/reportingType"

/**
 * One document on the viewer's shelf. What it can show depends on `format`:
 * a PDF is drawn by the browser from `viewUrl`; a workbook is read through
 * `loadSheets`; a text that could not be bundled carries `externalUrl` to the
 * publisher instead.
 */
export type ViewerDocument = {
    id: string
    title: string
    /** One line under the title on the shelf: the issuer, or what it is for. */
    caption?: string
    description?: string
    format: "pdf" | "sheet" | "external" | "missing"
    filename?: string
    size?: number
    viewUrl?: string
    downloadUrl?: string
    loadSheets?: () => Promise<WorkbookPreview>
    externalUrl?: string
    /** Who publishes it, for the external notice: "Open on <source>". */
    source?: string
}

const BADGES: Record<ViewerDocument["format"], { label: string; colour: string }> = {
    pdf: { label: "PDF", colour: "#B3261E" },
    sheet: { label: "XLS", colour: "#1E7F4F" },
    external: { label: "WEB", colour: "#1F5FA8" },
    missing: { label: "N/A", colour: "#94A3B8" },
}

const sizeOf = (bytes?: number) => {
    if (!bytes) return null
    return bytes >= 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

/** A small page with a folded corner and the format written across it. */
const FileBadge: React.FC<{ format: ViewerDocument["format"]; active: boolean }> = ({ format, active }) => {
    const badge = BADGES[format]
    return (
        <span className="relative inline-flex h-10 w-8 shrink-0 items-end justify-center" aria-hidden="true">
            <svg viewBox="0 0 32 40" className="absolute inset-0 h-full w-full">
                <path d="M3 1.5h18l9.5 9.5v26a1.5 1.5 0 0 1-1.5 1.5H3A1.5 1.5 0 0 1 1.5 37V3A1.5 1.5 0 0 1 3 1.5Z"
                    fill={active ? "#fff" : "#F8FAFC"} stroke={active ? badge.colour : "#CBD5E1"} strokeWidth="1.5" />
                <path d="M21 1.5V9.5a1.5 1.5 0 0 0 1.5 1.5h8" fill="none"
                    stroke={active ? badge.colour : "#CBD5E1"} strokeWidth="1.5" />
            </svg>
            <span className="relative mb-1.5 rounded-[3px] px-1 text-[8.5px] font-bold leading-[13px] tracking-wide
                             text-white" style={{ backgroundColor: badge.colour }}>
                {badge.label}
            </span>
        </span>
    )
}

const ActionLink: React.FC<{ href: string; children: ReactNode; download?: boolean; primary?: boolean }> = (
    { href, children, download, primary }) => (
    <a href={href} target={download ? undefined : "_blank"} rel="noreferrer"
        className={[
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition",
            primary
                ? "bg-[#0A2647] text-white shadow-sm hover:bg-[#123A6B]"
                : "border border-slate-300 bg-white text-slate-700 hover:border-[#0A2647] hover:text-[#0A2647]",
        ].join(" ")}>
        {children}
    </a>
)

/**
 * Several reference documents behind one shelf, each shown in place.
 *
 * The shelf reads like a row of files: the open one is lifted and joined to
 * the reading pane below. PDFs render in the browser's own reader, workbooks
 * in the spreadsheet view, and a text the platform could not bundle shows a
 * notice pointing to its publisher. The pane can be expanded to the whole
 * window; Escape brings it back. Workbooks are fetched once per visit, so
 * moving between documents is instant after the first look.
 */
const DocumentViewer: React.FC<{ documents: ViewerDocument[]; label: string }> = ({ documents, label }) => {
    const [selectedId, setSelectedId] = useState(documents[0]?.id)
    const [expanded, setExpanded] = useState(false)
    const cache = useRef(new Map<string, Promise<WorkbookPreview>>())
    const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
    const panelId = useId()

    // A new set of documents (another report, another module) starts over.
    const signature = documents.map((doc) => doc.id).join("|")
    useEffect(() => {
        setSelectedId((current) => documents.some((doc) => doc.id === current) ? current : documents[0]?.id)
        cache.current.clear()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [signature])

    const selected = documents.find((doc) => doc.id === selectedId) ?? documents[0]

    useEffect(() => {
        if (!expanded) return
        const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setExpanded(false) }
        const overflow = document.body.style.overflow
        document.body.style.overflow = "hidden"
        window.addEventListener("keydown", onKey)
        return () => {
            document.body.style.overflow = overflow
            window.removeEventListener("keydown", onKey)
        }
    }, [expanded])

    const loadSheets = useCallback(() => {
        if (!selected?.loadSheets) return Promise.reject(new Error("No workbook to preview."))
        let pending = cache.current.get(selected.id)
        if (!pending) {
            pending = selected.loadSheets()
            pending.catch(() => cache.current.delete(selected.id))
            cache.current.set(selected.id, pending)
        }
        return pending
    }, [selected])

    if (!selected) return null

    const onShelfKey = (event: KeyboardEvent<HTMLDivElement>) => {
        const index = documents.findIndex((doc) => doc.id === selected.id)
        const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: documents.length - 1 }[event.key]
        if (next === undefined) return
        event.preventDefault()
        const target = (next + documents.length) % documents.length
        setSelectedId(documents[target].id)
        tabRefs.current[target]?.focus()
    }

    const size = sizeOf(selected.size)
    const readable = selected.format === "pdf" || selected.format === "sheet"

    return (
        <>
            {expanded && (
                <div className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-[2px]"
                    onClick={() => setExpanded(false)} aria-hidden="true" />
            )}
            <section aria-label={label}
                className={[
                    "flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white",
                    "shadow-[0_1px_2px_rgba(10,38,71,0.06),0_12px_32px_-18px_rgba(10,38,71,0.3)]",
                    expanded ? "fixed inset-3 z-50 sm:inset-6" : "relative",
                ].join(" ")}>

                {documents.length > 1 && (
                    <div role="tablist" aria-label={label} onKeyDown={onShelfKey}
                        className="grid gap-2 border-b border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100/70
                                   p-3 sm:grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
                        {documents.map((doc, index) => {
                            const active = doc.id === selected.id
                            return (
                                <button key={doc.id} type="button" role="tab" aria-selected={active}
                                    aria-controls={panelId} tabIndex={active ? 0 : -1}
                                    ref={(node) => { tabRefs.current[index] = node }}
                                    onClick={() => setSelectedId(doc.id)}
                                    className={[
                                        "group relative flex items-center gap-3 rounded-lg border px-3 py-2.5",
                                        "text-left outline-none transition duration-200",
                                        "focus-visible:ring-2 focus-visible:ring-[#1F5FA8]/40",
                                        active
                                            ? "-translate-y-0.5 border-[#0A2647]/25 bg-white shadow-[0_8px_18px_-10px_rgba(10,38,71,0.45)]"
                                            : "border-transparent hover:-translate-y-px hover:border-slate-200 hover:bg-white/70",
                                    ].join(" ")}>
                                    <span className={[
                                        "absolute inset-x-3 top-0 h-0.5 rounded-full transition",
                                        active ? "opacity-100" : "opacity-0",
                                    ].join(" ")} style={{ backgroundColor: BADGES[doc.format].colour }} />
                                    <FileBadge format={doc.format} active={active} />
                                    <span className="min-w-0">
                                        <span className={[
                                            "line-clamp-2 text-sm font-semibold leading-snug",
                                            active ? "text-[#0A2647]" : "text-slate-700 group-hover:text-slate-900",
                                        ].join(" ")}>
                                            {doc.title}
                                        </span>
                                        {doc.caption && (
                                            <span className="line-clamp-1 text-[11px] text-slate-500">{doc.caption}</span>
                                        )}
                                    </span>
                                </button>
                            )
                        })}
                    </div>
                )}

                <header className="flex flex-wrap items-start gap-x-6 gap-y-3 border-b border-slate-200 px-5 py-4">
                    {/* A basis wide enough that the actions wrap below the title
                        on a phone rather than squeezing it. */}
                    <div className="min-w-0 flex-1 basis-64">
                        <h2 className="text-base font-semibold text-slate-900">{selected.title}</h2>
                        {selected.description && (
                            <p className="mt-0.5 max-w-3xl text-sm text-slate-600">{selected.description}</p>
                        )}
                        {(selected.filename || size) && (
                            <p className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                <FiFileText className="h-3 w-3 shrink-0" />
                                {selected.filename && <span className="break-all font-mono">{selected.filename}</span>}
                                {size && <span>· {size}</span>}
                            </p>
                        )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {selected.format === "pdf" && selected.viewUrl && (
                            <ActionLink href={selected.viewUrl}>
                                <FiExternalLink /> New tab
                            </ActionLink>
                        )}
                        {selected.downloadUrl && (
                            <ActionLink href={selected.downloadUrl} download primary>
                                <FiDownload /> Download
                            </ActionLink>
                        )}
                        {readable && (
                            <button type="button" onClick={() => setExpanded(!expanded)}
                                aria-label={expanded ? "Leave full screen" : "Full screen"}
                                title={expanded ? "Leave full screen (Esc)" : "Full screen"}
                                className="inline-flex h-[30px] w-[30px] items-center justify-center rounded-md border
                                           border-slate-300 text-slate-600 transition hover:border-[#0A2647]
                                           hover:text-[#0A2647]">
                                {expanded ? <FiMinimize2 /> : <FiMaximize2 />}
                            </button>
                        )}
                    </div>
                </header>

                <div id={panelId} role="tabpanel"
                    className={[
                        "relative min-h-0",
                        readable ? (expanded ? "flex-1" : "h-[72vh] min-h-[520px]") : "",
                    ].join(" ")}>
                    {selected.format === "pdf" && selected.viewUrl && (
                        <>
                            {/* Behind the frame: the reader covers it as soon as
                                it paints, with no load event to depend on. */}
                            <div className="absolute inset-0 flex items-center justify-center bg-slate-100">
                                <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300
                                                 border-t-[#0A2647]" aria-hidden="true" />
                            </div>
                            <iframe key={selected.id} title={selected.title} src={`${selected.viewUrl}#view=FitH`}
                                className="relative h-full w-full border-0" />
                        </>
                    )}

                    {selected.format === "sheet" && selected.loadSheets && (
                        <SpreadsheetView key={selected.id} load={loadSheets} />
                    )}

                    {selected.format === "external" && (
                        <div className="bg-[radial-gradient(rgba(10,38,71,0.05)_1px,transparent_1px)]
                                        bg-[length:16px_16px] px-5 pb-10 pt-6 sm:px-10">
                            <Notice eyebrow="Consult at the source"
                                title="This text is read on the publisher's own site"
                                actions={selected.externalUrl && (
                                    <a href={selected.externalUrl} target="_blank" rel="noreferrer"
                                        className="inline-flex items-center gap-2 rounded-md bg-[#0A2647] px-4 py-2
                                                   text-sm font-medium text-white shadow-sm transition
                                                   hover:bg-[#123A6B]">
                                        Open on {selected.source ?? "the publisher's site"}
                                        <FiExternalLink className="h-4 w-4" />
                                    </a>
                                )}>
                                The official page is protected against automated access or built in the
                                browser, so no copy could be bundled here. Reading it at the source also
                                guarantees the version in force.
                            </Notice>
                        </div>
                    )}

                    {selected.format === "missing" && (
                        <p className="px-5 py-8 text-center text-sm text-slate-500">
                            No document is bundled for this entry yet.
                        </p>
                    )}
                </div>
            </section>
        </>
    )
}

export default DocumentViewer
