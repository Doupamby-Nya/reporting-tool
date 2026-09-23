import { useState } from "react"
import { toast } from "react-toastify"

import PageTitle from "@components/PageTitle"
import { useChain, useModule } from "@hooks/useChain"
import { commitEdit, selectFile, setEdited } from "@store/chainSlice"

/**
 * Reads, and if necessary corrects, the document the generation step
 * produced, before it goes for review.
 *
 * The edit stays a local draft until it is explicitly saved: the controls
 * screen and the audit trail work off the chain's file content, so a
 * half-finished correction must never silently become the official report.
 */
const XmlPreview: React.FC = () => {
    const module = useModule()
    const { chain, dispatch } = useChain(module.key)
    const [wellFormed, setWellFormed] = useState<string | null>(null)

    const step = module.steps.find((candidate) => candidate.path === "preview")
    const file = chain.files.find((candidate) => candidate.key === chain.editedKey) ?? chain.files[0]
    const changed = file !== undefined && chain.edited !== null && chain.edited !== file.content

    const check = () => {
        if (chain.edited === null) return
        // The browser's own parser is the cheap, correct check for
        // well-formedness. It is not schema validation — that belongs to the
        // generator, which validates against the regulator's XSD.
        const document_ = new DOMParser().parseFromString(chain.edited, "application/xml")
        const failure = document_.querySelector("parsererror")
        if (failure) {
            setWellFormed(failure.textContent?.trim() || "The document is not well-formed XML.")
            toast.error("This document is not well-formed.")
        } else {
            setWellFormed(null)
            toast.success("The document is well-formed.")
        }
    }

    const save = () => {
        dispatch(commitEdit({ module: module.key }))
        toast.success("The edited document is now this filing's content.")
    }

    if (!file) {
        return (
            <section className="flex flex-col gap-6">
                <PageTitle title={`${module.title} — ${step?.label ?? "Preview"}`} />
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    Nothing has been generated yet. Produce a filing at the previous step first.
                </p>
            </section>
        )
    }

    return (
        <section className="flex flex-col gap-4">
            <PageTitle title={`${module.title} — ${step?.label ?? "Preview"}`}
                subtitle="Read the generated document, and correct it here if it needs it. An edit only
                          replaces the filing once you save it." />

            {chain.files.length > 1 && (
                <div className="flex flex-wrap gap-2">
                    {chain.files.map((candidate) => (
                        <button key={candidate.key} type="button"
                            onClick={() => dispatch(selectFile({ module: module.key, key: candidate.key }))}
                            className={[
                                "rounded-md border px-3 py-1.5 text-sm font-medium transition",
                                candidate.key === chain.editedKey
                                    ? "border-[#0A2647] bg-[#0A2647] text-white"
                                    : "border-slate-300 bg-white text-slate-700 hover:border-[#0A2647]",
                            ].join(" ")}>
                            {candidate.label}
                        </button>
                    ))}
                </div>
            )}

            <p className="font-mono text-xs text-slate-500">{file.filename}</p>

            <textarea value={chain.edited ?? ""} spellCheck={false} rows={26}
                onChange={(event) => dispatch(setEdited({ module: module.key, content: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 bg-white p-3 font-mono text-xs
                           outline-none focus:border-[#0A2647]" />

            <div className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={check}
                    className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium text-[#0A2647]
                               transition hover:bg-slate-100">
                    Check it is well-formed
                </button>
                <button type="button" onClick={save} disabled={!changed}
                    className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white transition
                               hover:bg-[#123A6B] disabled:opacity-40">
                    Save the edited document
                </button>
                {changed && <span className="text-xs text-amber-700">Unsaved changes.</span>}
            </div>

            {wellFormed && (
                <pre className="overflow-auto rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
                    {wellFormed}
                </pre>
            )}
        </section>
    )
}

export default XmlPreview
