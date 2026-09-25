import { useState } from "react"
import { FiChevronDown, FiFile } from "react-icons/fi"

import { ACTIONS, countOf, moduleMeta } from "@config/activity"
import type { ActivityGroup, ActivitySummary } from "src/types/reportingType"
import { monthName, shortDay } from "./dates"

const MONTHS_AT_ONCE = 3

/** One kind of work in a month: a sentence, then where it happened. */
const Group: React.FC<{ group: ActivityGroup; open?: boolean; onModule: (key: string) => void }> = (
    { group, open: initiallyOpen = true, onModule }) => {
    const [open, setOpen] = useState(initiallyOpen)
    const meta = ACTIONS[group.action]
    const Icon = meta.icon
    const widest = Math.max(...group.modules.map((row) => row.count))
    const where = group.modules.length === 1
        ? ` in ${moduleMeta(group.modules[0].module).label}`
        : ` in ${group.modules.length} reportings`

    return (
        <li className="relative pb-6 pl-12 last:pb-2">
            <span className="absolute left-0 top-0 flex h-8 w-8 items-center justify-center rounded-full border
                             border-slate-200 bg-white text-[#0A2647] shadow-sm">
                <Icon className="h-4 w-4" />
            </span>
            <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className="group flex w-full items-start justify-between gap-3 pt-1 text-left">
                <span className="text-[15px] font-medium text-slate-900">
                    {meta.sentence(group.count)}{where}
                </span>
                <FiChevronDown className={`mt-1 h-4 w-4 shrink-0 text-slate-400 transition group-hover:text-[#0A2647]
                                           ${open ? "" : "-rotate-90"}`} />
            </button>

            {open && (
                <div className="mt-2 flex flex-col gap-3">
                    <ul className="flex flex-col gap-1.5">
                        {group.modules.map((row) => {
                            const module = moduleMeta(row.module)
                            return (
                                <li key={row.module} className="grid grid-cols-[minmax(0,1fr)_minmax(80px,180px)] items-center gap-4">
                                    <span className="flex min-w-0 items-center gap-2 text-sm">
                                        <button type="button" onClick={() => onModule(row.module)}
                                            className="truncate font-medium text-[#1F5FA8] underline-offset-2 hover:underline">
                                            {module.label}
                                        </button>
                                        <span className="shrink-0 text-xs text-slate-500">
                                            {countOf(row.count, meta.unit)}
                                        </span>
                                    </span>
                                    <span className="h-2 overflow-hidden rounded-full bg-slate-100">
                                        <span className="block h-full rounded-full"
                                            style={{ width: `${Math.max(6, (row.count / widest) * 100)}%`,
                                                     backgroundColor: module.color }} />
                                    </span>
                                </li>
                            )
                        })}
                    </ul>
                    {group.subjects.length > 0 && (
                        <ul className="flex flex-col divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                            {group.subjects.map((subject) => (
                                <li key={`${subject.module}-${subject.subject}`}
                                    className="flex items-center gap-3 px-3 py-2 text-sm">
                                    <FiFile className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                                    <span className="min-w-0 flex-1 truncate font-mono text-[12.5px] text-slate-800"
                                        title={subject.subject}>
                                        {subject.subject}
                                    </span>
                                    <span className="hidden shrink-0 items-center gap-1.5 text-xs text-slate-500 sm:flex">
                                        <span className="h-2 w-2 rounded-full"
                                            style={{ backgroundColor: moduleMeta(subject.module).color }} />
                                        {moduleMeta(subject.module).label}
                                    </span>
                                    <span className="w-14 shrink-0 text-right text-xs tabular-nums text-slate-500">
                                        {shortDay(subject.at)}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </li>
    )
}

/**
 * The work under the calendar, month by month and newest first: for each
 * month, each kind of work in one sentence ("Generated 12 filings in 3
 * reportings"), where it happened, and the latest things it was done to.
 */
const ActivityTimeline: React.FC<{
    months: ActivitySummary["months"]
    onModule: (key: string) => void
}> = ({ months, onModule }) => {
    const [shown, setShown] = useState(MONTHS_AT_ONCE)

    if (!months.length) {
        return (
            <p className="rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm
                          text-slate-500">
                No activity in this period.
            </p>
        )
    }

    return (
        <div className="flex flex-col gap-2">
            {months.slice(0, shown).map((month, index) => (
                <section key={month.month}>
                    <h3 className="mb-4 flex items-center gap-3 text-xs font-semibold text-slate-900">
                        <span>{monthName(month.month).replace(/ (\d{4})$/, "")}</span>
                        <span className="font-normal text-slate-500">{month.month.slice(0, 4)}</span>
                        <span className="h-px flex-1 bg-slate-200" />
                    </h3>
                    {/* The rail the icons sit on. */}
                    <ol className="relative before:absolute before:bottom-2 before:left-4 before:top-2 before:w-0.5
                                   before:bg-slate-200">
                        {month.groups.map((group) => (
                            // The latest month is read in full; older ones open on demand,
                            // so a busy organisation's year stays a page and not a scroll.
                            <Group key={group.action} group={group} open={index === 0} onModule={onModule} />
                        ))}
                    </ol>
                </section>
            ))}
            {shown < months.length && (
                <button type="button" onClick={() => setShown(shown + MONTHS_AT_ONCE)}
                    className="mt-2 w-full rounded-lg border border-slate-200 bg-white py-2.5 text-sm font-semibold
                               text-[#1F5FA8] transition hover:border-[#0A2647] hover:bg-slate-50">
                    Show more activity
                </button>
            )}
        </div>
    )
}

export default ActivityTimeline
