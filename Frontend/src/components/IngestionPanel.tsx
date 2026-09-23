import { useRef, useState } from "react"

/**
 * How a filing gets into the platform, on one bar, the same for every
 * regime.
 *
 * A preparer arrives with one of five things: nothing but a client file they
 * want read for them, nothing at all (they will type it), a blank template
 * to fill offline, a workbook already filled, or a filing produced earlier.
 * The bar offers whichever of those the regime actually supports, so a
 * missing capability is an absent button rather than one that fails when
 * pressed.
 *
 * AI ingestion comes first because it is the route that will do the most
 * work for the preparer; the manual ones follow in the order they are used.
 */
export type IngestionAction = {
    label: string
    /** A download link, for a blank template or a reference document. */
    href?: string
    /** A file picker, for a workbook or a filing to read back. */
    accept?: string
    onFile?: (file: File) => void | Promise<void>
    onClick?: () => void
    hint?: string
    primary?: boolean
}

/** The id the capture form carries, so "Open the form" can reach it. */
export const FORM_ANCHOR = "capture-form"

const TAB = "flex items-center gap-2 whitespace-nowrap rounded-md border px-4 py-2 text-sm " +
    "font-medium transition"
const NEUTRAL = `${TAB} border-slate-300 bg-white text-slate-700 hover:border-[#0A2647]`
const PRIMARY = `${TAB} border-[#0A2647] bg-[#0A2647] text-white hover:bg-[#123A6B]`

const Action: React.FC<{ action: IngestionAction; busy: boolean }> = ({ action, busy }) => {
    const input = useRef<HTMLInputElement>(null)
    const className = action.primary ? PRIMARY : NEUTRAL

    if (action.href) {
        return <a href={action.href} className={className}>{action.label}</a>
    }
    if (action.onFile) {
        return (
            <>
                <button type="button" disabled={busy} className={`${className} disabled:opacity-50`}
                    onClick={() => input.current?.click()}>
                    {action.label}
                </button>
                <input ref={input} type="file" accept={action.accept} className="hidden"
                    onChange={(event) => {
                        const file = event.target.files?.[0]
                        if (file) void action.onFile?.(file)
                        // Cleared so picking the same file twice still fires.
                        event.target.value = ""
                    }} />
            </>
        )
    }
    return (
        <button type="button" onClick={action.onClick} disabled={busy}
            className={`${className} disabled:opacity-50`}>
            {action.label}
        </button>
    )
}

/**
 * The AI ingestion entry point.
 *
 * It is deliberately inert for now and says so when pressed, rather than
 * being hidden: the workflow it belongs to — drop in whatever the client
 * sent, have it read and mapped onto the template — is the one this screen
 * is designed around, and a preparer should be able to see where it will
 * sit. It never silently does nothing.
 */
const AiIngestion: React.FC<{ regime: string }> = ({ regime }) => {
    const [explained, setExplained] = useState(false)
    return (
        <div className="relative">
            <button type="button" onClick={() => setExplained(!explained)}
                aria-expanded={explained}
                className={`${TAB} border-dashed border-[#1F5FA8] bg-gradient-to-r from-[#0A2647]/5
                            to-[#1F5FA8]/10 text-[#0A2647] hover:from-[#0A2647]/10 hover:to-[#1F5FA8]/20`}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
                    <path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z" />
                </svg>
                AI ingestion
                <span className="rounded-full bg-[#1F5FA8] px-1.5 py-0.5 text-[10px] font-semibold
                                 uppercase text-white">
                    soon
                </span>
            </button>

            {explained && (
                <div className="absolute left-0 top-full z-30 mt-2 w-80 rounded-lg border border-slate-200
                                bg-white p-4 shadow-lg">
                    <p className="text-sm font-semibold text-slate-900">Not available yet</p>
                    <p className="mt-1 text-sm text-slate-600">
                        This is where a client&apos;s own file — a trial balance, a custodian extract, a
                        spreadsheet in whatever shape they keep it — will be read and mapped onto the{" "}
                        {regime} template, with every mapped field shown for review before anything is
                        filed.
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                        Until then, use the blank template or fill the form in directly.
                    </p>
                </div>
            )}
        </div>
    )
}

const IngestionPanel: React.FC<{
    regime: string
    actions: IngestionAction[]
    busy?: boolean
    /**
     * Whether the capture form is showing. It starts closed: a preparer who
     * came to bring a file should not have to scroll past a few hundred
     * empty fields to reach the panel they wanted.
     */
    formOpen?: boolean
    onToggleForm?: () => void
    children?: React.ReactNode
}> = ({ regime, actions, busy = false, formOpen, onToggleForm, children }) => {
    const toggleForm = () => {
        onToggleForm?.()
        // Scroll only when opening, and after the form has been laid out.
        if (!formOpen) {
            window.setTimeout(() => {
                document.getElementById(FORM_ANCHOR)
                    ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }, 0)
        }
    }

    return (
        <section className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-5">
            <div>
                <h2 className="text-sm font-semibold text-slate-900">Getting the data in</h2>
                <p className="mt-0.5 text-xs text-slate-500">
                    Start from a blank template, bring in a file you have already filled, re-open a filing
                    produced earlier — or fill the form below by hand.
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <AiIngestion regime={regime} />
                {actions.map((action) => (
                    <Action key={action.label} action={action} busy={busy} />
                ))}
                {onToggleForm && (
                    <button type="button" onClick={toggleForm} aria-expanded={formOpen}
                        className={formOpen ? PRIMARY : NEUTRAL}>
                        {formOpen ? "Hide the form" : "Open the form"}
                    </button>
                )}
            </div>

            {actions.some((action) => action.hint) && (
                <ul className="flex flex-col gap-0.5 text-xs text-slate-500">
                    {actions.filter((action) => action.hint).map((action) => (
                        <li key={action.label}>
                            <span className="font-medium">{action.label}</span> — {action.hint}
                        </li>
                    ))}
                </ul>
            )}

            {children}
        </section>
    )
}

export default IngestionPanel
