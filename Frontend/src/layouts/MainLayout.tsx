import { useEffect, useRef, useState } from "react"
import { useDispatch } from "react-redux"
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"

import { fetchMe } from "@api/reportingApi"
import NotificationBell from "@components/NotificationBell"
import TabScroller from "@components/TabScroller"
import { useCurrentUser } from "@hooks/useCurrentUser"
import type { AppDispatch } from "@store/store"
import { signedIn } from "@store/userSlice"

/**
 * The shell every page sits in.
 *
 * The header carries the identity block and, for a signed-in user, their
 * account; beneath it a row of destinations. A module's tab is only there
 * when the user can use that module — a visitor sees the home page and the
 * guide, nothing else.
 */

/** The brand gradient, from the deep navy to the brighter blue. */
const GRADIENT = "linear-gradient(135deg, #0A2647 0%, #1F5FA8 100%)"
const ELEVATION = "0 10px 30px -12px rgba(15,23,42,.18)"

const PILL = "shrink-0 whitespace-nowrap rounded-xl px-5 py-2.5 text-[13px] font-semibold " +
    "transition-all duration-150 will-change-transform"

const tabClass = ({ isActive }: { isActive: boolean }) =>
    [
        PILL,
        "min-w-[140px] text-center",
        isActive
            ? "border border-transparent text-white -translate-y-px"
            : "border border-slate-200 bg-white text-[#123A6B] hover:-translate-y-px " +
              "hover:border-[#0A2647] hover:text-[#0A2647]",
    ].join(" ")

const tabStyle = ({ isActive }: { isActive: boolean }) =>
    isActive ? { background: GRADIENT, boxShadow: ELEVATION } : undefined

const MainLayout: React.FC = () => {
    const { me, modules } = useCurrentUser()
    const dispatch = useDispatch<AppDispatch>()
    const { pathname } = useLocation()
    const fullBleed = pathname === "/"

    // The server normally renders the page already signed in. When it could
    // not reach the API, the browser asks once itself.
    const asked = useRef(false)
    useEffect(() => {
        if (me || asked.current) return
        asked.current = true
        fetchMe().then((found) => dispatch(signedIn(found))).catch(() => undefined)
    }, [me, dispatch])

    return (
        <div className="flex min-h-screen w-full flex-col bg-[#F6F7F9]">
            <header className="sticky top-0 z-20 backdrop-blur-[10px] backdrop-saturate-[180%]"
                style={{ backgroundColor: "rgba(246,247,249,.88)" }}>

                <div className="mx-auto flex w-full max-w-[1400px] items-center gap-4 px-6 py-3">
                    <Link to="/" className="flex min-w-0 items-center gap-4">
                        <img src="/forvisMazarslogo.png" alt="Forvis Mazars" className="h-10 w-auto shrink-0" />
                        <span className="min-w-0 text-[1.55rem] font-black uppercase leading-[1.15]
                                         tracking-[0.03em] text-[#0A2647]">
                            Forvis Mazars Regulatory Reporting Platform
                        </span>
                    </Link>

                    <div className="ml-auto flex shrink-0 items-center gap-2">
                        <NavLink to="/guide"
                            className={({ isActive }) => [
                                PILL,
                                isActive
                                    ? "border border-transparent text-white"
                                    : "border border-transparent bg-[#0A2647] text-white hover:bg-[#123A6B]",
                            ].join(" ")}
                            style={({ isActive }) =>
                                isActive ? { background: GRADIENT, boxShadow: ELEVATION } : undefined}>
                            Guide
                        </NavLink>
                        {me ? (
                            <>
                                {modules.length > 0 && <NotificationBell />}
                                <AccountMenu />
                            </>
                        ) : (
                            <NavLink to="/login"
                                className={`${PILL} border border-[#0A2647] bg-white text-[#0A2647] hover:bg-slate-100`}>
                                Sign in
                            </NavLink>
                        )}
                    </div>
                </div>

                <nav className="mx-auto w-full max-w-[1400px] border-b px-6 pb-3 pt-1"
                    style={{ borderColor: "rgba(10,38,71,.12)" }}>
                    <TabScroller>
                        <NavLink to="/" end className={tabClass} style={tabStyle}>Home</NavLink>
                        {modules.length > 0 && (
                            <NavLink to="/dashboard" className={tabClass} style={tabStyle}>Dashboard</NavLink>
                        )}
                        {modules.map((module) => (
                            // The tab opens the reporting's Home page, and stays lit on every step under it.
                            <NavLink key={module.key} to={`/${module.key}`} className={tabClass} style={tabStyle}>
                                {module.label}
                            </NavLink>
                        ))}
                    </TabScroller>
                </nav>
            </header>

            <main className={fullBleed ? "w-full flex-1" : "mx-auto w-full max-w-[1400px] flex-1 px-6 py-6"}>
                <Outlet />
            </main>

            <footer className="border-t border-slate-200 bg-white">
                <p className="mx-auto w-full max-w-[1400px] px-6 py-3 text-xs text-slate-500">
                    Every filing is validated against the regulator's own rules and XML schema before it can be
                    downloaded. The checks a regulator runs against its own register cannot be reproduced here and
                    remain the preparer's responsibility.
                </p>
            </footer>
        </div>
    )
}

/** The signed-in account, its organisation, and signing out. */
const AccountMenu: React.FC = () => {
    const { me, signOut } = useCurrentUser()
    const navigate = useNavigate()
    const [open, setOpen] = useState(false)
    if (!me) return null

    const leave = async () => {
        setOpen(false)
        await signOut()
        navigate("/")
    }

    return (
        <div className="relative">
            <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
                className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-left
                           transition hover:border-[#0A2647]">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0A2647] text-xs font-bold text-white">
                    {me.name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}
                </span>
                <span className="hidden flex-col leading-tight sm:flex">
                    <span className="text-xs font-semibold text-slate-900">{me.name}</span>
                    <span className="text-[11px] text-slate-500">{me.organisation}</span>
                </span>
            </button>
            {open && (
                <div className="absolute right-0 top-full z-30 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
                    <p className="text-sm font-semibold text-slate-900">{me.name}</p>
                    <p className="text-xs text-slate-500">{me.email}</p>
                    <p className="mt-1 text-xs text-slate-500">
                        {me.organisation}{me.role !== "user" && ` · ${me.role === "platform_admin" ? "platform administrator" : "organisation administrator"}`}
                    </p>
                    <button type="button" onClick={leave}
                        className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-semibold text-[#0A2647] hover:bg-slate-50">
                        Sign out
                    </button>
                </div>
            )}
        </div>
    )
}

export default MainLayout
