import ReportingHome, { type ReportingFact } from "@components/ReportingHome"
import { useModule } from "@hooks/useChain"

/** What sets AIFMD Annex IV apart from the other reportings, for its landing page. */
const FACTS: ReportingFact[] = [
    { label: "Legal basis", value: "Regulation (EU) No 231/2013, Annex IV — CSSF AIFM Reporting Technical Guidance" },
    { label: "Unit of filing", value: "One AIFM-level file (DATMAN) and one AIF-level file (DATAIF) per AIF / compartment" },
    { label: "Checks", value: "The CSSF controls, then ESMA's XSD v1.2" },
    { label: "Output", value: "DATMAN and DATAIF XML files" },
]

const SUMMARY =
    "Annex IV reporting (Regulation (EU) No 231/2013, Annex IV — CSSF AIFM Reporting) — one AIFM-level record plus one AIF-level record per AIF / compartment, covering all 38 AIFM-file and 301 AIF-file items."

/** The AIFMD Annex IV home page: the landing page of /aifmd. */
const AifmdHome: React.FC = () => {
    const module = useModule()
    return <ReportingHome module={module} summary={SUMMARY} facts={FACTS} />
}

export default AifmdHome
