import { useEffect, useState } from "react"
import { FiInfo, FiX } from "react-icons/fi"

import KpiRow from "@components/KpiRow"
import { ACTIONS, moduleMeta } from "@config/activity"
import type { ActivityAction, ActivityFilters, ActivitySummary } from "src/types/reportingType"
import ActivityCalendar, { HeatLegend } from "./ActivityCalendar"
import { ActionBreakdown, Card, ModuleBreakdown, Rhythm } from "./ActivityBreakdowns"
import { OrganisationList, PeopleTable } from "./ActivityPeople"
import ActivityTimeline from "./ActivityTimeline"
import { DAY_MS, longDay, parseDay, shortDay } from "./dates"

type Local = { year: number | null; day: string | null; module: string | null; action: string | null }

const NONE: Local = { year: null, day: null, module: null, action: null }

/**
 * A usage dashboard, whatever its scope: a person's own work, one
 * organisation, one of its people, or every organisation.
 *
 * Laid out like GitHub's contribution page — the year as a calendar, the
 * period chooser on the right, the work month by month underneath — with
 * what a regulatory team also asks: in which reporting the work went, what
 * kind of work it was, when in the week it happens, and, for an
 * administrator, who did it. Every breakdown is also a filter, and the
 * calendar narrows everything under it to the day chosen on it.
 */
const ActivityDashboard: React.FC<{
    load: (filters: ActivityFilters) => Promise<ActivitySummary>
    /** The scope, fixed by the page: an organisation, a person. */
    scope?: ActivityFilters
    /** Shown on an administrator's dashboard. */
    onPickUser?: (userId: number) => void
    onPickOrganisation?: (organisationId: number) => void
}> = ({ load, scope, onPickUser, onPickOrganisation }) => {
    const [local, setLocal] = useState<Local>(NONE)
    const [summary, setSummary] = useState<ActivitySummary | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState(false)
    const scopeKey = JSON.stringify(scope ?? {})

    // Another person or organisation: the filters belong to the previous one.
    useEffect(() => { setLocal(NONE) }, [scopeKey])

    useEffect(() => {
        let current = true
        setBusy(true)
        load({ ...(scope ?? {}), ...local })
            .then((found) => { if (current) { setSummary(found); setError(null) } })
            .catch((failure: Error) => current && setError(failure.message))
            .finally(() => current && setBusy(false))
        return () => { current = false }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [load, scopeKey, local.year, local.day, local.module, local.action])

    const set = (patch: Partial<Local>) => setLocal({ ...local, ...patch })

    if (error && !summary) {
        return <p className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-sm text-slate-600">{error}</p>
    }
    if (!summary) return <Skeleton />

    const period = local.year ? `in ${local.year}` : "in the last 12 months"
    const spanDays = Math.round((parseDay(summary.range.to).getTime() - parseDay(summary.range.from).getTime()) / DAY_MS) + 1
    const chips = [
        local.module && { key: "module", label: `Reporting: ${moduleMeta(local.module).label}`, clear: { module: null } },
        local.action && { key: "action", label: `Work: ${ACTIONS[local.action as ActivityAction]?.label ?? local.action}`,
                          clear: { action: null } },
        local.day && { key: "day", label: `Day: ${longDay(local.day)}`, clear: { day: null } },
    ].filter(Boolean) as { key: string; label: string; clear: Partial<Local> }[]

    return (
        <div className={`grid gap-6 transition-opacity lg:grid-cols-[minmax(0,1fr)_150px] ${busy ? "opacity-70" : ""}`}>
            <div className="flex min-w-0 flex-col gap-6">
                <Card title={`${summary.total.toLocaleString()} ${summary.total === 1 ? "activity" : "activities"} ${period}`}>
                    <ActivityCalendar days={summary.days} from={summary.range.from} to={summary.range.to}
                        selected={local.day} onSelect={(day) => set({ day })} />
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <details className="group text-xs text-slate-500">
                            <summary className="inline-flex cursor-pointer list-none items-center gap-1 hover:text-[#0A2647]">
                                <FiInfo className="h-3.5 w-3.5" /> How activity is counted
                            </summary>
                            <p className="mt-2 max-w-xl leading-relaxed">
                                Each filing generated, review decision, control run, file ingested, draft saved,
                                regulatory text consulted, download and settings change counts once, on the day it
                                was done in your time zone ({summary.timezone}). Opening a screen does not count.
                            </p>
                        </details>
                        <HeatLegend />
                    </div>
                </Card>

                {chips.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2">
                        {chips.map((chip) => (
                            <button key={chip.key} type="button" onClick={() => set(chip.clear)}
                                className="inline-flex items-center gap-1.5 rounded-full border border-[#0A2647]/20
                                           bg-white px-3 py-1 text-xs font-medium text-[#0A2647] shadow-sm
                                           transition hover:border-[#0A2647]">
                                {chip.label} <FiX className="h-3 w-3" />
                            </button>
                        ))}
                        <button type="button" onClick={() => setLocal({ ...NONE, year: local.year })}
                            className="text-xs font-medium text-slate-500 underline-offset-2 hover:text-[#0A2647] hover:underline">
                            Clear filters
                        </button>
                        <span className="text-xs text-slate-500">
                            {summary.shown_total.toLocaleString()} matching
                        </span>
                    </div>
                )}

                <KpiRow items={[
                    { label: "Active days", value: summary.active_days.toLocaleString(),
                      hint: `out of ${spanDays} · ${Math.round((summary.active_days / spanDays) * 100)}%` },
                    { label: "Current streak", value: `${summary.current_streak} d`, hint: "days in a row, to today" },
                    { label: "Longest streak", value: `${summary.longest_streak} d`, hint: `days in a row ${period}` },
                    { label: "Busiest day",
                      value: summary.busiest_day ? String(summary.busiest_day.count) : "0",
                      hint: summary.busiest_day ? `activities on ${shortDay(summary.busiest_day.date)}` : "no activity yet" },
                ]} />

                <div className="grid gap-6 xl:grid-cols-3">
                    <Card title="By reporting" hint="Choose one to see only its work">
                        <ModuleBreakdown summary={summary} active={local.module} onPick={(module) => set({ module })} />
                    </Card>
                    <Card title="By kind of work" hint="Choose one to see only that work">
                        <ActionBreakdown summary={summary} active={local.action} onPick={(action) => set({ action })} />
                    </Card>
                    <Card title="Weekly rhythm" hint={`When the work happens (${summary.timezone})`}>
                        <Rhythm grid={summary.by_hour} />
                    </Card>
                </div>

                {onPickOrganisation && summary.by_organisation.length > 0 && (
                    <Card title="By organisation" hint="Choose one to open it">
                        <OrganisationList rows={summary.by_organisation} onPick={onPickOrganisation} />
                    </Card>
                )}

                {onPickUser && summary.by_user.length > 0 && (
                    <Card title="People" hint="Choose someone to see their own activity">
                        <PeopleTable rows={summary.by_user} onPick={onPickUser} />
                    </Card>
                )}

                <section className="flex flex-col gap-4">
                    <h2 className="text-base font-semibold text-slate-900">
                        Activity{local.day ? ` on ${longDay(local.day)}` : ""}
                    </h2>
                    <ActivityTimeline key={`${scopeKey}${JSON.stringify(local)}`} months={summary.months}
                        onModule={(module) => set({ module })} />
                </section>
            </div>

            <nav aria-label="Period" className="order-first lg:order-none">
                <ul className="flex gap-1 overflow-x-auto lg:sticky lg:top-44 lg:flex-col">
                    {[null, ...summary.years].map((year) => {
                        const on = local.year === year
                        return (
                            <li key={year ?? "last"}>
                                <button type="button" onClick={() => set({ year, day: null })} aria-pressed={on}
                                    className={[
                                        "w-full whitespace-nowrap rounded-lg px-4 py-2 text-left text-sm transition",
                                        on ? "bg-[#0A2647] font-semibold text-white shadow-sm"
                                           : "text-slate-600 hover:bg-white hover:text-[#0A2647]",
                                    ].join(" ")}>
                                    {year ?? "Last 12 months"}
                                </button>
                            </li>
                        )
                    })}
                </ul>
            </nav>
        </div>
    )
}

const Skeleton: React.FC = () => (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading the activity">
        {[180, 90, 220].map((height, index) => (
            <div key={index} className="animate-shimmer rounded-xl border border-slate-200 bg-white bg-shimmer-gradient-track
                                        bg-[length:200%_100%]" style={{ height }} />
        ))}
    </div>
)

export default ActivityDashboard
