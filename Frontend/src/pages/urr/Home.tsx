import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets U 1.1 apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Circular CSSF 15/627" },
    { label: "Frequency", value: "Monthly, within 10 calendar days of month-end" },
    { label: "Unit of filing", value: "One report per UCI / sub-fund" },
    { label: "Output", value: "U 1.1 XML, filed via eDesk" },
]

const SUMMARY =
    "Monthly financial reporting on Luxembourg UCIs under Circular CSSF 15/627. One report per sub-fund, filed within 10 calendar days of month-end."

/** The U 1.1 home page: the landing page of /urr. */
const UrrHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default UrrHome
