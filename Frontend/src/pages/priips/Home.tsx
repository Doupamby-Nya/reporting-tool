import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets PRIIPs KID apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Regulation (EU) 1286/2014 · Delegated Regulation (EU) 2017/653, as amended by (EU) 2021/2268" },
    { label: "Unit of filing", value: "One KID per fund / share class" },
    { label: "Input", value: "The fund registry — standardised Excel template, or the demo dataset" },
    { label: "Output", value: "The KID as a PDF, from one of the configured templates" },
]

const SUMMARY =
    "Key information documents for packaged retail investment products: the summary risk indicator, the costs and the four performance scenarios of the RTS, merged into a narrative template and rendered per fund and share class."

/** The PRIIPs KID home page: the landing page of /priips. */
const PriipsHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default PriipsHome
