import FieldHelp from "@components/FieldHelp"

/**
 * The input primitives the three BCL capture forms share.
 *
 * The regulator's item number comes first, before the wording: that is the
 * order the BCL instructions are indexed in, so a preparer cross-checking a
 * screen against the rulebook scans for the number, not the sentence. Each
 * field carries a help marker saying what belongs in it.
 */

const LABEL = "flex h-full flex-col gap-1 text-sm"
const INPUT = "rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-[#0A2647]"

const EXPECTS: Record<string, string> = {
    date: "a date",
    number: "an amount",
    text: "text",
}

/** Item number first, then the wording, then the help marker. */
const Caption: React.FC<{
    label: string; item?: string; expects?: string; note?: string
}> = ({ label, item, expects, note }) => (
    <span className="flex flex-1 items-start gap-1.5 font-medium leading-snug text-slate-700">
        {item && <span className="shrink-0 font-mono text-xs text-[#1F5FA8]">{item}</span>}
        <span>{label}</span>
        <FieldHelp code={item} label={label} expects={expects} note={note} />
    </span>
)

export const Field: React.FC<{
    label: string
    item?: string
    value: string
    onChange: (next: string) => void
    type?: string
    hint?: string
}> = ({ label, item, value, onChange, type = "text", hint }) => (
    <label className={LABEL}>
        <Caption label={label} item={item} expects={EXPECTS[type] ?? "text"} note={hint} />
        <input type={type} value={value} onChange={(event) => onChange(event.target.value)}
            className={INPUT} />
        {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </label>
)

export const Select: React.FC<{
    label: string
    item?: string
    value: string
    onChange: (next: string) => void
    options: [string, string][]
    hint?: string
}> = ({ label, item, value, onChange, options, hint }) => (
    <label className={LABEL}>
        <Caption label={label} item={item} expects="one of the regulator's codes"
            note={hint ?? `${options.length} code(s) available.`} />
        <select value={value} onChange={(event) => onChange(event.target.value)} className={INPUT}>
            <option value="">—</option>
            {options.map(([code, text]) => <option key={code} value={code}>{text}</option>)}
        </select>
        {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </label>
)

export const Money: React.FC<{
    label: string
    item?: string
    value: string
    onChange: (next: string) => void
    /** A line with its own "of which" breakdown beneath it. */
    consolidating?: boolean
    /** One of those "of which" lines. */
    child?: boolean
}> = ({ label, item, value, onChange, consolidating = false, child = false }) => (
    <label className={[
        "flex items-center justify-between gap-4 border-b py-1.5 text-sm",
        consolidating
            ? "border-slate-200 bg-slate-100/70 px-2 font-medium text-slate-900"
            : "border-slate-100",
        child ? "pl-6" : "",
    ].join(" ")}>
        <span className="flex flex-1 items-start gap-1.5 leading-snug text-slate-700">
            {item && <span className="w-12 shrink-0 font-mono text-xs text-[#1F5FA8]">{item}</span>}
            <span>{label}</span>
            <FieldHelp code={item} label={label} expects="an amount"
                note="Leave empty for 'not reported' — that is not the same as reporting a zero." />
        </span>
        <input type="number" step="0.01" value={value} onChange={(event) => onChange(event.target.value)}
            placeholder="Not reported"
            className="w-44 shrink-0 rounded-md border border-slate-300 px-2 py-1 text-right font-normal
                       outline-none focus:border-[#0A2647]" />
    </label>
)

export const Section: React.FC<{ title: string; hint?: string; children: React.ReactNode }> =
    ({ title, hint, children }) => (
        <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
            <div>
                <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
                {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
            </div>
            {children}
        </section>
    )

/** A numeric string turned into what the API wants: a number, or nothing at
 *  all. An empty field means "not reported", which is not a zero. */
export const numberOrNull = (value: string): number | null =>
    value.trim() === "" ? null : Number.parseFloat(value)

/** A date string the API can parse, or nothing. */
export const dateOrNull = (value: string): string | null => (value.trim() === "" ? null : value)

/**
 * A regulator's code list, whatever shape it arrives in.
 *
 * The API serves most of them as a mapping of code to label, a few as a
 * plain list of codes, and occasionally as pairs. A picker that understood
 * only one of those rendered an empty dropdown — which is not a cosmetic
 * failure: a mandatory code that cannot be chosen makes the report
 * impossible to file. So every shape is accepted here, once, rather than at
 * each call site.
 */
export function toOptions(value: unknown): [string, string][] {
    if (!value) return []
    if (Array.isArray(value)) {
        return value.map((entry) =>
            Array.isArray(entry)
                ? [String(entry[0]), `${String(entry[0])} — ${String(entry[1])}`]
                : [String(entry), String(entry)])
    }
    if (typeof value === "object") {
        return Object.entries(value as Record<string, unknown>)
            .map(([code, label]) => [code, `${code} — ${String(label)}`])
    }
    return []
}


/** True when a label is an "of which" line rather than a figure of its own.
 *  The regulator marks them either by its own wording or by an ellipsis, and
 *  either can sit after the item number where the label carries one. */
export const isBreakdownLabel = (label: string): boolean => {
    const wording = label.replace(/^\s*[\w.-]+\s*[—–-]\s*/, "")
    return /^[\s….]/.test(wording) || /^of which/i.test(wording.trim())
}
