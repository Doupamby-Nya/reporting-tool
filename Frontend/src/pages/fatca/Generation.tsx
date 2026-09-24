import { useState } from "react"
import { toast } from "react-toastify"

import { generateFatca, recordGenerated } from "@api/reportingApi"
import PageTitle from "@components/PageTitle"
import { useChain } from "@hooks/useChain"
import { setGeneration } from "@store/chainSlice"
import { takeFile } from "@store/fileVault"
import type { FatcaClassification, GeneratedFile } from "src/types/reportingType"
import type { FatcaParameters } from "./Ingestion"

/**
 * Builds the AEOI return from the workbook classified at the ingestion step.
 *
 * The workbook has to be sent again — the API is stateless — so it is held
 * in this tab's memory between the two steps. A reload empties that, which
 * is why the step says so rather than failing obscurely.
 */
const FatcaGeneration: React.FC = () => {
    const { chain, dispatch } = useChain("fatca")
    const stored = chain.ingestion as {
        parameters?: FatcaParameters; classification?: FatcaClassification
    } | null
    const [busy, setBusy] = useState(false)
    const [errors, setErrors] = useState<string[]>([])

    const run = async () => {
        const file = takeFile("fatca")
        const parameters = stored?.parameters
        if (!file || !parameters) {
            toast.error("Upload the workbook again at the ingestion step — this tab no longer holds it.")
            return
        }
        setBusy(true)
        setErrors([])
        try {
            const produced = await generateFatca(
                file,
                { ...parameters, version: parameters.report_type === "Zero Report" ? "0" : parameters.version },
                parameters.preparer,
            )
            setErrors(produced.errors ?? [])

            const files: GeneratedFile[] = produced.files.map((output, index) => ({
                key: `fatca-${index}`, label: output.label || "AEOI return",
                filename: output.filename, content: output.content ?? "",
                schema_validation: { available: false, valid: true, errors: [] },
            }))
            dispatch(setGeneration({ module: "fatca", files }))

            if (files.length === 0) {
                toast.error("The return was not produced; see the problems below.")
            } else {
                await recordGenerated("fatca", files[0].filename, files[0].label)
                toast.success("Return generated.")
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const download = (file: GeneratedFile) => {
        const url = URL.createObjectURL(new Blob([file.content], { type: "application/xml" }))
        const anchor = document.createElement("a")
        anchor.href = url
        anchor.download = file.filename
        anchor.click()
        URL.revokeObjectURL(url)
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="FATCA & CRS — XML Generation"
                subtitle="Builds the AEOI return from the classified workbook, under the parameters set
                          at the ingestion step." />

            {!stored?.parameters ? (
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    Set the reporting parameters and upload a workbook at the ingestion step first.
                </p>
            ) : (
                <>
                    <section className="rounded-lg border border-slate-200 bg-white p-4">
                        <h2 className="text-sm font-semibold text-slate-900">This filing</h2>
                        <p className="mt-1 text-sm text-slate-700">
                            {stored.parameters.crs_fatca} · {stored.parameters.report_type} ·{" "}
                            {stored.parameters.selection} · version{" "}
                            {stored.parameters.report_type === "Zero Report" ? "0" : stored.parameters.version}
                            {stored.parameters.filer_category && ` · ${stored.parameters.filer_category}`}
                        </p>
                        <p className="text-xs text-slate-500">Preparer: {stored.parameters.preparer || "—"}</p>
                    </section>

                    <button type="button" onClick={run} disabled={busy}
                        className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                                   transition hover:bg-[#123A6B] disabled:opacity-50">
                        {busy ? "Working…" : "Generate the return"}
                    </button>
                </>
            )}

            {errors.length > 0 && (
                <section className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-slate-900">Problems</h2>
                    {errors.map((message, index) => (
                        <p key={index} className="rounded-md border border-red-200 bg-red-50 px-3 py-2
                                                  text-sm text-red-800">
                            {message}
                        </p>
                    ))}
                </section>
            )}

            {chain.files.map((file) => (
                <section key={file.key}
                    className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h2 className="text-sm font-semibold text-slate-900">{file.label}</h2>
                            <p className="font-mono text-xs text-slate-500">{file.filename}</p>
                        </div>
                        <button type="button" onClick={() => download(file)}
                            className="rounded-md bg-[#0A2647] px-4 py-2 text-sm font-medium text-white
                                       transition hover:bg-[#123A6B]">
                            Download
                        </button>
                    </div>
                    <pre className="max-h-96 overflow-auto rounded-md border border-slate-200 bg-slate-50
                                    p-3 font-mono text-xs text-slate-700">
                        {file.content.slice(0, 20000)}
                    </pre>
                </section>
            ))}
        </section>
    )
}

export default FatcaGeneration
