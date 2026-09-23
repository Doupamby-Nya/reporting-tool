export type Kpi = { label: string; value: string; hint?: string }

/**
 * A row of equal-width figure cards, as the Streamlit original used at the
 * top of the global summary and of every rules-engine step. The accent
 * colour cycles per card so the row reads as a row rather than a list.
 */
const ACCENTS = ["#0A2647", "#1F5FA8", "#C77700", "#1E7F4F", "#B3261E"]

const KpiRow: React.FC<{ items: Kpi[] }> = ({ items }) => (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item, index) => (
            <div key={item.label} className="rounded-lg border border-slate-200 bg-white p-4"
                style={{ borderTopColor: ACCENTS[index % ACCENTS.length], borderTopWidth: 3 }}>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{item.label}</p>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{item.value}</p>
                {item.hint && <p className="mt-0.5 text-xs text-slate-500">{item.hint}</p>}
            </div>
        ))}
    </div>
)

export default KpiRow
