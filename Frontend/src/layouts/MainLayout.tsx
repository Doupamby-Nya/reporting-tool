import { NavLink, Outlet } from "react-router-dom"

import { MODULES, firstStepOf } from "@config/navigation"
import NotificationBell from "@components/NotificationBell"
import TabScroller from "@components/TabScroller"
import UserBadge from "@components/UserBadge"

/**
 * The shell every page sits in.
 *
 * The header reproduces the original's: a sticky, frosted bar carrying the
 * identity block, and beneath it a row of its own for the destinations. The
 * tabs are pills of an even width that scroll sideways rather than wrapping,
 * so the bar keeps its height whichever module is open and the row never
 * reflows under the pointer — with the active one filled by the brand
 * gradient rather than a flat block.
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

const MainLayout: React.FC = () => (
    <div className="flex min-h-screen w-full flex-col bg-[#F6F7F9]">
        <header className="sticky top-0 z-20 backdrop-blur-[10px] backdrop-saturate-[180%]"
            style={{ backgroundColor: "rgba(246,247,249,.88)" }}>

            {/* Identity block, with the shortcuts glued to the right edge. */}
            <div className="mx-auto flex w-full max-w-[1400px] items-center gap-4 px-6 py-3">
                {/* Logo and name on one baseline: with no subtitle beneath,
                    anything else leaves the mark floating above the text. */}
                <img src="/forvisMazarslogo.png" alt="Forvis Mazars"
                    className="h-10 w-auto shrink-0" />
                <h1 className="min-w-0 text-[1.55rem] font-black uppercase leading-[1.15]
                               tracking-[0.03em] text-[#0A2647]">
                    Forvis Mazars Regulatory Reporting Platform
                </h1>

                <div className="ml-auto flex shrink-0 items-center gap-2">
                    <UserBadge />
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
                    <NotificationBell />
                </div>
            </div>

            {/* The destinations, on a row of their own. */}
            <nav className="mx-auto w-full max-w-[1400px] border-b px-6 pb-3 pt-1"
                style={{ borderColor: "rgba(10,38,71,.12)" }}>
                <TabScroller>
                    <NavLink to="/" end className={tabClass} style={tabStyle}>
                        Global Summary
                    </NavLink>
                    {MODULES.map((module) => (
                        <NavLink key={module.key} to={`/${module.key}/${firstStepOf(module)}`}
                            className={tabClass} style={tabStyle}>
                            {module.label}
                        </NavLink>
                    ))}
                </TabScroller>
            </nav>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">
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

export default MainLayout
