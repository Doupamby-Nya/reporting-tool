import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets BCL statistical reports apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Authority", value: "Banque centrale du Luxembourg" },
    { label: "Reports", value: "S 1.3 and S 1.6 monthly · S 2.13 and S 2.20 quarterly · S 4.4 annual · TPTOBS monthly" },
    { label: "Checks", value: "BCL's compendiums of verification rules, then each report's own XSD" },
    { label: "Output", value: "One XML file per report, named after BCL's convention" },
]

const SUMMARY =
    "Banque centrale du Luxembourg statistical reporting — S 1.3, S 2.13, S 1.6, S 2.20, S 4.4 and TPTOBS Layout 3."

/** The BCL statistical reports home page: the landing page of /bcl. */
const BclHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default BclHome
