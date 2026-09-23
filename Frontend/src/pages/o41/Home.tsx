import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets O 4.1 apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Circular IML 97/136 — Table O 4.1" },
    { label: "Frequency", value: "Annual" },
    { label: "Unit of filing", value: "One submission per UCI / sub-fund and financial year" },
    { label: "Output", value: "EDIFACT message (not XML)" },
]

const SUMMARY =
    "Annual financial information (Table O 4.1, Circular IML 97/136) — one submission per UCI / sub-fund and financial year."

/** The O 4.1 home page: the landing page of /o41. */
const O41Home: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default O41Home
