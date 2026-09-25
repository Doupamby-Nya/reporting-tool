import { useState } from "react"
import { toast } from "react-toastify"

import { generateAifmd, recordGenerated } from "@api/reportingApi"
import FileDownload from "@components/FileDownload"
import PageTitle from "@components/PageTitle"
import ValidationReport from "@components/ValidationReport"
import { useChain } from "@hooks/useChain"
import { setGeneration } from "@store/chainSlice"

const MODULE_KEY = "aifmd"

/**
 * Builds the two files a filing is made of: DATMAN for the manager, DATAIF
 * for the fund. Both are validated against ESMA's own XSD schemas, and a
 * file must carry exactly one reporting record, before either is offered.
 */
const AifmdGeneration: React.FC = () => {
    const { chain, dispatch } = useChain(MODULE_KEY)
    const [busy, setBusy] = useState(false)
    const [generated, setGenerated] = useState<boolean | null>(null)

    const run = async () => {
        if (!chain.ingestion) {
            toast.error("Save a submission at the ingestion step first.")
            return
        }
        setBusy(true)
        try {
            const outcome = await generateAifmd(chain.ingestion)
            setGenerated(outcome.generated)
            dispatch(setGeneration({
                module: MODULE_KEY, files: outcome.files, validation: outcome.validation,
            }))
            if (outcome.generated) {
                for (const file of outcome.files) {
                    await recordGenerated(MODULE_KEY, file.filename, file.label)
                }
                toast.success("DATMAN and DATAIF generated.")
            } else {
                toast.error("The filing was refused; see the controls below.")
            }
        } catch (error) {
            toast.error((error as Error).message)
        } finally {
            setBusy(false)
        }
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow="AIFMD Annex IV" title="XML generation"
                subtitle="The AIFM-level (DATMAN) and AIF-level (DATAIF) files, validated against ESMA's
                          own XSD schemas before either can be downloaded." />


            <button type="button" onClick={run} disabled={busy}
                className="w-fit rounded-md bg-[#0A2647] px-5 py-2 text-sm font-medium text-white
                           transition hover:bg-[#123A6B] disabled:opacity-50">
                {busy ? "Working…" : "Generate both files"}
            </button>

            {chain.validation && generated !== null && (
                <section className="flex flex-col gap-3">
                    <h2 className="text-sm font-semibold text-slate-900">Validation</h2>
                    <ValidationReport validation={chain.validation} />
                </section>
            )}

            {chain.files.map((file) => <FileDownload key={file.key} file={file} />)}
        </section>
    )
}

export default AifmdGeneration
