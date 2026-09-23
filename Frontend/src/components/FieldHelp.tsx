import { useState } from "react"

/**
 * What to report in a field, next to the field.
 *
 * A regulatory form is not self-explanatory: the label is the regulator's
 * own wording, which is terse by design, and the preparer's real question is
 * usually "what exactly goes in here". Answering it in place beats sending
 * someone to a PDF — and what is shown is only what the platform actually
 * knows about the field, never invented guidance.
 *
 * The popover opens on hover and on click, because hover alone is unusable
 * on a touch screen and invisible to a keyboard.
 */
const FieldHelp: React.FC<{
    /** The regulator's item number or code, when the field has one. */
    code?: string
    label: string
    /** The element or concept the value is written to. */
    target?: string
    /** What kind of value the field takes. */
    expects?: string
    /** Anything else known about it — a rule, a unit, a constraint. */
    note?: string
}> = ({ code, label, target, expects, note }) => {
    const [open, setOpen] = useState(false)

    if (!code && !target && !expects && !note) return null

    return (
        <span className="relative inline-flex">
            <button type="button"
                aria-label={`What to report in "${label}"`}
                aria-expanded={open}
                onClick={() => setOpen(!open)}
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
                onFocus={() => setOpen(true)}
                onBlur={() => setOpen(false)}
                className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border
                           border-slate-300 text-[10px] font-semibold leading-none text-slate-500
                           transition hover:border-[#0A2647] hover:bg-[#0A2647] hover:text-white">
                ?
            </button>

            {open && (
                <span role="tooltip"
                    className="absolute left-5 top-0 z-40 w-72 rounded-lg border border-slate-200
                               bg-white p-3 text-left shadow-lg">
                    <span className="block text-sm font-semibold text-slate-900">
                        {code && <span className="mr-2 font-mono text-xs text-[#1F5FA8]">{code}</span>}
                        {label}
                    </span>
                    {expects && (
                        <span className="mt-1 block text-xs text-slate-600">
                            <span className="font-medium">Expects:</span> {expects}
                        </span>
                    )}
                    {target && (
                        <span className="mt-1 block break-all font-mono text-[11px] text-slate-500">
                            {target}
                        </span>
                    )}
                    {note && <span className="mt-1 block text-xs text-slate-600">{note}</span>}
                </span>
            )}
        </span>
    )
}

export default FieldHelp
