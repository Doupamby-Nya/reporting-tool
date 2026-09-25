import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets FATCA & CRS apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Authority", value: "Administration des contributions directes (ACD), Luxembourg" },
    { label: "Unit of filing", value: "One return per run: CRS or FATCA, data report or zero report" },
    { label: "Input", value: "The data report workbook: CPS, Individual and Active tabs" },
    { label: "Output", value: "AEOI XML return, and the notification letters (Word / PDF)" },
]

const SUMMARY =
    "Automatic exchange of information with the Luxembourg tax authority: the FATCA and CRS returns built from the CPS / Active / Individual workbook, and the GDPR notification letters owed to each reported account holder."

/** The FATCA & CRS home page: the landing page of /fatca. */
const FatcaHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default FatcaHome
