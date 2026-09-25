import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { fetchAuditLog, fetchDocuments } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import type { ModuleNav } from "@config/navigation"
import type { AuditEntry, TrackedDocument } from "src/types/reportingType"

export type ReportingFact = { label: string; value: string }

/**
 * The landing page of one reporting: what it is, how it is filed, where its
 * filings stand, and the way into its production chain.
 *
 * Each reporting declares its own Home page (pages/<reporting>/Home.tsx) with
 * the facts that are particular to it; this component only lays them out, so
 * the eight pages read alike without being copies of one another.
 */
const ReportingHome: React.FC<{ module: ModuleNav; summary: string; facts: ReportingFact[] }> = (
    { module, summary, facts },
) => {
    const [documents, setDocuments] = useState<TrackedDocument[]>([])
    const [log, setLog] = useState<AuditEntry[]>([])

    useEffect(() => {
        fetchDocuments(module.key)
            .then((found) => setDocuments(Object.values(found)))
            .catch(() => setDocuments([]))
        fetchAuditLog(5, module.key).then(setLog).catch(() => setLog([]))
    }, [module.key])

    const count = (...statuses: string[]) =>
        documents.filter((document_) => statuses.includes(document_.status)).length

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title={module.title} subtitle={summary} />

            <dl className="grid gap-3 sm:grid-cols-2">
                {facts.map((fact) => (
                    <div key={fact.label} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
                        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{fact.label}</dt>
                        <dd className="mt-0.5 text-sm text-slate-900">{fact.value}</dd>
                    </div>
                ))}
            </dl>

            <KpiRow items={[
                { label: "Filings generated", value: String(documents.length) },
                { label: "Under review (4 eyes)", value: String(count("Under review")) },
                { label: "Approved / published", value: String(count("Approved", "Published")) },
                { label: "Rejected", value: String(count("Rejected")) },
            ]} />

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Production chain</h2>
                <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {module.steps.map((step, index) => (
                        <li key={step.path}>
                            <Link to={`/${module.key}/${step.path}`}
                                className="flex h-full items-center gap-3 rounded-lg border border-slate-200 bg-white
                                           p-4 transition hover:border-[#0A2647]">
                                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full
                                                 bg-[#0A2647] text-xs font-semibold text-white">
                                    {index + 1}
                                </span>
                                <span className="text-sm font-medium text-slate-900">{step.label}</span>
                            </Link>
                        </li>
                    ))}
                </ol>
            </section>

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Recent activity</h2>
                {log.length === 0 ? (
                    <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                        Nothing has been done on this reporting yet.
                    </p>
                ) : log.map((entry, index) => (
                    <div key={index} className="rounded-md border border-slate-200 bg-white px-4 py-2">
                        <p className="text-xs text-slate-500">
                            {entry.timestamp.slice(0, 16).replace("T", " ")} · {entry.user}
                        </p>
                        <p className="text-sm text-slate-900">
                            <span className="font-semibold">{entry.action}</span> · {entry.subject}
                        </p>
                    </div>
                ))}
            </section>
        </section>
    )
}

export default ReportingHome
