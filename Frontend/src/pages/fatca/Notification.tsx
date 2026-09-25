import { useState } from "react"
import { toast } from "react-toastify"

import { generateNotifications } from "@api/reportingApi"
import Notice from "@components/Notice"
import PageTitle from "@components/PageTitle"
import { useChain } from "@hooks/useChain"

const CATEGORIES = [
    { key: "individuals", label: "Individuals" },
    { key: "controlling", label: "Controlling Persons" },
    { key: "active", label: "Active NFE" },
    { key: "passive", label: "Passive NFE" },
] as const

/**
 * The data-protection notification letters owed to each reported account
 * holder, one per holder, produced from the filing itself.
 *
 * This is a legal obligation that sits beside the return rather than inside
 * it: the holders named in the XML are the ones entitled to be told they
 * were reported, which is why the letters are generated from the filing and
 * not from the workbook.
 */
const FatcaNotification: React.FC = () => {
    const { chain } = useChain("fatca")
    const [selected, setSelected] = useState<Record<string, boolean>>({
        individuals: true, controlling: true, active: true, passive: true,
    })
    const [uploaded, setUploaded] = useState<string | null>(null)
    const [busy, setBusy] = useState(false)
    const [result, setResult] = useState<{ letters: number; pdfs: number } | null>(null)

    // Either the filing this chain produced, or one the preparer brings in —
    // letters are often produced against a return filed in an earlier session.
    const xml = uploaded ?? chain.files[0]?.content ?? null

    const run = async () => {
        if (!xml) return
        setBusy(true)
        setResult(null)
        try {
            const { blob, letters, pdfs } = await generateNotifications(xml, selected)
            const url = URL.createObjectURL(blob)
            const anchor = document.createElement("a")
            anchor.href = url
            anchor.download = "fatca_crs_data_notifications.zip"
            anchor.click()
            URL.revokeObjectURL(url)
            setResult({ letters, pdfs })
            toast.success(`${letters} letter(s) generated.`)
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow="FATCA & CRS" title="Data notification"
                subtitle="The data-protection notification letters owed to each account holder named in
                          the filing." />

            <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-slate-900">1. The filing to notify from</h2>
                {chain.files[0] && !uploaded ? (
                    <p className="text-sm text-slate-700">
                        Using the return generated in this session:{" "}
                        <span className="font-mono text-xs">{chain.files[0].filename}</span>
                    </p>
                ) : (
                    <p className="text-sm text-slate-600">
                        {uploaded
                            ? "Using the filing you uploaded."
                            : "No filing in this session. Upload one produced earlier."}
                    </p>
                )}
                <label className="w-fit cursor-pointer rounded-md border border-slate-300 px-3 py-2
                                  text-sm text-slate-700 transition hover:border-[#0A2647]">
                    Upload a filing instead
                    <input type="file" accept=".xml" className="hidden"
                        onChange={async (event) => {
                            const file = event.target.files?.[0]
                            if (file) setUploaded(await file.text())
                        }} />
                </label>
            </section>

            <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                <h2 className="text-sm font-semibold text-slate-900">2. Categories to notify</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                    {CATEGORIES.map((category) => (
                        <label key={category.key} className="flex items-center gap-2 text-sm text-slate-700">
                            <input type="checkbox" checked={selected[category.key]}
                                onChange={(event) => setSelected((current) => ({
                                    ...current, [category.key]: event.target.checked,
                                }))} />
                            {category.label}
                        </label>
                    ))}
                </div>
                <button type="button" onClick={run} disabled={busy || !xml}
                    className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                               transition hover:bg-[#123A6B] disabled:opacity-40">
                    {busy ? "Writing the letters…" : "Generate notification letters"}
                </button>
                {!xml && (
                    <p className="text-xs text-slate-500">
                        Generate a filing at the XML generation step, or upload one above, first.
                    </p>
                )}
            </section>

            {result && (
                <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                    <p className="text-sm text-emerald-900">
                        {result.letters} letter(s) generated and downloaded as a ZIP.
                    </p>
                    {result.pdfs < result.letters && (
                        <p className="mt-1 text-xs text-emerald-800">
                            {result.pdfs} of {result.letters} were also converted to PDF. Conversion needs
                            a local MS Word install, so the rest are provided as .docx only.
                        </p>
                    )}
                </section>
            )}

            <Notice eyebrow="Before sending" title="Review each letter before it goes to an account holder">
                The wording and legal references are reused verbatim from the approved data-protection
                notification templates.
            </Notice>
        </section>
    )
}

export default FatcaNotification
