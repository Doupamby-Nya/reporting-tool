import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets ESEF apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Commission Delegated Regulation (EU) 2019/815" },
    { label: "Frequency", value: "Annual" },
    { label: "Unit of filing", value: "One submission per reporting entity and financial year" },
    { label: "Output", value: "Inline XBRL report (XHTML), or the full report package (ZIP)" },
]

const SUMMARY =
    "Annual financial report line items (Commission Delegated Regulation (EU) 2019/815) — one submission per reporting entity and financial year."

/** The ESEF home page: the landing page of /esef. */
const EsefHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default EsefHome
