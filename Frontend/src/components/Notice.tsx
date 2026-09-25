import { useEffect, useId, useRef } from "react"
import type { ReactNode } from "react"

export type NoticeTone = "warning" | "info" | "error"
type Tone = NoticeTone

const GLYPHS: Record<Tone, string> = { warning: "!", info: "i", error: "!" }

/**
 * The drop both notices carry: a circle (centre 24,36, radius 16) with a tip
 * at the top, its sides the circle's tangents. On the full notice the tip
 * turns towards the pointer; on the inline one it stays still.
 */
const Drop: React.FC<{ className: string }> = ({ className }) => {
    // One gradient per drop, since ids must be unique in the document. React's
    // ids carry characters that url(#...) does not accept, so they are dropped.
    const gradient = `mz-drop-${useId().replace(/[^\w-]/g, "")}`
    return (
        <svg viewBox="0 0 48 56" className={className}>
            <defs>
                <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" className="mz-beacon-stop-a" />
                    <stop offset="1" className="mz-beacon-stop-b" />
                </linearGradient>
            </defs>
            <path d="M24 3 L38.12 28.47 A16 16 0 1 1 9.88 28.47 Z"
                fill={`url(#${gradient})`} stroke="#fff" strokeWidth="3"
                strokeLinejoin="round" />
        </svg>
    )
}

type NoticeProps = {
    tone?: Tone
    eyebrow?: string
    title: string
    children?: ReactNode
    /** Buttons or links, laid out under the message. */
    actions?: ReactNode
    className?: string
}

/**
 * A notice that belongs to the page rather than interrupting it.
 *
 * Three things carry the message without resorting to a flat yellow box:
 * a beacon sits on the card's top edge and turns its tip towards the
 * pointer wherever it is on the page; the card tilts a few degrees under the
 * pointer, lit by a soft sheen, so it reads as an object rather than a strip
 * of colour; and a hatched spine, in the corporate navy and the warning
 * amber, marks it as something to act on. Everything moves through CSS
 * variables written from a single animation frame, so the pointer never
 * causes a React render. When the system asks for less motion, the card
 * stays flat and only the beacon keeps turning.
 */
const Notice: React.FC<NoticeProps> = ({ tone = "warning", eyebrow, title, children, actions, className }) => {
    const cardRef = useRef<HTMLDivElement>(null)
    const beaconRef = useRef<HTMLSpanElement>(null)

    useEffect(() => {
        const card = cardRef.current
        const beacon = beaconRef.current
        if (!card || !beacon) return
        // The beacon only ever answers the user's own pointer, so it keeps
        // following it when the system asks for less motion (Windows Server
        // asks by default). The tilt is parallax, which is what that setting
        // is for, so it stays flat then.
        const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches

        let frame = 0
        let pointer: { x: number; y: number } | null = null
        // Unwrapped, so crossing straight down turns the short way round
        // instead of spinning a full turn from 179deg to -179deg.
        let aim = 0

        const paint = () => {
            frame = 0
            if (!pointer) return
            // The beacon's tip points at the pointer: 0deg is straight up.
            // It turns around its circle's centre, 64.29% down the shape.
            const b = beacon.getBoundingClientRect()
            const angle = Math.atan2(pointer.x - (b.left + b.width / 2),
                                     (b.top + b.height * 0.6429) - pointer.y) * 180 / Math.PI
            aim += ((angle - aim) % 360 + 540) % 360 - 180
            beacon.style.setProperty("--mz-aim", `${aim.toFixed(1)}deg`)

            if (still) return

            // The card only tilts while the pointer is over it.
            const c = card.getBoundingClientRect()
            const inside = pointer.x >= c.left && pointer.x <= c.right
                && pointer.y >= c.top && pointer.y <= c.bottom
            const px = inside ? (pointer.x - c.left) / c.width - 0.5 : 0
            const py = inside ? (pointer.y - c.top) / c.height - 0.5 : 0
            card.style.setProperty("--mz-tilt-x", `${(-py * 5).toFixed(2)}deg`)
            card.style.setProperty("--mz-tilt-y", `${(px * 7).toFixed(2)}deg`)
            card.style.setProperty("--mz-sheen-x", `${((px + 0.5) * 100).toFixed(1)}%`)
            card.style.setProperty("--mz-sheen-y", `${((py + 0.5) * 100).toFixed(1)}%`)
            card.dataset.lit = inside ? "1" : ""
        }

        const onMove = (event: PointerEvent) => {
            pointer = { x: event.clientX, y: event.clientY }
            if (!frame) frame = requestAnimationFrame(paint)
        }
        const onScroll = () => { if (pointer && !frame) frame = requestAnimationFrame(paint) }

        window.addEventListener("pointermove", onMove, { passive: true })
        window.addEventListener("scroll", onScroll, { passive: true, capture: true })
        return () => {
            window.removeEventListener("pointermove", onMove)
            window.removeEventListener("scroll", onScroll, { capture: true })
            if (frame) cancelAnimationFrame(frame)
        }
    }, [])

    return (
        <div className={["mz-notice-stage", className ?? ""].join(" ")}>
            <div ref={cardRef} role={tone === "info" ? "status" : "alert"}
                className={`mz-notice mz-notice--${tone}`}>
                <span ref={beaconRef} className="mz-notice-beacon" aria-hidden="true">
                    <Drop className="mz-notice-beacon-shape" />
                    <span className="mz-notice-glyph">{GLYPHS[tone]}</span>
                </span>

                <span className="mz-notice-spine" aria-hidden="true" />
                <span className="mz-notice-sheen" aria-hidden="true" />

                <div className="relative flex flex-col gap-2 py-5 pl-9 pr-6 pt-8">
                    {eyebrow && <p className="mz-notice-eyebrow">{eyebrow}</p>}
                    <p className="text-base font-semibold text-[#0A2647]">{title}</p>
                    {children && <div className="max-w-2xl text-sm leading-relaxed text-slate-600">{children}</div>}
                    {actions && <div className="mt-2 flex flex-wrap items-center gap-3">{actions}</div>}
                </div>
            </div>
        </div>
    )
}

/**
 * The same notice, sized for a line of text: for a warning inside a form, a
 * finding in a list of controls, or one problem among several. It keeps the
 * card's material (hatched spine, dotted paper, the drop, a slab of
 * thickness) but neither tilts nor follows the pointer, so a list of fifteen
 * reads as a list rather than fifteen alarms.
 */
export const InlineNotice: React.FC<{ tone?: Tone; children: ReactNode; className?: string }> = (
    { tone = "warning", children, className }) => (
    <div className={`mz-notice mz-notice--inline mz-notice--${tone} ${className ?? ""}`}>
        <span className="mz-notice-spine" aria-hidden="true" />
        <span className="mz-notice-drop" aria-hidden="true">
            <Drop className="h-full w-full" />
            <span className="mz-notice-glyph">{GLYPHS[tone]}</span>
        </span>
        <div className="min-w-0 flex-1 text-sm leading-snug text-slate-700">{children}</div>
    </div>
)

/** A list of messages inside a full notice: one beacon for the group. */
export const NoticeList: React.FC<{ items: ReactNode[]; more?: number }> = ({ items, more }) => (
    <ul className="mz-notice-list">
        {items.map((item, index) => <li key={index}>{item}</li>)}
        {!!more && <li className="mz-notice-list-more">…and {more} more.</li>}
    </ul>
)

export default Notice
