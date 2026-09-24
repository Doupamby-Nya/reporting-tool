import { useState } from "react"
import { toast } from "react-toastify"

import { generateEsefPackage, generateFiling, recordGenerated } from "@api/reportingApi"
import PageTitle from "@components/PageTitle"
import { useChain, useModule } from "@hooks/useChain"
import { setGeneration } from "@store/chainSlice"
import type { FilingOutput, GeneratedFile } from "src/types/reportingType"

/** Turns the API's output into a download the browser can hand over.
 *  A text filing arrives as a string, a workbook or ZIP as base64 — the
 *  blob is built from whichever one is filled. */
function download(output: FilingOutput) {
    const type = output.media_type || "application/octet-stream"
    let blob: Blob
    if (output.content_base64) {
        const binary = atob(output.content_base64)
        const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
        blob = new Blob([bytes], { type })
    } else {
        blob = new Blob([output.content ?? ""], { type })
    }
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = output.filename
    anchor.click()
    URL.revokeObjectURL(url)
}

/**
 * The generation step of the workbook-driven regimes.
 *
 * It builds from what ingestion parsed, so a chain that has not been started
 * cannot produce a filing — which is deliberate: the alternative is a filing
 * built from an empty submission that looks valid and says nothing.
 */
const FilingGeneration: React.FC = () => {
    const module = useModule()
    const { chain, dispatch } = useChain(module.key)
    const [busy, setBusy] = useState(false)
    const [output, setOutput] = useState<FilingOutput | null>(null)
    const [refusal, setRefusal] = useState<string[]>([])

    const submission = () => {
        // The parser returns its problems alongside the data; the generator
        // takes the data only.
        const parsed = { ...(chain.ingestion as Record<string, unknown> ?? {}) }
        delete parsed.errors
        return parsed
    }

    const run = async (asPackage = false) => {
        if (!chain.ingestion) return toast.error("Ingest a workbook first. There is nothing to generate from yet.")
        setBusy(true)
        try {
            const answer = asPackage
                ? await generateEsefPackage(submission())
                : await generateFiling(module.key, submission())
            if (!answer.generated) {
                // The engine's own checks refused the submission, as the
                // Streamlit generation step did: nothing is produced.
                setOutput(null)
                setRefusal(answer.errors)
                toast.error(`The ${module.label} filing was not generated: ${answer.errors.length} issue(s) to fix.`)
                return
            }
            const produced: FilingOutput = {
                filename: answer.filename, label: answer.label, media_type: answer.media_type,
                content: answer.content, content_base64: answer.content_base64,
            }
            setRefusal([])
            setOutput(produced)

            // The preview and the audit trail both work off the chain, so
            // the produced document is put there as the module's one file.
            const file: GeneratedFile = {
                key: module.key, label: produced.label, filename: produced.filename,
                content: produced.content ?? "",
                schema_validation: { available: false, valid: true, errors: [] },
            }
            dispatch(setGeneration({ module: module.key, files: [file] }))

            await recordGenerated(module.key, produced.filename, produced.label)
            toast.success(`${produced.label} generated.`)
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const step = module.steps.find((candidate) => candidate.path === "generation")

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow={module.title} title={step?.label ?? "Generation"}
                subtitle="Builds the filing from the submission read at the ingestion step." />


            <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => run(false)} disabled={busy}
                    className="rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white transition
                               hover:bg-[#123A6B] disabled:opacity-50">
                    {busy ? "Working…" : `Generate the ${module.label} filing`}
                </button>
                {module.key === "esef" && (
                    <button type="button" onClick={() => run(true)} disabled={busy}
                        className="rounded-md border border-[#0A2647] px-4 py-2 text-sm font-medium
                                   text-[#0A2647] transition hover:bg-slate-100 disabled:opacity-50">
                        Generate the ESEF report package (ZIP)
                    </button>
                )}
            </div>

            {refusal.length > 0 && (
                <section className="flex flex-col gap-2 rounded-lg border border-red-200 bg-red-50 p-5">
                    <h2 className="text-sm font-semibold text-red-800">Validation issues</h2>
                    <ul className="list-disc pl-5 text-sm text-red-700">
                        {refusal.map((message) => <li key={message}>{message}</li>)}
                    </ul>
                </section>
            )}

            {output && (
                <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h2 className="text-sm font-semibold text-slate-900">{output.label}</h2>
                            <p className="font-mono text-xs text-slate-500">{output.filename}</p>
                        </div>
                        <button type="button" onClick={() => download(output)}
                            className="rounded-md bg-[#0A2647] px-4 py-2 text-sm font-medium text-white
                                       transition hover:bg-[#123A6B]">
                            Download
                        </button>
                    </div>
                    {output.content && (
                        <pre className="max-h-96 overflow-auto rounded-md border border-slate-200 bg-slate-50
                                        p-3 font-mono text-xs text-slate-700">
                            {output.content.slice(0, 20000)}
                        </pre>
                    )}
                </section>
            )}
        </section>
    )
}

export default FilingGeneration
