import { useEffect, useRef } from "react"

/**
 * Closes a popover when the user clicks or taps outside it, or presses Escape.
 * Attach the returned ref to the element that wraps both the trigger and the
 * panel, so a click on the trigger still toggles rather than closing and
 * reopening.
 */
export function useDismiss<T extends HTMLElement>(open: boolean, close: () => void) {
    const ref = useRef<T>(null)

    useEffect(() => {
        if (!open) return
        const onPointer = (event: PointerEvent) => {
            if (ref.current && !ref.current.contains(event.target as Node)) close()
        }
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") close()
        }
        document.addEventListener("pointerdown", onPointer)
        document.addEventListener("keydown", onKey)
        return () => {
            document.removeEventListener("pointerdown", onPointer)
            document.removeEventListener("keydown", onKey)
        }
    }, [open, close])

    return ref
}
