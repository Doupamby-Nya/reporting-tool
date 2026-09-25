import type { ReactNode } from "react"

import { ACTIONS, HEAT, moduleMeta } from "@config/activity"
import type { ActivityAction, ActivitySummary } from "src/types/reportingType"

export const Card: React.FC<{ title: string; hint?: string; children: ReactNode; className?: string }> = (
    { title, hint, children, className }) => (
    <section className={`flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5
                         shadow-[0_1px_2px_rgba(10,38,71,0.05)] ${className ?? ""}`}>
        <header>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            {hint && <p className="text-xs text-slate-500">{hint}</p>}
        </header>
        {children}
    </section>
)

type Bar = { key: string; label: string; count: number; color: string; icon?: ReactNode }

/** Ranked horizontal bars; choosing one filters the dashboard to it. */
const BarList: React.FC<{ bars: Bar[]; active: string | null; onPick: (key: string | null) => void }> = (
    { bars, active, onPick }) => {
    const total = bars.reduce((sum, bar) => sum + bar.count, 0) || 1
    const widest = Math.max(1, ...bars.map((bar) => bar.count))
    if (!bars.length) return <p className="text-sm text-slate-500">Nothing yet.</p>
    return (
        <ul className="flex flex-col gap-1">
            {bars.map((bar) => {
                const on = active === bar.key
                return (
                    <li key={bar.key}>
                        <button type="button" onClick={() => onPick(on ? null : bar.key)} aria-pressed={on}
                            className={[
                                "grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md",
                                "px-2 py-1.5 text-left transition",
                                on ? "bg-[#0A2647]/[0.06] ring-1 ring-[#0A2647]/20" : "hover:bg-slate-50",
                            ].join(" ")}>
                            <span className="flex min-w-0 items-center gap-2 text-sm text-slate-800">
                                {bar.icon ?? <span className="h-2.5 w-2.5 shrink-0 rounded-sm"
                                    style={{ backgroundColor: bar.color }} />}
                                <span className="truncate">{bar.label}</span>
                            </span>
                            <span className="text-xs tabular-nums text-slate-500">
                                <span className="font-semibold text-slate-800">{bar.count.toLocaleString()}</span>
                                {" "}· {Math.round((bar.count / total) * 100)}%
                            </span>
                            <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                                <span className="block h-full rounded-full transition-[width] duration-500"
                                    style={{ width: `${(bar.count / widest) * 100}%`, backgroundColor: bar.color }} />
                            </span>
                        </button>
                    </li>
                )
            })}
        </ul>
    )
}

export const ModuleBreakdown: React.FC<{
    summary: ActivitySummary; active: string | null; onPick: (key: string | null) => void
}> = ({ summary, active, onPick }) => (
    <BarList active={active} onPick={onPick}
        bars={summary.by_module.map((row) => ({ key: row.module, count: row.count, ...moduleMeta(row.module) }))} />
)

export const ActionBreakdown: React.FC<{
    summary: ActivitySummary; active: string | null; onPick: (key: string | null) => void
}> = ({ summary, active, onPick }) => (
    <BarList active={active} onPick={onPick}
        bars={summary.by_action.map((row) => {
            const meta = ACTIONS[row.action as ActivityAction]
            const Icon = meta.icon
            return { key: row.action, label: meta.label, count: row.count, color: "#1F5FA8",
                     icon: <Icon className="h-3.5 w-3.5 shrink-0 text-[#1F5FA8]" /> }
        })} />
)

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/** When the work happens: weekday against hour of day, in the viewer's zone. */
export const Rhythm: React.FC<{ grid: number[][] }> = ({ grid }) => {
    const max = Math.max(0, ...grid.flat())
    const shade = (n: number) => HEAT[n === 0 ? 0 : Math.min(4, Math.ceil((n / max) * 4))]
    const peak = max === 0 ? null : (() => {
        for (let d = 0; d < 7; d++) for (let h = 0; h < 24; h++) if (grid[d][h] === max) return [d, h]
        return null
    })()
    return (
        <div className="flex flex-col gap-2">
            <div className="grid grid-cols-[28px_repeat(24,minmax(0,1fr))] gap-[2px]">
                {grid.map((row, day) => [
                    <span key={`l${day}`} className="self-center text-[10px] text-slate-500">{WEEKDAYS[day]}</span>,
                    ...row.map((count, hour) => (
                        <span key={`${day}-${hour}`} title={`${WEEKDAYS[day]} ${hour}:00 · ${count} activit${count === 1 ? "y" : "ies"}`}
                            className="aspect-square rounded-[2px]" style={{ backgroundColor: shade(count) }} />
                    )),
                ])}
                <span />
                {Array.from({ length: 24 }, (_, hour) => (
                    <span key={`h${hour}`} className="text-center text-[9px] text-slate-400">
                        {hour % 6 === 0 ? hour : ""}
                    </span>
                ))}
            </div>
            {peak && (
                <p className="text-xs text-slate-500">
                    Busiest slot: <span className="font-medium text-slate-700">
                        {WEEKDAYS[peak[0]]} around {peak[1]}:00</span>
                </p>
            )}
        </div>
    )
}
