import { useCallback, useEffect, useRef, useState } from "react"

/**
 * The destination bar, with the arrows that appear only when it overflows.
 *
 * Nine destinations do not fit on a laptop, and a row that scrolls with no
 * visible handle reads as a row that has been cut off. So the arrows appear
 * when there is something past the edge and disappear when there is not,
 * and each is disabled at its own end rather than scrolling into nothing.
 *
 * The overflow is measured rather than assumed: it depends on the window,
 * the font and how many modules exist, none of which this component should
 * be guessing at.
 */
const STEP = 220

const TabScroller: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const track = useRef<HTMLDivElement>(null)
    const [atStart, setAtStart] = useState(true)
    const [atEnd, setAtEnd] = useState(true)

    const measure = useCallback(() => {
        const element = track.current
        if (!element) return
        const overflow = element.scrollWidth - element.clientWidth
        // A couple of pixels of slack: sub-pixel layout rounding otherwise
        // leaves an arrow enabled with nothing to scroll to.
        setAtStart(element.scrollLeft <= 2)
        setAtEnd(overflow <= 2 || element.scrollLeft >= overflow - 2)
    }, [])

    useEffect(() => {
        measure()
        const element = track.current
        if (!element) return

        element.addEventListener("scroll", measure, { passive: true })
        window.addEventListener("resize", measure)

        // The tabs are laid out after the fonts load, which changes the
        // width — so the bar is watched rather than measured once.
        const observer = typeof ResizeObserver === "undefined"
            ? null
            : new ResizeObserver(measure)
        observer?.observe(element)

        return () => {
            element.removeEventListener("scroll", measure)
            window.removeEventListener("resize", measure)
            observer?.disconnect()
        }
    }, [measure])

    const scroll = (direction: -1 | 1) =>
        track.current?.scrollBy({ left: direction * STEP, behavior: "smooth" })

    // Nothing overflows: no arrows at all, rather than two dead ones.
    const overflowing = !(atStart && atEnd)

    const arrow = "flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full " +
        "border border-slate-200 bg-white text-slate-500 shadow-sm transition-all duration-200 " +
        "hover:-translate-y-0.5 hover:border-transparent hover:text-white " +
        "disabled:pointer-events-none disabled:opacity-35 disabled:shadow-none"

    const hoverFill = { "--tw-shadow": "0 2px 5px rgba(15,23,42,.06)" } as React.CSSProperties

    return (
        <div className="flex items-center gap-2">
            {overflowing && (
                <button type="button" onClick={() => scroll(-1)} disabled={atStart}
                    aria-label="Show the previous destinations"
                    className={`${arrow} hover:bg-[#0A2647]`} style={hoverFill}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M15 18l-6-6 6-6" />
                    </svg>
                </button>
            )}

            <div ref={track} className="mz-tabs flex flex-1 items-center gap-2 overflow-x-auto pb-1.5 pt-1">
                {children}
            </div>

            {overflowing && (
                <button type="button" onClick={() => scroll(1)} disabled={atEnd}
                    aria-label="Show the next destinations"
                    className={`${arrow} hover:bg-[#0A2647]`} style={hoverFill}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M9 18l6-6-6-6" />
                    </svg>
                </button>
            )}
        </div>
    )
}

export default TabScroller
