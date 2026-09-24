import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { fetchAuditLog, fetchDocuments, fetchFunds } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import { useCurrentUser } from "@hooks/useCurrentUser"
import type { AuditEntry, Fund, TrackedDocument } from "src/types/reportingType"

type ModuleRow = { key: string; label: string; total: number; review: number; approved: number }

/**
 * The signed-in user's dashboard: where their filings stand, across the
 * modules they use, and what was done recently. Read from the API rather
 * than kept client-side, so the figures are the ones the review screens work
 * from. The fund registry is shown to PRIIPs users, who maintain it.
 */
const Dashboard: React.FC = () => {
    const { modules: MODULES, canUse } = useCurrentUser()
    const showFunds = canUse("priips")
    const [funds, setFunds] = useState<Fund[]>([])
    const [rows, setRows] = useState<ModuleRow[]>([])
    const [log, setLog] = useState<AuditEntry[]>([])
    const [query, setQuery] = useState("")

    useEffect(() => {
        if (showFunds) fetchFunds().then(setFunds).catch(() => setFunds([]))
        fetchAuditLog(8).then(setLog).catch(() => setLog([]))

        Promise.all(MODULES.map(async (module) => {
            let documents: Record<string, TrackedDocument> = {}
            try {
                documents = await fetchDocuments(module.key)
            } catch {
                documents = {}
            }
            const statuses = Object.values(documents).map((document_) => document_.status)
            return {
                key: module.key, label: module.label, total: statuses.length,
                review: statuses.filter((status) => status === "Under review").length,
                approved: statuses.filter((status) => ["Approved", "Published"].includes(status)).length,
            }
        })).then(setRows)
        // eslint-disable-next-line react-hooks/exhaustive-deps -- the module list changes only on sign-in
    }, [MODULES.map((module) => module.key).join()])

    const filtered = useMemo(() => {
        const needle = query.trim().toLowerCase()
        if (!needle) return funds
        return funds.filter((fund) =>
            [fund.fund_name, fund.share_class, fund.isin, fund.manco, fund.regime]
                .some((field) => String(field ?? "").toLowerCase().includes(needle)))
    }, [funds, query])

    const totalFilings = rows.reduce((sum, row) => sum + row.total, 0)
    const underReview = rows.reduce((sum, row) => sum + row.review, 0)
    const approved = rows.reduce((sum, row) => sum + row.approved, 0)
    const mancos = new Set(funds.map((fund) => fund.manco).filter(Boolean)).size

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="Dashboard"
                subtitle="Where your filings stand, in the modules your organisation subscribes to." />

            <KpiRow items={[
                ...(showFunds ? [{ label: "Funds / classes in your registry", value: String(funds.length),
                  hint: `${mancos} distinct ManCo(s)` }] : []),
                { label: "Filings generated", value: String(totalFilings), hint: "in your modules" },
                { label: "Under review (4 eyes)", value: String(underReview), hint: "control in progress" },
                { label: "Approved / published", value: String(approved), hint: "ready to file" },
            ]} />

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Your modules</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {MODULES.map((module) => {
                        const row = rows.find((candidate) => candidate.key === module.key)
                        return (
                            <Link key={module.key} to={`/${module.key}`}
                                className="rounded-lg border border-slate-200 bg-white p-4 transition
                                           hover:border-[#0A2647]">
                                <p className="text-sm font-semibold text-slate-900">{module.label}</p>
                                <p className="text-xs text-slate-500">{module.authority}</p>
                                <p className="mt-2 text-xs text-slate-600">
                                    {row ? `${row.total} filing(s) · ${row.review} under review` : "—"}
                                </p>
                            </Link>
                        )
                    })}
                </div>
            </section>

            <div className={showFunds ? "grid gap-6 lg:grid-cols-[1.4fr_1fr]" : "grid gap-6"}>
                {showFunds && <section className="flex flex-col gap-2">
                    <h2 className="text-sm font-semibold text-slate-900">Your fund registry</h2>
                    <input value={query} onChange={(event) => setQuery(event.target.value)}
                        placeholder="Search by fund, ISIN, share class or ManCo"
                        className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none
                                   focus:border-[#0A2647]" />
                    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide
                                              text-slate-500">
                                <tr>
                                    <th className="px-3 py-2">Fund</th>
                                    <th className="px-3 py-2">Class</th>
                                    <th className="px-3 py-2">ISIN</th>
                                    <th className="px-3 py-2">Regime</th>
                                    <th className="px-3 py-2">ManCo</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="px-3 py-3 text-sm text-slate-500">
                                            {funds.length === 0
                                                ? "The registry is empty — populate it from the PRIIPs KID ingestion step."
                                                : "No fund matches your search."}
                                        </td>
                                    </tr>
                                ) : filtered.map((fund) => (
                                    <tr key={fund.fund_id} className="border-t border-slate-100">
                                        <td className="px-3 py-2">{fund.fund_name}</td>
                                        <td className="px-3 py-2">{fund.share_class}</td>
                                        <td className="px-3 py-2 font-mono text-xs">{fund.isin}</td>
                                        <td className="px-3 py-2">{fund.regime}</td>
                                        <td className="px-3 py-2">{fund.manco}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>}

                <section className="flex flex-col gap-2">
                    <h2 className="text-sm font-semibold text-slate-900">Recent activity</h2>
                    {log.length === 0 ? (
                        <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm
                                      text-slate-500">
                            No action has been logged yet.
                        </p>
                    ) : log.map((entry, index) => (
                        <div key={index} className="rounded-md border border-slate-200 bg-white px-4 py-2">
                            <p className="text-xs text-slate-500">
                                {entry.timestamp.slice(0, 16).replace("T", " ")} — {entry.user}
                            </p>
                            <p className="text-sm font-semibold text-slate-900">{entry.action}</p>
                            <p className="text-xs text-slate-600">{entry.subject} — {entry.detail}</p>
                        </div>
                    ))}
                </section>
            </div>
        </section>
    )
}

export default Dashboard
