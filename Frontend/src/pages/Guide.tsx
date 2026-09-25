import { useState } from "react"
import { Link } from "react-router-dom"
import {
    FiAlertTriangle, FiCheckCircle, FiCpu, FiDownload, FiEye, FiFileText, FiSend, FiSettings,
    FiShield, FiUploadCloud,
} from "react-icons/fi"
import type { IconType } from "react-icons"

import ModuleLogo from "@components/ModuleLogo"
import PageTitle from "@components/PageTitle"
import { PITCHES, STEP_HELP } from "@config/catalogue"
import { MODULES, type ModuleNav } from "@config/navigation"
import { useCurrentUser } from "@hooks/useCurrentUser"

/**
 * The user guide, in two forms.
 *
 * A visitor, or a user without a subscription, sees what the platform can do:
 * one card per module, and the chain every filing goes through — enough to
 * understand it without the demo video, which some networks block.
 *
 * A subscriber sees, for each of their modules, the steps in order with what
 * to do at each one. The module's own pages already show the details; the
 * guide only says what comes next and why.
 */

const STEP_ICONS: Record<string, IconType> = {
    ingestion: FiUploadCloud, engine: FiCpu, rules: FiShield, generation: FiFileText,
    preview: FiEye, notification: FiSend, controls: FiCheckCircle, configuration: FiSettings,
}

const CHAIN_LABELS: Record<string, string> = {
    ingestion: "Ingestion", rules: "Rules engine", generation: "Generation",
    preview: "Preview", controls: "Four-eyes review",
}

const REGISTER_LIMIT = "Schema validation proves a filing is well-formed. The checks a regulator runs against its "
    + "own register, such as whether an entity code exists or a period was already filed, cannot be "
    + "reproduced here and remain the preparer's responsibility."

const Guide: React.FC = () => {
    const { modules } = useCurrentUser()
    return modules.length > 0 ? <SubscriberGuide modules={modules} /> : <PublicGuide />
}

const SubscriberGuide: React.FC<{ modules: ModuleNav[] }> = ({ modules }) => {
    const [selected, setSelected] = useState(modules[0].key)
    const module = modules.find((candidate) => candidate.key === selected) ?? modules[0]
    const pitch = PITCHES[module.key]

    return (
        <section className="flex flex-col gap-6">
            <PageTitle title="User guide" subtitle="Your modules, step by step." />

            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Your modules">
                {modules.map((candidate) => (
                    <button key={candidate.key} type="button" role="tab" aria-selected={candidate.key === module.key}
                        onClick={() => setSelected(candidate.key)}
                        className={[
                            "flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-semibold transition",
                            candidate.key === module.key
                                ? "border-transparent bg-[#0A2647] text-white"
                                : "border-slate-200 bg-white text-[#123A6B] hover:border-[#0A2647]",
                        ].join(" ")}>
                        {candidate.label}
                    </button>
                ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
                <ol className="flex flex-col gap-3">
                    {module.steps.map((step, index) => {
                        const Icon = STEP_ICONS[step.path] ?? FiFileText
                        return (
                            <li key={step.path} className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-5">
                                <div className="flex flex-col items-center gap-2">
                                    <span className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-black text-white"
                                        style={{ background: pitch?.color ?? "#0A2647" }}>
                                        {index + 1}
                                    </span>
                                </div>
                                <div className="flex flex-1 flex-col gap-1">
                                    <div className="flex items-center gap-2">
                                        <Icon className="text-slate-500" aria-hidden="true" />
                                        <h2 className="text-sm font-extrabold uppercase tracking-wide text-[#0A2647]">{step.label}</h2>
                                    </div>
                                    <p className="text-sm leading-relaxed text-slate-700">{STEP_HELP[step.path]}</p>
                                    <Link to={`/${module.key}/${step.path}`} className="w-fit text-xs font-bold text-[#1F5FA8] hover:underline">
                                        Go to this step →
                                    </Link>
                                </div>
                            </li>
                        )
                    })}
                </ol>

                <aside className="flex flex-col gap-4">
                    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-5">
                        <div className="flex items-center gap-3">
                            <ModuleLogo moduleKey={module.key} size={44} />
                            <div>
                                <p className="font-extrabold text-[#0A2647]">{module.title}</p>
                                <p className="text-xs text-slate-500">{module.authority}</p>
                            </div>
                        </div>
                        <p className="text-sm text-slate-700">{pitch?.pitch}</p>
                        <Link to={`/${module.key}/regulation`} className="flex items-center gap-2 text-xs font-bold text-[#1F5FA8] hover:underline">
                            <FiDownload aria-hidden="true" /> The regulator's texts
                        </Link>
                    </div>
                    <Limits limitation={pitch?.limitation} />
                </aside>
            </div>
        </section>
    )
}

const PublicGuide: React.FC = () => {
    const { me } = useCurrentUser()
    return (
        <section className="flex flex-col gap-10">
            <PageTitle title="User guide"
                subtitle="What the platform does, module by module, and how a filing goes through it." />

            <div className="grid gap-5 md:grid-cols-2">
                {MODULES.map((module) => {
                    const pitch = PITCHES[module.key]
                    return (
                        <article key={module.key} className="flex gap-5 rounded-2xl bg-[#1f2a37] p-6 text-white shadow-sm">
                            <ModuleLogo moduleKey={module.key} size={56} />
                            <div className="flex flex-col gap-2">
                                <h2 className="text-lg font-extrabold uppercase tracking-wide">{module.title}</h2>
                                <p className="text-sm text-white/80">{pitch?.pitch}</p>
                                <ul className="mt-1 flex flex-col gap-1">
                                    {pitch?.highlights.map((item) => (
                                        <li key={item} className="flex gap-2 text-sm text-white/90">
                                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: pitch.color === "#0A2647" ? "#5B9BE0" : pitch.color }} />
                                            {item}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </article>
                    )
                })}
            </div>

            <section className="flex flex-col gap-4">
                <h2 className="text-xl font-black text-[#0A2647]">Every filing goes through the same chain</h2>
                <ol className="grid gap-3 md:grid-cols-5">
                    {(["ingestion", "rules", "generation", "preview", "controls"] as const).map((path, index) => {
                        const Icon = STEP_ICONS[path]
                        return (
                            <li key={path} className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-4">
                                <span className="text-xs font-bold uppercase tracking-widest text-[#1F5FA8]">Step {index + 1}</span>
                                <Icon size={22} className="text-[#0A2647]" aria-hidden="true" />
                                <h3 className="text-sm font-extrabold uppercase tracking-wide text-[#0A2647]">{CHAIN_LABELS[path]}</h3>
                                <p className="text-xs leading-relaxed text-slate-600">{STEP_HELP[path]}</p>
                            </li>
                        )
                    })}
                </ol>
            </section>

            <Limits />

            <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-[#0A2647] p-6 text-white">
                <p className="flex-1 text-sm">
                    {me
                        ? "Your account has no module yet. Ask your administrator to open the ones your organisation subscribes to."
                        : "Each module is subscribed to on its own. Already have an account?"}
                </p>
                {!me && (
                    <Link to="/login" className="rounded-full bg-white px-6 py-2 text-sm font-bold text-[#0A2647]">Sign in</Link>
                )}
            </div>
        </section>
    )
}

const Limits: React.FC<{ limitation?: string }> = ({ limitation }) => (
    <div className="flex flex-col gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        <p className="flex items-center gap-2 font-bold"><FiAlertTriangle aria-hidden="true" /> Good to know</p>
        {limitation && <p>{limitation}</p>}
        <p>{REGISTER_LIMIT}</p>
    </div>
)

export default Guide
