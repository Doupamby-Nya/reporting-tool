import { useEffect, useMemo, useState } from "react"
import { Navigate, useSearchParams } from "react-router-dom"
import { FiChevronRight } from "react-icons/fi"

import { fetchActivityScopes, fetchOrganisationActivity } from "@api/reportingApi"
import ActivityDashboard from "@components/activity/ActivityDashboard"
import PageTitle from "@components/PageTitle"
import { useCurrentUser } from "@hooks/useCurrentUser"
import type { ActivityScope } from "src/types/reportingType"

const select = "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition " +
    "focus:border-[#0A2647] focus:ring-2 focus:ring-[#0A2647]/10"

/**
 * Activity across an organisation, for its administrators: who works, in
 * which reporting, and how much. A platform administrator chooses the
 * organisation, or looks at all of them; an organisation administrator is
 * kept to their own by the API, whatever this page asks for. The choice is
 * kept in the address, so a view can be bookmarked or sent.
 */
const ActivityAdmin: React.FC = () => {
    const { me } = useCurrentUser()
    const [params, setParams] = useSearchParams()
    const [scopes, setScopes] = useState<ActivityScope[]>([])

    const isPlatform = me?.role === "platform_admin"
    const organisationId = Number(params.get("organisation")) || null
    const userId = Number(params.get("user")) || null

    useEffect(() => {
        if (!me || me.role === "user") return
        fetchActivityScopes().then(setScopes).catch(() => setScopes([]))
    }, [me])

    // An organisation administrator has exactly one organisation.
    const organisation = scopes.find((scope) => scope.id === organisationId)
        ?? (!isPlatform ? scopes[0] : undefined)
    const person = scopes.flatMap((scope) => scope.users).find((user) => user.id === userId)
    const scope = useMemo(() => ({ organisation_id: organisation?.id ?? null, user_id: userId }),
        [organisation?.id, userId])

    if (!me) return <Navigate to="/login?next=%2Fadmin%2Factivity" replace />
    if (me.role === "user") return <Navigate to="/profile/usage" replace />

    const choose = (next: { organisation?: number | null; user?: number | null }) => {
        const query = new URLSearchParams()
        const org = next.organisation !== undefined ? next.organisation : organisationId
        const user = next.user !== undefined ? next.user : userId
        if (org) query.set("organisation", String(org))
        if (user) query.set("user", String(user))
        setParams(query)
    }

    const people = organisation ? organisation.users : scopes.flatMap((item) => item.users)

    return (
        <section className="flex flex-col gap-6">
            <PageTitle eyebrow="Administration" title="Activity"
                subtitle="Who works on the platform, in which reporting, and how much. Choose an organisation or a
                          person to narrow it; every figure below follows." />

            <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
                {isPlatform ? (
                    <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                        Organisation
                        <select className={select} value={organisation?.id ?? ""}
                            onChange={(event) => choose({ organisation: Number(event.target.value) || null, user: null })}>
                            <option value="">All organisations</option>
                            {scopes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                        </select>
                    </label>
                ) : (
                    <div className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                        Organisation
                        <span className="px-1 py-2 text-sm font-semibold text-slate-900">{organisation?.name ?? me.organisation}</span>
                    </div>
                )}
                <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
                    Person
                    <select className={select} value={userId ?? ""}
                        onChange={(event) => choose({ user: Number(event.target.value) || null })}>
                        <option value="">Everyone</option>
                        {people.map((user) => (
                            <option key={user.id} value={user.id}>{user.name}{user.active ? "" : " (disabled)"}</option>
                        ))}
                    </select>
                </label>

                {/* Where the view stands, as a trail back up: only once there is somewhere to go back to. */}
                {(isPlatform || person) && (
                <p className="ml-auto flex items-center gap-1 text-sm text-slate-500">
                    <button type="button" onClick={() => choose({ organisation: null, user: null })}
                        className="hover:text-[#0A2647] hover:underline" disabled={!isPlatform}>
                        {isPlatform ? "All organisations" : me.organisation}
                    </button>
                    {isPlatform && organisation && (
                        <>
                            <FiChevronRight />
                            <button type="button" onClick={() => choose({ user: null })}
                                className="hover:text-[#0A2647] hover:underline">{organisation.name}</button>
                        </>
                    )}
                    {person && (
                        <>
                            <FiChevronRight />
                            <span className="font-semibold text-slate-900">{person.name}</span>
                        </>
                    )}
                </p>
                )}
            </div>

            <ActivityDashboard load={fetchOrganisationActivity} scope={scope}
                onPickUser={userId ? undefined : (id) => choose({ user: id })}
                onPickOrganisation={isPlatform && !organisation && !userId
                    ? (id) => choose({ organisation: id, user: null }) : undefined} />
        </section>
    )
}

export default ActivityAdmin
