import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { fetchDocuments } from "@api/reportingApi"
import { useCurrentUser } from "@hooks/useCurrentUser"

type Pending = { module: string; moduleLabel: string; label: string; status: string }

/**
 * Filings waiting on somebody.
 *
 * A filing that has been generated but not yet approved is work outstanding,
 * and it is easy to lose track of across eight modules — so the count is
 * carried in the header, as the Streamlit original did, and each entry links
 * straight to the review screen of its module.
 */
const NotificationBell: React.FC = () => {
    const { modules } = useCurrentUser()
    const [pending, setPending] = useState<Pending[]>([])
    const [open, setOpen] = useState(false)

    useEffect(() => {
        let cancelled = false
        // One request per module; a module with no documents yet simply
        // contributes nothing rather than failing the whole bell.
        Promise.all(modules.map(async (module) => {
            try {
                const documents = await fetchDocuments(module.key)
                return Object.values(documents)
                    .filter((document) => ["Generated", "Under review"].includes(document.status))
                    .map((document) => ({
                        module: module.key, moduleLabel: module.label,
                        label: document.label, status: document.status,
                    }))
            } catch {
                return []
            }
        })).then((results) => {
            if (!cancelled) setPending(results.flat())
        })
        return () => { cancelled = true }
        // eslint-disable-next-line react-hooks/exhaustive-deps -- the module list changes only on sign-in
    }, [modules.map((module) => module.key).join()])

    return (
        <div className="relative">
            <button type="button" onClick={() => setOpen(!open)}
                aria-label={`${pending.length} filing(s) awaiting review`}
                className="relative rounded-md p-2 text-slate-600 transition hover:bg-slate-100">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {pending.length > 0 && (
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center
                                     rounded-full bg-[#B3261E] px-1 text-[10px] font-semibold text-white">
                        {pending.length}
                    </span>
                )}
            </button>

            {open && (
                <div className="absolute right-0 top-full z-30 mt-1 w-80 rounded-lg border border-slate-200
                                bg-white p-2 shadow-lg">
                    <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Awaiting review
                    </p>
                    {pending.length === 0 ? (
                        <p className="px-2 py-2 text-sm text-slate-500">Nothing is waiting on you.</p>
                    ) : pending.map((item, index) => (
                        <Link key={index} to={`/${item.module}/controls`} onClick={() => setOpen(false)}
                            className="block rounded-md px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-100">
                            <span className="font-semibold">{item.moduleLabel}</span> · {item.label}
                            <span className="block text-xs text-slate-500">{item.status}</span>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    )
}

export default NotificationBell
