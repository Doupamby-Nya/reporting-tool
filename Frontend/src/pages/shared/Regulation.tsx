import { useEffect, useState } from "react"
import { fetchRegulations, regulationDownloadUrl } from "@api/reportingApi"
import PageTitle from "@components/PageTitle"
import { useModule } from "@hooks/useChain"
import type { RegulationDocument } from "src/types/reportingType"

/**
 * The legal and technical texts this module's rules and generation logic are
 * built against, with the bundled PDF shown in place.
 *
 * Some texts sit behind an anti-bot or JavaScript-rendered page on the
 * official source and could not be bundled as a local PDF; those carry a
 * link to the publisher instead of a preview, rather than a copy of unknown
 * provenance.
 */
const Regulation: React.FC = () => {
    const module = useModule()
    const [documents, setDocuments] = useState<RegulationDocument[]>([])
    const [selected, setSelected] = useState<number>(0)

    useEffect(() => {
        fetchRegulations(module.regulationKey)
            .then((found) => { setDocuments(found); setSelected(0) })
            .catch(() => setDocuments([]))
    }, [module.regulationKey])

    const document_ = documents[selected]

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow={module.title} title="Regulatory reference"
                subtitle="The legal and technical texts this module's rules and generation logic are built
                          against." />

            {documents.length === 0 ? (
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    No regulatory reference has been catalogued for this module yet.
                </p>
            ) : (
                <>
                    <section className="rounded-lg border border-slate-200 bg-white p-5">
                        <h2 className="text-sm font-semibold text-slate-900">Applicable texts</h2>
                        <ul className="mt-3 flex flex-col gap-3">
                            {documents.map((entry) => (
                                <li key={entry.index}>
                                    <button type="button" onClick={() => setSelected(entry.index)}
                                        className="text-left">
                                        <span className={[
                                            "text-sm font-semibold",
                                            entry.index === selected ? "text-[#0A2647]" : "text-slate-900",
                                        ].join(" ")}>
                                            {entry.title}
                                        </span>
                                        <span className="block text-xs text-slate-500">{entry.issuer}</span>
                                        <span className="block text-sm text-slate-600">{entry.description}</span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </section>

                    {document_ && (
                        <section className="flex flex-col gap-3">
                            <h2 className="text-sm font-semibold text-slate-900">{document_.title}</h2>
                            {document_.downloadable ? (
                                <>
                                    <a href={regulationDownloadUrl(module.regulationKey, document_.index, true)}
                                        className="w-fit rounded-md bg-[#0A2647] px-4 py-2 text-sm font-medium
                                                   text-white transition hover:bg-[#123A6B]">
                                        Download the PDF
                                    </a>
                                    <iframe title={document_.title}
                                        src={regulationDownloadUrl(module.regulationKey, document_.index)}
                                        className="h-[800px] w-full rounded-lg border border-slate-200" />
                                </>
                            ) : document_.url ? (
                                <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
                                    <p className="text-sm text-amber-800">
                                        This text sits behind an anti-bot or JavaScript-rendered page on the
                                        official source and could not be bundled locally. Open it from the
                                        publisher instead.
                                    </p>
                                    <a href={document_.url} target="_blank" rel="noreferrer"
                                        className="mt-2 inline-block text-sm font-medium text-[#0A2647] underline">
                                        Open on {document_.issuer}
                                    </a>
                                </div>
                            ) : (
                                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm
                                              text-slate-500">
                                    No document is bundled for this entry yet.
                                </p>
                            )}
                            <p className="text-xs text-slate-500">Source: {document_.issuer}</p>
                        </section>
                    )}
                </>
            )}
        </section>
    )
}

export default Regulation
