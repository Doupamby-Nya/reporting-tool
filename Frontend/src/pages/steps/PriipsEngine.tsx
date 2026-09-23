import { useEffect, useState } from "react"
import { toast } from "react-toastify"

import { calculatePriips, fetchFunds } from "@api/reportingApi"
import KpiRow from "@components/KpiRow"
import PageTitle from "@components/PageTitle"
import ScenarioCards, { type ScenarioHorizon } from "@components/ScenarioCards"
import type { Fund } from "src/types/reportingType"

type CostLine = {
    horizon_label: string
    one_off_amortized_pct: number
    ongoing_pct: number
    incidental_pct: number
    riy_pct: number
    riy_amount_annual: number
    riy_amount_cumulative: number
}

type ScenarioLine = ScenarioHorizon

type Calculation = {
    sri: { mrm_class: number; crm_class: number | null; sri_class: number; credit_risk_material: boolean }
    costs: { reference_amount: number; rhp_years: number; by_horizon: CostLine[] }
    scenarios: { reference_amount: number; rhp_years: number; by_horizon: ScenarioLine[] }
}

const pct = (value: number) => `${value.toFixed(2)} %`
const money = (value: number) => value.toLocaleString("en-GB", { maximumFractionDigits: 0 })

/** The seven SRI bands, coloured as the KID prints them. */
const SRI_COLOURS = ["#1E7F4F", "#4C9A2A", "#A8B400", "#E3B505", "#E07B39", "#D9534F", "#B3261E"]

/**
 * The PRIIPs calculation engine, fund by fund: the summary risk indicator,
 * the cost structure and the four performance scenarios.
 *
 * The RTS parameters behind the figures are returned with them and shown, so
 * a number can be reviewed alongside the calibration that produced it —
 * which is the whole point of a step between ingestion and the document.
 */
const PriipsEngine: React.FC = () => {
    const [funds, setFunds] = useState<Fund[]>([])
    const [fundId, setFundId] = useState("")
    const [calculation, setCalculation] = useState<Calculation | null>(null)
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        fetchFunds().then((found) => {
            setFunds(found)
            if (found.length) setFundId(found[0].fund_id)
        }).catch((error: Error) => toast.error(error.message))
    }, [])

    const fund = funds.find((candidate) => candidate.fund_id === fundId)

    useEffect(() => {
        if (!fund) return
        setBusy(true)
        calculatePriips(fund)
            .then((result) => setCalculation(result as unknown as Calculation))
            .catch((error: Error) => toast.error(error.message))
            .finally(() => setBusy(false))
    }, [fund])

    if (funds.length === 0) {
        return (
            <section className="flex flex-col gap-6">
                <PageTitle title="PRIIPs KID — Calculation Engine" />
                <p className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    The registry is empty. Populate it at the ingestion step first.
                </p>
            </section>
        )
    }

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="PRIIPs KID — Calculation Engine"
                subtitle="The summary risk indicator, the cost structure and the four performance
                          scenarios of the RTS, computed for one share class at a time." />

            <label className="flex max-w-xl flex-col gap-1 text-sm">
                <span className="font-medium text-slate-700">Share class</span>
                <select value={fundId} onChange={(event) => setFundId(event.target.value)}
                    className="rounded-md border border-slate-300 px-3 py-2 outline-none
                               focus:border-[#0A2647]">
                    {funds.map((candidate) => (
                        <option key={candidate.fund_id} value={candidate.fund_id}>
                            {candidate.fund_name} — {candidate.share_class} ({candidate.isin})
                        </option>
                    ))}
                </select>
            </label>

            {busy && <p className="text-sm text-slate-500">Calculating…</p>}

            {calculation && (
                <>
                    <KpiRow items={[
                        { label: "Summary risk indicator", value: String(calculation.sri.sri_class),
                          hint: "1 lowest, 7 highest" },
                        { label: "Market risk (MRM)", value: String(calculation.sri.mrm_class),
                          hint: "from the fund's volatility" },
                        { label: "Credit risk (CRM)",
                          value: calculation.sri.crm_class === null ? "n/a" : String(calculation.sri.crm_class),
                          hint: calculation.sri.credit_risk_material
                              ? "material for this asset class" : "not material" },
                        { label: "Recommended holding period",
                          value: `${calculation.costs.rhp_years} year(s)`, hint: "" },
                    ]} />

                    <section className="flex flex-col gap-3 rounded-lg border border-slate-200
                                        bg-white p-5">
                        <div>
                            <h2 className="text-sm font-semibold text-slate-900">
                                Summary risk indicator
                            </h2>
                            <p className="mt-0.5 text-xs text-slate-500">
                                1 is the lowest risk, 7 the highest. It assumes you keep the product
                                for the recommended holding period.
                            </p>
                        </div>

                        <div className="flex items-end gap-1.5">
                            {SRI_COLOURS.map((colour, index) => {
                                const band = index + 1
                                const active = band === calculation.sri.sri_class
                                return (
                                    <div key={band} className="flex flex-1 flex-col items-center gap-1">
                                        {active && (
                                            <span className="text-[10px] font-semibold uppercase
                                                             tracking-wide"
                                                style={{ color: colour }}>
                                                this fund
                                            </span>
                                        )}
                                        <div
                                            className={[
                                                "flex w-full items-center justify-center rounded-md",
                                                "text-sm font-semibold transition-all",
                                                active ? "text-white shadow-md" : "text-slate-400",
                                            ].join(" ")}
                                            style={{
                                                // The band grows with the risk, so the scale reads
                                                // as a scale rather than seven equal boxes.
                                                height: `${28 + index * 6}px`,
                                                backgroundColor: active ? colour : "#EEF1F5",
                                                outline: active ? `3px solid ${colour}33` : "none",
                                            }}>
                                            {band}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>

                        <div className="flex justify-between text-[11px] text-slate-500">
                            <span>Lower risk, typically lower reward</span>
                            <span>Higher risk, typically higher reward</span>
                        </div>
                    </section>

                    <section className="flex flex-col gap-2">
                        <h2 className="text-sm font-semibold text-slate-900">
                            Costs over time — reduction in yield on {money(calculation.costs.reference_amount)}
                        </h2>
                        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide
                                                  text-slate-500">
                                    <tr>
                                        <th className="px-3 py-2">If you cash in after</th>
                                        <th className="px-3 py-2 text-right">One-off (amortised)</th>
                                        <th className="px-3 py-2 text-right">Ongoing</th>
                                        <th className="px-3 py-2 text-right">Incidental</th>
                                        <th className="px-3 py-2 text-right">Reduction in yield</th>
                                        <th className="px-3 py-2 text-right">Cost, cumulative</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {calculation.costs.by_horizon.map((line) => (
                                        <tr key={line.horizon_label} className="border-t border-slate-100">
                                            <td className="px-3 py-2">{line.horizon_label}</td>
                                            <td className="px-3 py-2 text-right">{pct(line.one_off_amortized_pct)}</td>
                                            <td className="px-3 py-2 text-right">{pct(line.ongoing_pct)}</td>
                                            <td className="px-3 py-2 text-right">{pct(line.incidental_pct)}</td>
                                            <td className="px-3 py-2 text-right font-semibold">{pct(line.riy_pct)}</td>
                                            <td className="px-3 py-2 text-right">
                                                {money(line.riy_amount_cumulative)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <section className="flex flex-col gap-3">
                        <h2 className="text-sm font-semibold text-slate-900">Performance scenarios</h2>
                        <ScenarioCards horizons={calculation.scenarios.by_horizon}
                            investment={calculation.scenarios.reference_amount} />
                        <p className="text-xs text-slate-500">
                            The methodology is simplified relative to the RTS — it does not reproduce
                            the Cornish-Fisher approach or the official MRM/CRM combination matrix.
                            Calibrate it before any production use.
                        </p>
                    </section>

                </>
            )}
        </section>
    )
}

export default PriipsEngine
