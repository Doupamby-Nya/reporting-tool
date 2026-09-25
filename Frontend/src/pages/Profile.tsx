import { Navigate, NavLink, useParams } from "react-router-dom"

import { fetchMyActivity } from "@api/reportingApi"
import ActivityDashboard from "@components/activity/ActivityDashboard"
import ModuleLogo from "@components/ModuleLogo"
import PageTitle from "@components/PageTitle"
import { useCurrentUser } from "@hooks/useCurrentUser"

const ROLES: Record<string, string> = {
    platform_admin: "Platform administrator",
    org_admin: "Organisation administrator",
    user: "User",
}

const TABS = [["", "Account"], ["usage", "Usage"]] as const

/**
 * The signed-in person's own page: who they are on the platform, and under
 * "Usage" what they have done on it. Nobody else's activity is reachable
 * from here; the API answers /activity/me for the session's own account.
 */
const Profile: React.FC = () => {
    const { me, modules, validUntil } = useCurrentUser()
    const { tab = "" } = useParams()
    if (!me) return <Navigate to={`/login?next=${encodeURIComponent(`/profile${tab ? `/${tab}` : ""}`)}`} replace />

    return (
        <section className="flex flex-col gap-6">
            <header className="flex flex-wrap items-center gap-5">
                <span className="flex h-16 w-16 items-center justify-center rounded-2xl text-xl font-black text-white
                                 shadow-[0_10px_30px_-12px_rgba(15,23,42,.35)]"
                    style={{ background: "linear-gradient(135deg, #0A2647 0%, #1F5FA8 100%)" }}>
                    {me.name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}
                </span>
                <PageTitle eyebrow={me.organisation} title={me.name} subtitle={`${me.email} · ${ROLES[me.role]}`} />
            </header>

            <nav className="flex gap-1 border-b border-slate-200" aria-label="Profile">
                {TABS.map(([path, label]) => (
                    <NavLink key={path} to={`/profile${path ? `/${path}` : ""}`} end
                        className={({ isActive }) => [
                            "-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition",
                            isActive ? "border-[#0A2647] text-[#0A2647]"
                                     : "border-transparent text-slate-500 hover:text-slate-900",
                        ].join(" ")}>
                        {label}
                    </NavLink>
                ))}
            </nav>

            {tab === "usage" ? (
                <ActivityDashboard load={fetchMyActivity} />
            ) : (
                <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <section className="rounded-xl border border-slate-200 bg-white p-5">
                        <h2 className="text-sm font-semibold text-slate-900">Account</h2>
                        <dl className="mt-3 grid grid-cols-[140px_minmax(0,1fr)] gap-y-2 text-sm">
                            <dt className="text-slate-500">Name</dt><dd className="text-slate-900">{me.name}</dd>
                            <dt className="text-slate-500">Email</dt><dd className="truncate text-slate-900">{me.email}</dd>
                            <dt className="text-slate-500">Organisation</dt><dd className="text-slate-900">{me.organisation}</dd>
                            <dt className="text-slate-500">Role</dt><dd className="text-slate-900">{ROLES[me.role]}</dd>
                        </dl>
                    </section>
                    <section className="rounded-xl border border-slate-200 bg-white p-5">
                        <h2 className="text-sm font-semibold text-slate-900">Reportings you can use</h2>
                        {modules.length === 0 ? (
                            <p className="mt-3 text-sm text-slate-500">
                                None yet. Your administrator opens reportings to you once your organisation subscribes.
                            </p>
                        ) : (
                            <ul className="mt-3 flex flex-col gap-2">
                                {modules.map((module) => {
                                    const until = validUntil(module.key)
                                    return (
                                        <li key={module.key} className="flex items-center gap-3">
                                            <ModuleLogo moduleKey={module.key} size={30} />
                                            <span className="min-w-0 flex-1 text-sm font-medium text-slate-800">{module.label}</span>
                                            <span className="text-xs text-slate-500">
                                                {until ? `until ${new Date(until).toLocaleDateString("en-GB")}` : "no end date"}
                                            </span>
                                        </li>
                                    )
                                })}
                            </ul>
                        )}
                    </section>
                </div>
            )}
        </section>
    )
}

export default Profile
