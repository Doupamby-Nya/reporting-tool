import { Link, Navigate, useLocation } from "react-router-dom"
import { FiLock } from "react-icons/fi"

import ModuleLogo from "@components/ModuleLogo"
import { PITCHES } from "@config/catalogue"
import type { ModuleNav } from "@config/navigation"
import { useCurrentUser } from "@hooks/useCurrentUser"

/**
 * In front of every page of a module. A visitor is sent to sign in and
 * brought back; a signed-in user without the module is told so, rather than
 * shown pages whose every call the API would refuse.
 */
const ModuleGate: React.FC<{ module: ModuleNav; children: React.ReactNode }> = ({ module, children }) => {
    const { me, canUse } = useCurrentUser()
    const { pathname } = useLocation()

    if (!me) return <Navigate to={`/login?next=${encodeURIComponent(pathname)}`} replace />
    if (canUse(module.key)) return <>{children}</>

    return (
        <section className="mx-auto flex max-w-xl flex-col items-center gap-4 py-16 text-center">
            <ModuleLogo moduleKey={module.key} size={72} />
            <h1 className="text-2xl font-black text-[#0A2647]">{module.title}</h1>
            <p className="text-sm text-slate-600">{PITCHES[module.key]?.pitch}</p>
            <p className="flex items-center gap-2 rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-600">
                <FiLock aria-hidden="true" /> This module is not part of your subscription.
            </p>
            <p className="text-xs text-slate-500">
                Your administrator can open it once your organisation has subscribed to it.
            </p>
            <Link to="/" className="text-sm font-bold text-[#1F5FA8] hover:underline">Back to the home page</Link>
        </section>
    )
}

export default ModuleGate
