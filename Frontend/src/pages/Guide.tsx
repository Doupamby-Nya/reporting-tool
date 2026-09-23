import PageTitle from "@components/PageTitle"

/**
 * How the platform is meant to be used, and — just as important — what it
 * does not do. The limitations below are not disclaimers for their own sake:
 * they are the difference between a filing a preparer can rely on and one
 * they have to re-check by hand.
 */
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
    <section className="flex flex-col gap-2">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        <div className="flex flex-col gap-2 text-sm leading-relaxed text-slate-700">{children}</div>
    </section>
)

const Guide: React.FC = () => (
    <section className="flex max-w-4xl flex-col gap-8">
        <PageTitle title="User Guide"
            subtitle="Automated production of regulatory filings for third-party management companies." />

        <Section title="The production chain">
            <p>
                Every regime follows the same five steps, which is what lets one control layer serve
                eight regulators:
            </p>
            <ol className="ml-5 flex list-decimal flex-col gap-1">
                <li>
                    <strong>Ingestion</strong> — the standardised workbook is downloaded, filled in
                    offline and uploaded back. What the parser read is shown exactly as the generator
                    will receive it.
                </li>
                <li>
                    <strong>Rules Engine</strong> — the regulator's own controls and the field-to-element
                    mapping, reported against the submission: what is filled, what is missing, which
                    cross-checks fail.
                </li>
                <li>
                    <strong>Generation</strong> — the filing is built and validated against the
                    regulator's schema before it can be downloaded.
                </li>
                <li>
                    <strong>Preview</strong> — the produced document can be read and corrected. An edit
                    only replaces the filing once it is explicitly saved.
                </li>
                <li>
                    <strong>Controls &amp; Audit</strong> — four-eyes review. A filing stays under review
                    until it is approved and published, and every transition is written to one trail.
                </li>
            </ol>
        </Section>

        <Section title="What each regime produces">
            <ul className="ml-5 flex list-disc flex-col gap-1">
                <li><strong>PRIIPs KID</strong> — the key information document, as a PDF, with the SRI,
                    cost and performance-scenario calculations of the RTS.</li>
                <li><strong>FATCA &amp; CRS</strong> — the XML returns for the Luxembourg tax authority,
                    with the account classification that precedes them.</li>
                <li><strong>U 1.1</strong> — the monthly XML filing on undertakings for collective
                    investment (Circular CSSF 15/627).</li>
                <li><strong>O 4.1</strong> — the balance-sheet return of Circular IML 97/136, filed as
                    EDIFACT rather than XML.</li>
                <li><strong>ESEF</strong> — the annual report in Inline XBRL, and the ESEF report package.</li>
                <li><strong>AIFMD Annex IV</strong> — the AIFM-level (DATMAN) and AIF-level (DATAIF)
                    files.</li>
                <li><strong>SAQ</strong> — an internal summary of the Circular CSSF 21/790 self-assessment,
                    for review and record-keeping ahead of the eDesk filing.</li>
                <li><strong>BCL</strong> — the six statistical reports: S 1.3, S 2.13, S 1.6, S 2.20,
                    S 4.4 and TPTOBS Layout 3.</li>
            </ul>
        </Section>

        <Section title="Scope and limitations">
            <ul className="ml-5 flex list-disc flex-col gap-1">
                <li>
                    The PRIIPs calculation methodology is simplified and configurable. It follows the
                    spirit of Regulation (EU) 1286/2014 and its RTS without reproducing the full
                    actuarial formulas — the Cornish-Fisher approach and the official MRM/CRM matrix in
                    particular. Calibrate it before any production use.
                </li>
                <li>
                    The ESEF output has not been run through an XBRL processor against ESMA's conformance
                    suite, and its extension schema declares no custom elements.
                </li>
                <li>
                    The SAQ is filed on CSSF's eDesk portal; there is no public schema to generate
                    against, so this module tracks rather than files.
                </li>
                <li>
                    Schema validation proves a filing is well-formed against the regulator's XSD. The
                    checks a regulator runs against its own register — that an entity code exists, that a
                    period has not already been filed — cannot be reproduced here and remain the
                    preparer's responsibility.
                </li>
                <li>
                    There is no authentication yet: the name entered in the header is what the audit
                    trail records, on trust.
                </li>
            </ul>
        </Section>
    </section>
)

export default Guide
