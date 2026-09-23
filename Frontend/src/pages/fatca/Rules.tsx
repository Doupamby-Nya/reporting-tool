import PageTitle from "@components/PageTitle"
import DataPreview from "@components/DataPreview"
import KpiRow from "@components/KpiRow"
import { useChain } from "@hooks/useChain"
import type { FatcaClassification } from "src/types/reportingType"
import type { FatcaParameters } from "./Ingestion"

/**
 * What the classification engine decided, account by account.
 *
 * For FATCA and CRS the rules are not a field mapping but a decision: each
 * account is classified as an Active NFE, a Passive NFE, a Controlling
 * Person or an Individual, and that classification is what the return is
 * built from. It is shown in full here, before anything is generated,
 * because a misclassified account is not visible in the XML afterwards.
 */
const FatcaRules: React.FC = () => {
    const { chain } = useChain("fatca")
    const stored = chain.ingestion as {
        parameters?: FatcaParameters; classification?: FatcaClassification
    } | null
    const classification = stored?.classification

    if (!classification) {
        return (
            <section className="flex flex-col gap-6">
                <PageTitle title="FATCA & CRS — Rules Engine" />
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    Nothing has been classified yet. Upload a workbook at the ingestion step first.
                </p>
            </section>
        )
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="FATCA & CRS — Rules Engine"
                subtitle="How every account in the workbook was classified, and why — the decision the
                          return is built from." />

            <KpiRow items={Object.entries(classification.counts).map(([label, value]) => ({
                label: label.replace(/_/g, " "), value: String(value),
            }))} />

            {stored?.parameters && (
                <section className="rounded-lg border border-slate-200 bg-white p-4">
                    <h2 className="text-sm font-semibold text-slate-900">This filing</h2>
                    <p className="mt-1 text-sm text-slate-700">
                        {stored.parameters.crs_fatca} · {stored.parameters.report_type} ·{" "}
                        {stored.parameters.selection} · version{" "}
                        {stored.parameters.report_type === "Zero Report" ? "0" : stored.parameters.version}
                        {stored.parameters.filer_category && ` · ${stored.parameters.filer_category}`}
                    </p>
                </section>
            )}

            {classification.messages.length > 0 && (
                <section className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-slate-900">Classification notes</h2>
                    {classification.messages.map((message, index) => (
                        <p key={index} className="rounded-md border border-slate-200 bg-white px-3 py-2
                                                  text-sm text-slate-700">
                            {message}
                        </p>
                    ))}
                </section>
            )}

            {classification.warnings.length > 0 && (
                <section className="flex flex-col gap-1">
                    <h2 className="text-sm font-semibold text-slate-900">Warnings</h2>
                    {classification.warnings.map((message, index) => (
                        <p key={index} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2
                                                  text-sm text-amber-800">
                            {message}
                        </p>
                    ))}
                </section>
            )}

            <section className="flex flex-col gap-2">
                <h2 className="text-sm font-semibold text-slate-900">
                    Classified accounts — {classification.accounts.length}
                </h2>
                <DataPreview data={{ accounts: classification.accounts }} />
            </section>
        </section>
    )
}

export default FatcaRules
