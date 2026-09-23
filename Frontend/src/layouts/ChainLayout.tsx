import { NavLink, Outlet, useLocation } from "react-router-dom"

import { REFERENCE_STEP, type ModuleNav } from "@config/navigation"

/**
 * The production chain of one regulatory module: the steps down the left as
 * a progress line, and the active step on the right.
 *
 * The chain is an order, not a menu — ingestion feeds the rules engine,
 * which feeds generation, which feeds review — so it is drawn as a line with
 * a dot per step: filled behind you, ringed where you are, hollow ahead.
 * That is the difference between knowing which page is open and knowing how
 * far through the filing you are.
 *
 * Only the rules-engine and generation steps are module-specific; ingestion
 * and controls & audit are the platform's shared layers, reused as-is across
 * every module. The regulatory reference sits below the chain rather than on
 * it — see the link at the foot of the panel.
 */
const ChainLayout: React.FC<{ module: ModuleNav }> = ({ module }) => {
    const { pathname } = useLocation()

    // Which step is open, so the ones before it can be drawn as behind you.
    // Sitting on the regulatory reference is not being on a step, so the
    // line shows no position at all rather than pointing at the first one.
    const current = module.steps.findIndex(
        (step) => pathname === `/${module.key}/${step.path}`)
    const onAStep = current !== -1
    const activeIndex = onAStep ? current : -1

    return (
        <div className="flex flex-col gap-6 lg:flex-row">
            <aside className="w-full shrink-0 lg:w-64">
                <div className="sticky top-32 rounded-lg border border-slate-200 bg-white p-4">
                    <span className="block pb-3 text-xs font-semibold uppercase tracking-wide
                                     text-slate-500">
                        Production chain
                    </span>

                    <ol className="relative flex flex-col">
                        {module.steps.map((step, index) => {
                            const done = onAStep && index < activeIndex
                            const active = index === activeIndex
                            const last = index === module.steps.length - 1

                            return (
                                <li key={step.path} className="relative flex gap-3">
                                    {/* The line joining this dot to the next. It stops at the
                                        last step so the chain does not trail into nothing. */}
                                    {!last && (
                                        <span aria-hidden="true"
                                            className={[
                                                "absolute left-[7px] top-5 h-[calc(100%-4px)] w-0.5",
                                                done ? "bg-[#1F5FA8]" : "bg-slate-200",
                                            ].join(" ")} />
                                    )}

                                    <span aria-hidden="true"
                                        className={[
                                            "relative z-10 mt-[7px] h-[15px] w-[15px] shrink-0",
                                            "rounded-full border-2 transition",
                                            active
                                                ? "border-[#1F5FA8] bg-white ring-4 ring-[#1F5FA8]/20"
                                                : done
                                                    ? "border-[#1F5FA8] bg-[#1F5FA8]"
                                                    : "border-slate-300 bg-white",
                                        ].join(" ")} />

                                    <NavLink to={`/${module.key}/${step.path}`}
                                        aria-current={active ? "step" : undefined}
                                        className={[
                                            "flex-1 rounded-md px-2 py-1.5 pb-4 text-left text-sm transition",
                                            active
                                                ? "font-semibold text-[#0A2647]"
                                                : done
                                                    ? "text-slate-700 hover:text-[#0A2647]"
                                                    : "text-slate-500 hover:text-[#0A2647]",
                                        ].join(" ")}>
                                        {step.label}
                                    </NavLink>
                                </li>
                            )
                        })}
                    </ol>

                    <p className="mt-1 border-t border-slate-100 px-2 pt-3 text-xs text-slate-500">
                        {onAStep
                            ? `Step ${activeIndex + 1} of ${module.steps.length}`
                            : `${module.steps.length} steps`} · {module.authority}
                    </p>

                    {/* The regulator's own texts sit below the chain, not on
                        it: they are consulted at any point and never
                        completed, so a progress line would report them as an
                        outstanding step forever. */}
                    <NavLink to={`/${module.key}/${REFERENCE_STEP.path}`}
                        className={({ isActive }) => [
                            "mt-2 flex items-center gap-2 rounded-md px-2 py-2 text-sm transition",
                            isActive
                                ? "bg-slate-100 font-semibold text-[#0A2647]"
                                : "text-slate-600 hover:bg-slate-50 hover:text-[#0A2647]",
                        ].join(" ")}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                            aria-hidden="true" className="shrink-0">
                            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                        </svg>
                        {REFERENCE_STEP.label}
                    </NavLink>
                </div>
            </aside>

            <div className="min-w-0 flex-1">
                <Outlet context={module} />
            </div>
        </div>
    )
}

export default ChainLayout
