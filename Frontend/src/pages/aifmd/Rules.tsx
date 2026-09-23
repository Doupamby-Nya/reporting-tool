import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { fetchAifmdMetadata, validateAifmd } from "@api/reportingApi"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import { setValidation } from "@store/chainSlice"

const MODULE_KEY = "aifmd"

/**
 * The CSSF controls of the Technical Guidance, run against the submission,
 * plus the structural rule that trips most filings: the fixed-cardinality
 * blocks.
 *
 * ESMA declares those blocks with an exact number of occurrences. They are
 * always sent in full, with the unused ranks padded by the "nothing to
 * report" code of that block — a filing that omits them is rejected by the
 * schema, which is why they are shown here rather than left implicit.
 */
const AifmdRules: React.FC = () => {
    const { chain, dispatch } = useChain(MODULE_KEY)
    const [metadata, setMetadata] = useState<Record<string, unknown> | null>(null)
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        fetchAifmdMetadata().then(setMetadata).catch((error: Error) => toast.error(error.message))
    }, [])

    const run = async () => {
        if (!chain.ingestion) {
            toast.error("Save a submission at the ingestion step first.")
            return
        }
        setBusy(true)
        try {
            const outcome = await validateAifmd(chain.ingestion)
            dispatch(setValidation({ module: MODULE_KEY, validation: outcome }))
            if (outcome.valid) toast.success("Every implemented CSSF control passes.")
            else toast.error(`${outcome.errors.length} control(s) would reject this filing.`)
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const cardinalities = (metadata?.fixed_cardinalities ?? {}) as Record<string, number>

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="AIFMD Annex IV — Rules Engine"
                subtitle="The CSSF controls of the Technical Guidance, run against the submission saved
                          at the ingestion step." />

            <button type="button" onClick={run} disabled={busy}
                className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                           transition hover:bg-[#123A6B] disabled:opacity-50">
                {busy ? "Running…" : "Run the CSSF controls"}
            </button>

            {chain.validation && <ValidationReport validation={chain.validation} />}

            {Object.keys(cardinalities).length > 0 && (
                <section className="rounded-lg border border-slate-200 bg-white p-5">
                    <h2 className="text-sm font-semibold text-slate-900">Fixed-cardinality blocks</h2>
                    <p className="mt-1 text-sm text-slate-600">
                        ESMA declares these blocks with an exact number of occurrences. They are always
                        sent in full, with the unused ranks padded by the &quot;nothing to report&quot;
                        code of that block — a filing that omits them is rejected by the schema.
                    </p>
                    <ul className="mt-3 grid gap-x-8 gap-y-1 text-sm text-slate-700 sm:grid-cols-2">
                        {Object.entries(cardinalities).map(([name, count]) => (
                            <li key={name} className="flex justify-between border-b border-slate-100 py-1">
                                <span className="font-mono text-xs">{name}</span>
                                <span className="font-semibold">{count}</span>
                            </li>
                        ))}
                    </ul>
                </section>
            )}
        </section>
    )
}

export default AifmdRules
