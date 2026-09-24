import { Link } from "react-router-dom"
import { FiArrowRight, FiCheckCircle, FiLock, FiPlayCircle } from "react-icons/fi"

import ModuleLogo from "@components/ModuleLogo"
import { PITCHES, PROMISES, STEP_HELP } from "@config/catalogue"
import { MODULES } from "@config/navigation"
import { useCurrentUser } from "@hooks/useCurrentUser"

/**
 * The public home page: what the platform does, module by module, for a
 * visitor deciding whether to subscribe — and, for a signed-in user, the way
 * into the modules they have.
 *
 * One long page to scroll, sparse on purpose: a headline, the modules as
 * cards, how a filing goes through, the demo video, and what the platform
 * guarantees. Figures about filings belong on the dashboard, not here.
 */

const DEMO_VIDEO_URL = import.meta.env.VITE_DEMO_VIDEO_URL as string | undefined
const CONTACT_EMAIL = import.meta.env.VITE_CONTACT_EMAIL as string | undefined

const CHAIN = ["ingestion", "rules", "generation", "preview", "controls"] as const
const CHAIN_LABELS: Record<(typeof CHAIN)[number], string> = {
    ingestion: "Ingestion", rules: "Rules engine", generation: "Generation",
    preview: "Preview", controls: "Four-eyes review",
}

const GRADIENT = "linear-gradient(135deg, #061a33 0%, #0A2647 45%, #1F5FA8 100%)"

const Home: React.FC = () => {
    const { me, canUse, modules } = useCurrentUser()

    const primaryCta = me
        ? modules.length > 0
            ? <Link to="/dashboard" className="rounded-full bg-white px-7 py-3 text-sm font-bold text-[#0A2647] transition hover:bg-slate-100">Open my dashboard</Link>
            : <Link to="/guide" className="rounded-full bg-white px-7 py-3 text-sm font-bold text-[#0A2647] transition hover:bg-slate-100">Discover the platform</Link>
        : <Link to="/login" className="rounded-full bg-white px-7 py-3 text-sm font-bold text-[#0A2647] transition hover:bg-slate-100">Sign in</Link>

    return (
        <div className="flex flex-col">
            {/* Headline */}
            <section className="relative overflow-hidden px-6 py-20 text-white sm:py-28" style={{ background: GRADIENT }}>
                <HexagonPattern />
                <div className="relative mx-auto flex max-w-4xl flex-col items-center gap-6 text-center">
                    <span className="rounded-full border border-white/25 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/80">
                        Forvis Mazars · Luxembourg
                    </span>
                    <h1 className="text-4xl font-black uppercase leading-tight tracking-tight sm:text-6xl">
                        Regulatory reporting,<br />checked before it is filed.
                    </h1>
                    <p className="max-w-2xl text-lg text-white/85">
                        Eight regulatory regimes for management companies and their funds — prepared from
                        your data, validated against each regulator's own rules and schema, reviewed by a
                        second pair of eyes.
                    </p>
                    <div className="flex flex-wrap justify-center gap-3 pt-2">
                        {primaryCta}
                        <a href="#modules" className="rounded-full border border-white/60 px-7 py-3 text-sm font-bold text-white transition hover:bg-white/10">
                            Explore the modules
                        </a>
                    </div>
                </div>
            </section>

            {/* Modules */}
            <section id="modules" className="scroll-mt-32 bg-white px-6 py-20">
                <div className="mx-auto max-w-[1200px]">
                    <SectionHeading kicker="The modules" title="One platform, eight regulators."
                        text="Each module is subscribed to on its own. Start with the one you need; add the others when you are ready." />
                    <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                        {MODULES.map((module) => {
                            const pitch = PITCHES[module.key]
                            const open = canUse(module.key)
                            return (
                                <article key={module.key}
                                    className="group flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                                    <div className="flex items-center gap-3">
                                        <ModuleLogo moduleKey={module.key} size={52} />
                                        <div>
                                            <h3 className="text-lg font-extrabold text-[#0A2647]">{module.label}</h3>
                                            <p className="text-xs font-medium text-slate-500">{module.authority}</p>
                                        </div>
                                    </div>
                                    <p className="text-sm leading-relaxed text-slate-700">{pitch?.pitch}</p>
                                    <ul className="flex flex-1 flex-col gap-1.5">
                                        {pitch?.highlights.map((item) => (
                                            <li key={item} className="flex gap-2 text-xs text-slate-600">
                                                <FiCheckCircle className="mt-0.5 shrink-0" style={{ color: pitch.color }} aria-hidden="true" />
                                                {item}
                                            </li>
                                        ))}
                                    </ul>
                                    {open ? (
                                        <Link to={`/${module.key}`} className="mt-2 inline-flex items-center gap-1.5 text-sm font-bold" style={{ color: pitch?.color }}>
                                            Open the module <FiArrowRight aria-hidden="true" />
                                        </Link>
                                    ) : (
                                        <span className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400">
                                            <FiLock aria-hidden="true" /> Available on subscription
                                        </span>
                                    )}
                                </article>
                            )
                        })}
                    </div>
                </div>
            </section>

            {/* How a filing goes through */}
            <section className="bg-[#F6F7F9] px-6 py-20">
                <div className="mx-auto max-w-[1200px]">
                    <SectionHeading kicker="How it works" title="The same five steps, whatever the regulator."
                        text="One production chain for every module: that is what lets a single control layer serve eight regimes." />
                    <ol className="mt-12 grid gap-4 md:grid-cols-5">
                        {CHAIN.map((step, index) => (
                            <li key={step} className="relative flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm">
                                <span className="flex h-10 w-10 items-center justify-center rounded-full text-base font-black text-white" style={{ background: GRADIENT }}>
                                    {index + 1}
                                </span>
                                <h3 className="text-sm font-extrabold uppercase tracking-wide text-[#0A2647]">{CHAIN_LABELS[step]}</h3>
                                <p className="text-xs leading-relaxed text-slate-600">{STEP_HELP[step]}</p>
                            </li>
                        ))}
                    </ol>
                </div>
            </section>

            {/* Demo */}
            <section id="demo" className="scroll-mt-32 bg-white px-6 py-20">
                <div className="mx-auto max-w-[1000px]">
                    <SectionHeading kicker="Demo" title="See a filing go through."
                        text="A few minutes, from the workbook to the approved filing." />
                    <div className="mt-10 overflow-hidden rounded-2xl shadow-[0_0_0_4px_rgba(31,95,168,.15),0_30px_60px_-20px_rgba(10,38,71,.45)]">
                        {DEMO_VIDEO_URL ? (
                            <div className="relative aspect-video w-full bg-slate-800">
                                <iframe src={DEMO_VIDEO_URL} title="Platform demonstration"
                                    className="absolute inset-0 h-full w-full" loading="lazy"
                                    allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />
                            </div>
                        ) : (
                            <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 text-white" style={{ background: GRADIENT }}>
                                <FiPlayCircle size={72} aria-hidden="true" className="opacity-90" />
                                <p className="text-lg font-bold">The demonstration video is on its way.</p>
                            </div>
                        )}
                    </div>
                    <p className="mt-4 text-center text-sm text-slate-500">
                        Video blocked on your network? The <Link to="/guide" className="font-semibold text-[#1F5FA8] underline">user guide</Link> walks
                        through the same steps without it.
                    </p>
                </div>
            </section>

            {/* Promises */}
            <section className="px-6 py-20 text-white" style={{ background: GRADIENT }}>
                <div className="mx-auto max-w-[1200px]">
                    <h2 className="text-center text-3xl font-black uppercase tracking-tight sm:text-4xl">
                        File faster. Stay compliant. Keep the evidence.
                    </h2>
                    <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                        {PROMISES.map((promise) => (
                            <div key={promise.title} className="rounded-2xl border border-white/15 bg-white/5 p-6 backdrop-blur-sm">
                                <h3 className="text-base font-extrabold">{promise.title}</h3>
                                <p className="mt-2 text-sm leading-relaxed text-white/80">{promise.text}</p>
                            </div>
                        ))}
                    </div>
                    <div className="mt-12 flex flex-wrap justify-center gap-3">
                        {!me && primaryCta}
                        {CONTACT_EMAIL ? (
                            <a href={`mailto:${CONTACT_EMAIL}?subject=Regulatory%20Reporting%20Platform%20%E2%80%94%20access%20request`}
                                className="rounded-full border border-white/60 px-7 py-3 text-sm font-bold text-white transition hover:bg-white/10">
                                Request access
                            </a>
                        ) : (
                            <p className="text-sm text-white/75">To subscribe, contact your Forvis Mazars representative.</p>
                        )}
                    </div>
                </div>
            </section>
        </div>
    )
}

const SectionHeading: React.FC<{ kicker: string; title: string; text: string }> = ({ kicker, title, text }) => (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
        <span className="text-xs font-bold uppercase tracking-[0.25em] text-[#1F5FA8]">{kicker}</span>
        <h2 className="text-3xl font-black tracking-tight text-[#0A2647] sm:text-4xl">
            {title.replace(/\.$/, "")}<span className="text-[#1F5FA8]">.</span>
        </h2>
        <p className="text-base text-slate-600">{text}</p>
    </div>
)

/** The faint lattice behind the headline. */
const HexagonPattern: React.FC = () => (
    <svg aria-hidden="true" className="absolute inset-0 h-full w-full opacity-[0.07]">
        <defs>
            <pattern id="hex" width="56" height="97" patternUnits="userSpaceOnUse" patternTransform="scale(1.2)">
                <path d="M28 0 L56 16 L56 48 L28 64 L0 48 L0 16 Z M28 64 L28 97" fill="none" stroke="#ffffff" strokeWidth="1.2" />
            </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hex)" />
    </svg>
)

export default Home
