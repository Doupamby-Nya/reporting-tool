import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets SAQ apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Circular CSSF 21/790" },
    { label: "Frequency", value: "Annual, per financial year" },
    { label: "Unit of filing", value: "One submission per UCI and financial year" },
    { label: "Output", value: "Summary workbook — the questionnaire itself is filed by hand on eDesk" },
]

const SUMMARY =
    "Self-assessment questionnaire tracker (Circular CSSF 21/790) — one submission per UCI and financial year, ahead of manual filing on CSSF's eDesk portal."

/** The SAQ home page: the landing page of /saq. */
const SaqHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default SaqHome
