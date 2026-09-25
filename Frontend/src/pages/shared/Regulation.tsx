import { useEffect, useState } from "react"
import { fetchRegulations, regulationDownloadUrl } from "@api/reportingApi"
import DocumentViewer from "@components/DocumentViewer"
import type { ViewerDocument } from "@components/DocumentViewer"
import PageTitle from "@components/PageTitle"
import { useModule } from "@hooks/useChain"
import type { RegulationDocument } from "src/types/reportingType"

/**
 * The legal and technical texts this module's rules and generation logic are
 * built against, each shown in place.
 *
 * Some texts sit behind an anti-bot or JavaScript-rendered page on the
 * official source and could not be bundled as a local PDF; those point to the
 * publisher instead of offering a copy of unknown provenance.
 */
const Regulation: React.FC = () => {
    const module = useModule()
    const [documents, setDocuments] = useState<RegulationDocument[] | null>(null)

    useEffect(() => {
        fetchRegulations(module.regulationKey)
            .then(setDocuments)
            .catch(() => setDocuments([]))
    }, [module.regulationKey])

    const shelf: ViewerDocument[] = (documents ?? []).map((doc) => ({
        id: String(doc.index),
        title: doc.title,
        caption: doc.issuer,
        description: doc.description,
        format: doc.downloadable ? "pdf" : doc.url ? "external" : "missing",
        filename: doc.downloadable ? doc.filename : undefined,
        viewUrl: doc.downloadable ? regulationDownloadUrl(module.regulationKey, doc.index) : undefined,
        downloadUrl: doc.downloadable ? regulationDownloadUrl(module.regulationKey, doc.index, true) : undefined,
        externalUrl: doc.url ?? undefined,
        source: doc.issuer,
    }))

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow={module.title} title="Regulatory reference"
                subtitle="The legal and technical texts this module's rules and generation logic are built
                          against." />

            {documents === null ? null : shelf.length === 0 ? (
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    No regulatory reference has been catalogued for this module yet.
                </p>
            ) : (
                <DocumentViewer documents={shelf} label="Applicable texts" />
            )}
        </section>
    )
}

export default Regulation
