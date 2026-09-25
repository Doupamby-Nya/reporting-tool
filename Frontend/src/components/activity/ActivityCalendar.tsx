import { useMemo, useRef, useState } from "react"
import type { KeyboardEvent } from "react"

import { HEAT } from "@config/activity"
import { DAY_MS, isoDay, longDay, parseDay, weekdayOf } from "./dates"

const CELL = 11
const GAP = 3
const STEP = CELL + GAP
const LEFT = 30   // room for Mon / Wed / Fri
const TOP = 18    // room for the month names

type Cell = { day: string; count: number; week: number; weekday: number }

/** Four shades above "nothing", cut at the quartiles of the active days, so
 *  one exceptional day does not wash every other day out to the palest. */
function levelsOf(counts: number[]): (count: number) => number {
    const sorted = counts.filter((n) => n > 0).sort((a, b) => a - b)
    if (!sorted.length) return () => 0
    const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))]
    const [q1, q2, q3] = [at(0.25), at(0.5), at(0.75)]
    return (n) => (n <= 0 ? 0 : n <= q1 ? 1 : n <= q2 ? 2 : n <= q3 ? 3 : 4)
}

const plural = (n: number) => (n === 1 ? "1 activity" : `${n} activities`)

/**
 * A year of work as a grid of days: one column a week, Monday at the top, a
 * shade for how much was done. Pointing at a day names it; choosing one
 * (click, or Enter from the keyboard) narrows the rest of the dashboard to
 * that day, and choosing it again lets go.
 */
const ActivityCalendar: React.FC<{
    days: [string, number][]
    from: string
    to: string
    selected: string | null
    onSelect: (day: string | null) => void
}> = ({ days, from, to, selected, onSelect }) => {
    const wrapper = useRef<HTMLDivElement>(null)
    const [hover, setHover] = useState<{ cell: Cell; x: number; y: number } | null>(null)
    const [focus, setFocus] = useState<string | null>(null)

    const { cells, weeks, months, level } = useMemo(() => {
        const counts = new Map(days)
        const start = parseDay(from)
        const end = parseDay(to)
        const gridStart = start.getTime() - weekdayOf(start) * DAY_MS
        const list: Cell[] = []
        for (let t = start.getTime(); t <= end.getTime(); t += DAY_MS) {
            const date = new Date(t)
            const day = isoDay(date)
            list.push({ day, count: counts.get(day) ?? 0, weekday: weekdayOf(date),
                week: Math.floor((t - gridStart) / (7 * DAY_MS)) })
        }
        const weekCount = (list[list.length - 1]?.week ?? 0) + 1
        // A month is named over the first column that opens on it, unless
        // that would crowd the previous name.
        const names: { week: number; label: string }[] = []
        let lastMonth = -1
        for (const cell of list) {
            const month = parseDay(cell.day).getUTCMonth()
            if (month !== lastMonth && (cell.weekday === 0 || cell === list[0])) {
                if (!names.length || cell.week - names[names.length - 1].week >= 3) {
                    names.push({ week: cell.week, label: parseDay(cell.day).toLocaleDateString(
                        "en-GB", { month: "short", timeZone: "UTC" }) })
                }
                lastMonth = month
            }
        }
        return { cells: list, weeks: weekCount, months: names, level: levelsOf(list.map((c) => c.count)) }
    }, [days, from, to])

    const width = LEFT + weeks * STEP
    const height = TOP + 7 * STEP
    const byDay = useMemo(() => new Map(cells.map((cell) => [cell.day, cell])), [cells])

    const show = (cell: Cell, target: Element) => {
        const box = target.getBoundingClientRect()
        const frame = wrapper.current?.getBoundingClientRect()
        if (!frame) return
        setHover({ cell, x: box.left - frame.left + box.width / 2, y: box.top - frame.top })
    }

    const onKey = (event: KeyboardEvent<SVGSVGElement>) => {
        const current = byDay.get(focus ?? selected ?? cells[cells.length - 1]?.day ?? "")
        if (!current) return
        const moves: Record<string, number> = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 }
        if (event.key in moves) {
            event.preventDefault()
            const next = isoDay(new Date(parseDay(current.day).getTime() + moves[event.key] * DAY_MS))
            const cell = byDay.get(next)
            if (!cell) return
            setFocus(next)
            const node = wrapper.current?.querySelector(`[data-day="${next}"]`)
            if (node) show(cell, node)
        } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            onSelect(selected === current.day ? null : current.day)
        } else if (event.key === "Escape") {
            onSelect(null)
        }
    }

    const active = cells.filter((cell) => cell.count > 0).length

    return (
        <div ref={wrapper} className="relative">
            <div className="overflow-x-auto pb-1">
                {/* Only a keyboard user sees where the focus is; a click does not leave a frame. */}
                <svg viewBox={`0 0 ${width} ${height}`}
                    className="block h-auto min-w-[640px] rounded outline-none focus-visible:outline
                               focus-visible:outline-2 focus-visible:outline-offset-4
                               focus-visible:outline-[#1F5FA8]/50"
                    style={{ width: "100%", maxWidth: width * 1.7 }}
                    tabIndex={0} role="img" onKeyDown={onKey}
                    onBlur={() => { setFocus(null); setHover(null) }}
                    aria-label={`Activity calendar: ${active} active day(s) between ${longDay(from)} and ${longDay(to)}. `
                        + "Use the arrow keys to move between days and Enter to choose one."}
                    onMouseLeave={() => setHover(null)}>
                    {months.map((month) => (
                        <text key={`${month.week}-${month.label}`} x={LEFT + month.week * STEP} y={11}
                            className="fill-slate-500" fontSize="9.5">{month.label}</text>
                    ))}
                    {[["Mon", 0], ["Wed", 2], ["Fri", 4]].map(([label, row]) => (
                        <text key={label} x={0} y={TOP + (row as number) * STEP + CELL - 1.5}
                            className="fill-slate-500" fontSize="9">{label}</text>
                    ))}
                    {cells.map((cell) => {
                        const chosen = selected === cell.day
                        const dimmed = selected !== null && !chosen
                        const focused = focus === cell.day
                        return (
                            <rect key={cell.day} data-day={cell.day}
                                x={LEFT + cell.week * STEP} y={TOP + cell.weekday * STEP}
                                width={CELL} height={CELL} rx={2.5}
                                fill={HEAT[level(cell.count)]}
                                opacity={dimmed ? 0.35 : 1}
                                stroke={chosen || focused ? "#C77700" : "rgba(10,38,71,0.06)"}
                                strokeWidth={chosen || focused ? 1.6 : 0.6}
                                className="cursor-pointer transition-opacity"
                                onMouseEnter={(event) => show(cell, event.currentTarget)}
                                onClick={() => onSelect(chosen ? null : cell.day)} />
                        )
                    })}
                </svg>
            </div>

            {hover && (
                <div role="tooltip"
                    className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap
                               rounded-md bg-[#0A2647] px-2.5 py-1.5 text-xs text-white shadow-lg"
                    style={{ left: hover.x, top: hover.y - 8 }}>
                    <span className="font-semibold">
                        {hover.cell.count ? plural(hover.cell.count) : "No activity"}
                    </span>{" "}
                    on {longDay(hover.cell.day)}
                    <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent
                                     border-t-[#0A2647]" />
                </div>
            )}
        </div>
    )
}

export const HeatLegend: React.FC = () => (
    <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
        Less
        {HEAT.map((colour) => (
            <span key={colour} className="h-[11px] w-[11px] rounded-[2.5px] border border-[#0A2647]/5"
                style={{ backgroundColor: colour }} />
        ))}
        More
    </span>
)

export default ActivityCalendar
