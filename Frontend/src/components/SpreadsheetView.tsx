import { useEffect, useMemo, useRef, useState } from "react"
import { FiAlertCircle, FiChevronDown, FiChevronUp, FiGrid, FiSearch, FiX } from "react-icons/fi"
import type { SheetPreview, WorkbookPreview } from "src/types/reportingType"

/** A workbook's column width is in characters; this turns it into pixels,
 *  keeping the sheet's designed proportions within readable bounds. */
const columnWidth = (characters: number) =>
    characters > 0 ? Math.min(Math.max(Math.round(characters * 7 + 14), 44), 560) : 88

const columnLetter = (index: number): string => {
    let name = ""
    for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) {
        name = String.fromCharCode(65 + ((n - 1) % 26)) + name
    }
    return name
}

type Layout = {
    /** "r,c" of each merge's top-left cell, with its spans. */
    anchors: Map<string, [number, number]>
    /** "r,c" of every cell a merge covers, other than its anchor. */
    covered: Set<string>
}

function layoutOf(sheet: SheetPreview): Layout {
    const anchors = new Map<string, [number, number]>()
    const covered = new Set<string>()
    for (const [row, col, rowSpan, colSpan] of sheet.merges) {
        const rows = Math.min(rowSpan, sheet.rows.length - row)
        const cols = Math.min(colSpan, sheet.cols - col)
        if (rows <= 0 || cols <= 0) continue
        anchors.set(`${row},${col}`, [rows, cols])
        for (let r = row; r < row + rows; r++) {
            for (let c = col; c < col + cols; c++) {
                if (r !== row || c !== col) covered.add(`${r},${c}`)
            }
        }
    }
    return { anchors, covered }
}

/**
 * A regulator's workbook, drawn in the page: sheet tabs along the bottom as
 * in a spreadsheet, column letters and row numbers pinned while scrolling,
 * merged cells, bold headings and filled cells as the file sets them, and a
 * search that steps through every match.
 */
const SpreadsheetView: React.FC<{ load: () => Promise<WorkbookPreview> }> = ({ load }) => {
    const [workbook, setWorkbook] = useState<WorkbookPreview | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [active, setActive] = useState(0)
    const [query, setQuery] = useState("")
    const [cursor, setCursor] = useState(0)
    const gridRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        let current = true
        setWorkbook(null)
        setError(null)
        load()
            .then((found) => {
                if (!current) return
                setWorkbook(found)
                setActive(found.default_sheet ?? 0)
            })
            .catch((failure: Error) => current && setError(failure.message))
        return () => { current = false }
    }, [load])

    const sheet = workbook?.sheets[active]
    const layout = useMemo(() => (sheet ? layoutOf(sheet) : null), [sheet])

    const needle = query.trim().toLowerCase()
    const matches = useMemo(() => {
        if (!sheet || !needle) return [] as string[]
        const found: string[] = []
        sheet.rows.forEach((row, r) => row.forEach((cell, c) => {
            if (cell?.v && cell.v.toLowerCase().includes(needle)) found.push(`${r},${c}`)
        }))
        return found
    }, [sheet, needle])
    const current = matches.length ? matches[Math.min(cursor, matches.length - 1)] : null

    useEffect(() => { setCursor(0) }, [needle, active])
    useEffect(() => { gridRef.current?.scrollTo({ top: 0, left: 0 }) }, [active])
    useEffect(() => {
        if (!current) return
        gridRef.current?.querySelector(`[data-cell="${current}"]`)
            ?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" })
    }, [current])

    const step = (by: number) => {
        if (matches.length) setCursor((cursor + by + matches.length) % matches.length)
    }

    if (error) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-10 text-center">
                <FiAlertCircle className="h-6 w-6 text-slate-400" />
                <p className="text-sm font-medium text-slate-700">This workbook could not be previewed.</p>
                <p className="max-w-md text-xs text-slate-500">{error} The file itself can still be downloaded.</p>
            </div>
        )
    }

    if (!workbook || !sheet || !layout) {
        return (
            <div className="flex h-full flex-col gap-2 p-4" aria-busy="true" aria-label="Loading the workbook">
                {Array.from({ length: 12 }, (_, index) => (
                    <div key={index} className="h-6 rounded bg-slate-100 bg-shimmer-gradient-track
                                                bg-[length:200%_100%] animate-shimmer"
                        style={{ width: `${95 - (index % 4) * 12}%` }} />
                ))}
            </div>
        )
    }

    const widths = Array.from({ length: sheet.cols }, (_, c) => columnWidth(sheet.widths[c] ?? 0))

    return (
        <div className="flex h-full min-h-0 flex-col">
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
                <span className="inline-flex items-center gap-2 text-xs text-slate-500">
                    <FiGrid className="h-3.5 w-3.5 text-[#1E7F4F]" />
                    <span className="font-medium text-slate-700">{sheet.name}</span>
                    <span>{sheet.rows.length} rows × {sheet.cols} columns</span>
                </span>
                <label className="relative ml-auto flex items-center">
                    <FiSearch className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-slate-400" />
                    <input value={query} onChange={(event) => setQuery(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === "Enter") { event.preventDefault(); step(event.shiftKey ? -1 : 1) }
                            if (event.key === "Escape") setQuery("")
                        }}
                        placeholder="Find in this sheet" aria-label="Find in this sheet"
                        className="w-56 rounded-md border border-slate-300 py-1.5 pl-8 pr-8 text-xs
                                   outline-none transition focus:border-[#0A2647]
                                   focus:ring-2 focus:ring-[#0A2647]/10" />
                    {query && (
                        <button type="button" onClick={() => setQuery("")} aria-label="Clear the search"
                            className="absolute right-2 text-slate-400 hover:text-slate-700">
                            <FiX className="h-3.5 w-3.5" />
                        </button>
                    )}
                </label>
                {needle && (
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                        <span className="tabular-nums">
                            {matches.length ? `${Math.min(cursor, matches.length - 1) + 1} of ${matches.length}` : "No match"}
                        </span>
                        <button type="button" onClick={() => step(-1)} disabled={!matches.length}
                            aria-label="Previous match"
                            className="rounded p-1 hover:bg-slate-100 disabled:opacity-40">
                            <FiChevronUp />
                        </button>
                        <button type="button" onClick={() => step(1)} disabled={!matches.length}
                            aria-label="Next match"
                            className="rounded p-1 hover:bg-slate-100 disabled:opacity-40">
                            <FiChevronDown />
                        </button>
                    </span>
                )}
            </div>

            <div ref={gridRef} className="min-h-0 flex-1 overflow-auto bg-slate-50/60">
                <table className="border-separate border-spacing-0 bg-white text-[12.5px] text-slate-800"
                    style={{ width: 44 + widths.reduce((sum, w) => sum + w, 0), tableLayout: "fixed" }}>
                    <colgroup>
                        <col style={{ width: 44 }} />
                        {widths.map((width, c) => <col key={c} style={{ width }} />)}
                    </colgroup>
                    <thead>
                        <tr>
                            <th className="sticky left-0 top-0 z-30 border-b border-r border-slate-300
                                           bg-slate-100" />
                            {widths.map((_, c) => (
                                <th key={c} scope="col"
                                    className="sticky top-0 z-20 border-b border-r border-slate-300 bg-slate-100
                                               py-1 text-center text-[11px] font-medium text-slate-500">
                                    {columnLetter(c)}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sheet.rows.map((row, r) => (
                            <tr key={r}>
                                <th scope="row"
                                    className="sticky left-0 z-10 border-b border-r border-slate-300 bg-slate-100
                                               px-1 text-center align-top text-[11px] font-medium text-slate-500">
                                    <span className="block py-1">{r + 1}</span>
                                </th>
                                {widths.map((_, c) => {
                                    const key = `${r},${c}`
                                    if (layout.covered.has(key)) return null
                                    const cell = row[c] ?? null
                                    const [rowSpan, colSpan] = layout.anchors.get(key) ?? [1, 1]
                                    const hit = needle && cell?.v.toLowerCase().includes(needle)
                                    return (
                                        <td key={c} rowSpan={rowSpan} colSpan={colSpan} data-cell={key}
                                            title={cell?.v && cell.v.length > 40 ? cell.v : undefined}
                                            className={[
                                                "border-b border-r border-slate-200 px-2 py-1 align-top",
                                                "whitespace-pre-wrap break-words",
                                                cell?.b ? "font-semibold text-[#0A2647]" : "",
                                                current === key
                                                    ? "outline outline-2 -outline-offset-2 outline-[#C77700]"
                                                    : "",
                                            ].join(" ")}
                                            style={{
                                                backgroundColor: hit
                                                    ? "#FFF1C7"
                                                    : cell?.bg ? `${cell.bg}55` : undefined,
                                            }}>
                                            {cell?.v}
                                        </td>
                                    )
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
                {sheet.truncated && (
                    <p className="px-4 py-3 text-xs text-slate-500">
                        This sheet is larger than the preview shows. Download the file for the rest.
                    </p>
                )}
            </div>

            {workbook.sheets.length > 1 && (
                <div role="tablist" aria-label="Sheets"
                    className="flex items-stretch gap-1 overflow-x-auto border-t border-slate-200 bg-slate-100 px-2">
                    {workbook.sheets.map((candidate, index) => (
                        <button key={candidate.name} type="button" role="tab" aria-selected={index === active}
                            onClick={() => setActive(index)}
                            className={[
                                "-mt-px whitespace-nowrap border-t-2 px-4 py-2 text-xs transition",
                                index === active
                                    ? "border-[#1E7F4F] bg-white font-semibold text-[#0A2647] shadow-sm"
                                    : "border-transparent text-slate-600 hover:bg-white/60 hover:text-slate-900",
                            ].join(" ")}>
                            {candidate.name}
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}

export default SpreadsheetView
