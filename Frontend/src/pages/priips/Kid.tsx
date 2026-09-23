import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { buildKid, fetchFunds, fetchPriipsTemplates, recordGenerated, renderKidPdf } from "@api/reportingApi"
import PageTitle from "@components/PageTitle"
import { useCurrentUser } from "@hooks/useCurrentUser"
import type { Fund } from "src/types/reportingType"

type KidSection = { title?: string; heading?: string; body?: string; text?: string }
type Kid = {
    product_name: string
    isin: string
    generation_date: string
    template_name: string
    sections: KidSection[]
    [field: string]: unknown
}

/**
 * The KID itself: the calculated figures merged into a narrative template,
 * previewed here and exported as the PDF that is distributed.
 *
 * The PDF is rendered server-side rather than in the browser, because it is
 * the same renderer the platform would use unattended — a preview produced
 * by different code than the deliverable is worth very little.
 */
const PriipsKid: React.FC = () => {
    const { name: user } = useCurrentUser()
    const [funds, setFunds] = useState<Fund[]>([])
    const [fundId, setFundId] = useState("")
    const [templates, setTemplates] = useState<string[]>([])
    const [templateName, setTemplateName] = useState("standard")
    const [kid, setKid] = useState<Kid | null>(null)
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        fetchFunds().then((found) => {
            setFunds(found)
            if (found.length) setFundId(found[0].fund_id)
        }).catch((error: Error) => toast.error(error.message))

        fetchPriipsTemplates()
            .then((response) => {
                const available = (response as unknown as { available?: string[] }).available ?? []
                setTemplates(available)
                if (available.length && !available.includes("standard")) setTemplateName(available[0])
            })
            .catch(() => setTemplates([]))
    }, [])

    const fund = funds.find((candidate) => candidate.fund_id === fundId)

    const build = async () => {
        if (!fund) return
        setBusy(true)
        try {
            const built = await buildKid(fund, templateName)
            setKid(built as unknown as Kid)
            toast.success("KID assembled.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const exportPdf = async () => {
        if (!kid) return
        setBusy(true)
        try {
            const { blob, filename } = await renderKidPdf(kid)
            const url = URL.createObjectURL(blob)
            const anchor = document.createElement("a")
            anchor.href = url
            anchor.download = filename
            anchor.click()
            URL.revokeObjectURL(url)

            if (user) await recordGenerated("priips", filename, `KID — ${kid.product_name}`, user)
            toast.success("KID exported.")
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    if (funds.length === 0) {
        return (
            <section className="flex flex-col gap-6">
                <PageTitle title="PRIIPs KID — KID Generation" />
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    The registry is empty. Populate it at the ingestion step first.
                </p>
            </section>
        )
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="PRIIPs KID — KID Generation"
                subtitle="One key information document per fund and share class: preview it, then export
                          the PDF that is distributed." />

            {!user && (
                <p className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    Enter your name in the header — an exported KID is registered in the audit trail
                    against whoever prepared it.
                </p>
            )}

            <div className="flex flex-wrap items-end gap-3">
                <label className="flex min-w-72 flex-1 flex-col gap-1 text-sm">
                    <span className="font-medium text-slate-700">Share class</span>
                    <select value={fundId} onChange={(event) => setFundId(event.target.value)}
                        className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                   focus:border-[#0A2647]">
                        {funds.map((candidate) => (
                            <option key={candidate.fund_id} value={candidate.fund_id}>
                                {candidate.fund_name} — {candidate.share_class} ({candidate.isin})
                            </option>
                        ))}
                    </select>
                </label>
                <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium text-slate-700">Narrative template</span>
                    <select value={templateName} onChange={(event) => setTemplateName(event.target.value)}
                        className="rounded-md border border-slate-300 px-3 py-2 outline-none
                                   focus:border-[#0A2647]">
                        {(templates.length ? templates : ["standard"]).map((name) => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </select>
                </label>
                <button type="button" onClick={build} disabled={busy}
                    className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white transition
                               hover:bg-[#123A6B] disabled:opacity-50">
                    {busy ? "Working…" : "Assemble the KID"}
                </button>
                {kid && (
                    <button type="button" onClick={exportPdf} disabled={busy}
                        className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                                   text-[#0A2647] transition hover:bg-slate-100 disabled:opacity-50">
                        Export as PDF
                    </button>
                )}
            </div>

            {kid && (
                <article className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-8">
                    <header className="border-b border-slate-200 pb-3">
                        <h2 className="text-xl font-semibold text-slate-900">Key Information Document</h2>
                        <p className="text-sm text-slate-600">
                            {kid.product_name} — {kid.isin}
                        </p>
                        <p className="text-xs text-slate-500">
                            Generated {kid.generation_date} from the “{kid.template_name}” template.
                        </p>
                    </header>
                    {(kid.sections ?? []).map((section, index) => (
                        <section key={index} className="flex flex-col gap-1">
                            <h3 className="text-sm font-semibold text-slate-900">
                                {section.title ?? section.heading ?? `Section ${index + 1}`}
                            </h3>
                            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
                                {section.body ?? section.text ?? ""}
                            </p>
                        </section>
                    ))}
                </article>
            )}
        </section>
    )
}

export default PriipsKid
