/**
 * The four performance scenarios of a PRIIPs KID.
 *
 * As a table the amount and the return ran together — "7,1312.06 %" — and
 * the four scenarios read as four equivalent rows, which they are not: they
 * are a range, from what happens in a severe market to what happens in a
 * good one. So each gets a card, ordered worst to best and coloured along
 * that axis, with a ring showing the return against the widest outcome on
 * screen. The ring is a comparison, not a measurement: it makes the spread
 * between the four visible at a glance, and the figures underneath are what
 * gets read.
 */

export type ScenarioOutcome = { amount: number; return_pct: number }

export type ScenarioHorizon = {
    horizon_years: number
    horizon_label: string
    stress: ScenarioOutcome
    unfavourable: ScenarioOutcome
    moderate: ScenarioOutcome
    favourable: ScenarioOutcome
}

/** Worst to best, which is the order the regulator prints them in. */
const SCENARIOS = [
    { key: "stress", label: "Stress", colour: "#B3261E",
      note: "A severe market downturn." },
    { key: "unfavourable", label: "Unfavourable", colour: "#E07B39",
      note: "The worst 10 % of outcomes." },
    { key: "moderate", label: "Moderate", colour: "#1F5FA8",
      note: "The middle outcome." },
    { key: "favourable", label: "Favourable", colour: "#1E7F4F",
      note: "The best 10 % of outcomes." },
] as const

const money = (value: number) =>
    value.toLocaleString("en-GB", { maximumFractionDigits: 0 })

const signed = (value: number) =>
    `${value > 0 ? "+" : ""}${value.toFixed(2)} %`

/** A ring whose filled arc is the return's size relative to the widest one
 *  shown, so the four rings can be compared with each other. */
const Ring: React.FC<{ percent: number; scale: number; colour: string }> =
    ({ percent, scale, colour }) => {
        const radius = 34
        const circumference = 2 * Math.PI * radius
        const share = scale > 0 ? Math.min(Math.abs(percent) / scale, 1) : 0
        const negative = percent < 0

        return (
            <svg viewBox="0 0 84 84" className="h-24 w-24" role="img"
                aria-label={`${signed(percent)} a year`}>
                <circle cx="42" cy="42" r={radius} fill="none" stroke="#E7EAEF" strokeWidth="8" />
                <circle cx="42" cy="42" r={radius} fill="none" stroke={colour} strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${share * circumference} ${circumference}`}
                    // Start at the top, and run anticlockwise for a loss so a
                    // negative return does not look like a positive one.
                    transform={negative ? "rotate(-90 42 42) scale(1 -1) translate(0 -84)"
                        : "rotate(-90 42 42)"} />
                <text x="42" y="42" textAnchor="middle" dominantBaseline="central"
                    className="fill-slate-900 text-[13px] font-semibold">
                    {signed(percent)}
                </text>
            </svg>
        )
    }

const ScenarioCards: React.FC<{
    horizons: ScenarioHorizon[]
    investment: number
}> = ({ horizons, investment }) => {
    if (horizons.length === 0) return null

    // One scale across every card on screen, otherwise the rings compare
    // nothing.
    const scale = Math.max(
        ...horizons.flatMap((horizon) =>
            SCENARIOS.map((scenario) => Math.abs(horizon[scenario.key].return_pct))),
        1)

    return (
        <div className="flex flex-col gap-5">
            {horizons.map((horizon) => (
                <section key={horizon.horizon_label} className="flex flex-col gap-3">
                    <h3 className="text-sm font-medium text-slate-700">
                        If you cash in after{" "}
                        <span className="font-semibold text-slate-900">{horizon.horizon_label}</span>
                    </h3>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        {SCENARIOS.map((scenario) => {
                            const outcome = horizon[scenario.key]
                            const gain = outcome.amount - investment
                            return (
                                <article key={scenario.key}
                                    className="relative flex flex-col items-center gap-2 overflow-hidden
                                               rounded-xl border border-slate-200 bg-white p-5">
                                    {/* The scenario's colour, as a band rather than a
                                        whole tinted card: the figures stay readable. */}
                                    <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1"
                                        style={{ backgroundColor: scenario.colour }} />

                                    <p className="text-xs font-semibold uppercase tracking-wide"
                                        style={{ color: scenario.colour }}>
                                        {scenario.label}
                                    </p>

                                    <Ring percent={outcome.return_pct} scale={scale}
                                        colour={scenario.colour} />

                                    <p className="text-2xl font-semibold tabular-nums text-slate-900">
                                        {money(outcome.amount)}
                                    </p>
                                    <p className="text-xs tabular-nums"
                                        style={{ color: gain < 0 ? "#B3261E" : "#1E7F4F" }}>
                                        {gain < 0 ? "−" : "+"}{money(Math.abs(gain))} on your investment
                                    </p>
                                    <p className="text-center text-[11px] leading-snug text-slate-500">
                                        {scenario.note}
                                    </p>
                                </article>
                            )
                        })}
                    </div>
                </section>
            ))}

            <p className="text-xs text-slate-500">
                Figures are what you might get back on an investment of{" "}
                <span className="font-medium text-slate-700">{money(investment)}</span>, after costs.
                The percentage is the return a year. They are not a guarantee: the stress scenario
                shows what a severe market downturn would do, and you could get back less than the
                amounts shown.
            </p>
        </div>
    )
}

export default ScenarioCards
