import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import {
    addFunds, fetchFunds, fundTemplateUrl, loadDemoFunds, parseFundWorkbook, removeFund, resetFunds,
} from "@api/reportingApi"
import DraftsPanel from "@components/DraftsPanel"
import IngestionPanel, { FORM_ANCHOR } from "@components/IngestionPanel"
import PageTitle from "@components/PageTitle"
import { useDrafts } from "@hooks/useDrafts"
import type { Fund } from "src/types/reportingType"

/**
 * The registry of funds and share classes under mandate.
 *
 * A workbook is read before it is committed: the rows it would add and the
 * problems it carries are both shown, and only then does the preparer accept
 * them. That is deliberate — an ingestion that silently half-succeeds is the
 * hardest kind of error to find later, because the registry looks populated.
 */
const PriipsIngestion: React.FC = () => {
    const [funds, setFunds] = useState<Fund[]>([])
    const [staged, setStaged] = useState<Fund[]>([])
    const [errors, setErrors] = useState<string[]>([])
    const [busy, setBusy] = useState(false)
    const [formOpen, setFormOpen] = useState(true)
    const drafts = useDrafts<Fund[]>("priips", setStaged, () => setFormOpen(true))

    useEffect(() => {
        fetchFunds().then(setFunds).catch((error: Error) => toast.error(error.message))
    }, [])

    const read = async (file: File) => {
        setBusy(true)
        try {
            const { funds: parsed, errors: problems } = await parseFundWorkbook(file)
            setStaged(parsed)
            setErrors(problems)
            if (parsed.length) toast.success(`${parsed.length} row(s) read and ready to add.`)
            else toast.error("No usable row was found in this workbook.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const commit = async () => {
        try {
            setFunds(await addFunds(staged))
            setStaged([])
            setErrors([])
            toast.success("The registry has been updated.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const demo = async () => {
        try {
            setFunds(await loadDemoFunds())
            toast.success("Demo dataset loaded.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const empty = async () => {
        try {
            setFunds(await resetFunds())
            toast.success("The registry is now empty.")
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const drop = async (fundId: string) => {
        try {
            setFunds(await removeFund(fundId))
        } catch (error) {
            toast.error((error as Error).message)
        }
    }

    const table = (rows: Fund[], onRemove?: (fundId: string) => void) => (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                        <th className="px-3 py-2">Identifier</th>
                        <th className="px-3 py-2">Fund</th>
                        <th className="px-3 py-2">Class</th>
                        <th className="px-3 py-2">ISIN</th>
                        <th className="px-3 py-2">Regime</th>
                        <th className="px-3 py-2">ManCo</th>
                        {onRemove && <th className="px-3 py-2" />}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((fund) => (
                        <tr key={fund.fund_id} className="border-t border-slate-100">
                            <td className="px-3 py-2 font-mono text-xs">{fund.fund_id}</td>
                            <td className="px-3 py-2">{fund.fund_name}</td>
                            <td className="px-3 py-2">{fund.share_class}</td>
                            <td className="px-3 py-2 font-mono text-xs">{fund.isin}</td>
                            <td className="px-3 py-2">{fund.regime}</td>
                            <td className="px-3 py-2">{fund.manco}</td>
                            {onRemove && (
                                <td className="px-3 py-2 text-right">
                                    <button type="button" onClick={() => onRemove(fund.fund_id)}
                                        className="text-xs text-red-700 underline">Remove</button>
                                </td>
                            )}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="PRIIPs KID — Ingestion"
                subtitle="A standardised workbook, one row per fund and share class. This registry is
                          what the calculation engine and the KID generation step work from." />

            <IngestionPanel regime="PRIIPs KID" busy={busy} actions={[
                { label: "Download template", href: fundTemplateUrl(),
                  hint: "one row per fund and share class" },
                { label: "Import a filled-in workbook", accept: ".xlsx", onFile: read, primary: true,
                  hint: "read and shown before anything is added to the registry" },
                { label: "Load the demo dataset", onClick: demo,
                  hint: "invented funds, to walk the chain end to end" },
                { label: "Saved drafts", onClick: () => drafts.setPanelOpen(true),
                  hint: "re-open a set of rows staged earlier" },
                { label: "Empty the registry", onClick: empty },
            ]}
                formOpen={formOpen} onToggleForm={() => setFormOpen(!formOpen)} />

            {drafts.panelOpen && (
                <DraftsPanel moduleKey="priips" moduleLabel="PRIIPs KID"
                    onOpen={drafts.open} onClose={() => drafts.setPanelOpen(false)} />
            )}

            {errors.length > 0 && (
                <section className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-slate-900">
                        {errors.length} row(s) were rejected
                    </h2>
                    {errors.slice(0, 20).map((message, index) => (
                        <p key={index} className="rounded-md border border-red-200 bg-red-50 px-3 py-2
                                                  text-sm text-red-800">
                            {message}
                        </p>
                    ))}
                    {errors.length > 20 && (
                        <p className="text-xs text-slate-500">…and {errors.length - 20} more.</p>
                    )}
                </section>
            )}

            {staged.length > 0 && (
                <section className="flex flex-col gap-2">
                    <h2 className="text-sm font-semibold text-slate-900">
                        Ready to add — {staged.length} row(s)
                    </h2>
                    {table(staged)}
                    <button type="button" onClick={commit}
                        className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                   transition hover:bg-[#123A6B]">
                        Add these to the registry
                    </button>
                </section>
            )}

            {formOpen && (
            <section id={FORM_ANCHOR} className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">
                    Registry — {funds.length} share class(es)
                </h2>
                {funds.length === 0 ? (
                    <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                        Nothing under mandate yet. Upload a workbook, or load the demo dataset to walk the
                        chain end to end — its funds, ISINs and figures are invented.
                    </p>
                ) : table(funds, drop)}
            </section>
            )}
        </section>
    )
}

export default PriipsIngestion
