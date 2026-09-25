import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { fetchFilingRules } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import Notice from "@components/Notice"
import PageTitle from "@components/PageTitle"
import { splitCode } from "@components/splitCode"
import { useChain, useModule } from "@hooks/useChain"
import type { RulesCatalogue as Catalogue } from "src/types/reportingType"

/**
 * The rules engine of U 1.1, O 4.1, ESEF and SAQ.
 *
 * For these regimes the rules are a mapping: every field the platform
 * captures, the exact regulator element it is tagged to, and whether this
 * submission fills it. The catalogue is built by the API from the same
 * constants the generator uses, so the screen cannot describe a mapping the
 * generator does not apply. O 4.1 adds real arithmetic on top — the Annexe B
 * cross-checks, evaluated against the submission.
 */
const RulesCatalogue: React.FC = () => {
    const module = useModule()
    const { chain } = useChain(module.key)
    const [catalogue, setCatalogue] = useState<Catalogue | null>(null)

    useEffect(() => {
        fetchFilingRules(module.key, chain.ingestion ?? {})
            .then(setCatalogue)
            .catch((error: Error) => toast.error(error.message))
    }, [module.key, chain.ingestion])

    if (!catalogue) {
        return (
            <section className="flex flex-col gap-6">
                <PageTitle eyebrow={module.title} title="Rules engine" />
                <p className="text-sm text-slate-500">Loading the mapping catalogue…</p>
            </section>
        )
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow={module.title} title={catalogue.title} subtitle={catalogue.description} />

            {!chain.ingestion && (
                <Notice tone="info" eyebrow="Coverage" title="Nothing has been ingested yet">
                    The coverage below stays empty until a submission is ingested. The mapping itself is
                    the regime's own and does not depend on a submission.
                </Notice>
            )}

            <KpiRow items={catalogue.coverage.map((item) => ({
                label: item.label, value: item.value, hint: item.hint,
            }))} />

            {catalogue.errors.length > 0 && (
                <section className="flex flex-col gap-2">
                    <h2 className="text-sm font-semibold text-slate-900">Cross-check results</h2>
                    {catalogue.errors.map((message, index) => (
                        <p key={index} className="rounded-md border border-red-200 bg-red-50 px-3 py-2
                                                  text-sm text-red-800">
                            {message}
                        </p>
                    ))}
                </section>
            )}
            {catalogue.errors.length === 0 && Boolean(chain.ingestion) && (
                <p className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm
                              text-emerald-800">
                    Every cross-check this regime defines is consistent for the current submission.
                </p>
            )}

            {catalogue.tables.map((table) => {
                const hasCodes = table.rows.some((row) => splitCode(row.label).code)
                return (
                <section key={table.title} className="flex flex-col gap-2">
                    <h2 className="text-sm font-semibold text-slate-900">{table.title}</h2>
                    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                        <table className="w-full text-sm">
                            <caption className="sr-only">{table.title}</caption>
                            <thead className="bg-slate-50 text-left text-xs text-slate-500">
                                <tr>
                                    {hasCodes && <th scope="col" className="w-20 px-3 py-2 font-semibold">Code</th>}
                                    <th scope="col" className="px-3 py-2 font-semibold">Description</th>
                                    <th scope="col" className="px-3 py-2 font-semibold">{table.column}</th>
                                    <th scope="col" className="w-28 px-3 py-2 text-center font-semibold">In submission</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table.rows.map((row) => {
                                    const { code, text } = splitCode(row.label)
                                    return (
                                        <tr key={row.key} className="border-t border-slate-100">
                                            {hasCodes && <td className="px-3 py-2 align-top font-mono text-xs text-slate-500">{code}</td>}
                                            <td className="px-3 py-2 align-top text-slate-700">{text}</td>
                                            <td className="px-3 py-2 align-top font-mono text-xs text-slate-600">{row.path}</td>
                                            <td className="px-3 py-2 text-center align-top">
                                                {row.filled
                                                    ? <span className="text-emerald-600" aria-label="Provided">✓</span>
                                                    : <span className="sr-only">Not provided</span>}
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                    {table.note && <p className="text-xs text-slate-500">{table.note}</p>}
                </section>
                )
            })}

            <section className="rounded-lg border border-slate-200 bg-white p-4">
                <h2 className="text-sm font-semibold text-slate-900">About this mapping</h2>
                <p className="mt-1 text-sm text-slate-600">{catalogue.note}</p>
            </section>
        </section>
    )
}

export default RulesCatalogue
