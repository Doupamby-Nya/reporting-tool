/**
 * Calendar days travel as "YYYY-MM-DD" and are handled at UTC midnight, so
 * the browser's own time zone can never move one onto its neighbour. The API
 * has already counted them in the viewer's zone.
 */
export const DAY_MS = 86_400_000

export const parseDay = (iso: string) => {
    const [year, month, day] = iso.split("-").map(Number)
    return new Date(Date.UTC(year, month - 1, day))
}

export const isoDay = (date: Date) => date.toISOString().slice(0, 10)

/** Monday is 0: the week starts where it does in Luxembourg. */
export const weekdayOf = (date: Date) => (date.getUTCDay() + 6) % 7

export const longDay = (iso: string) =>
    parseDay(iso).toLocaleDateString("en-GB", {
        weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
    })

export const shortDay = (iso: string) =>
    parseDay(iso.slice(0, 10)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" })

export const monthName = (month: string) =>
    parseDay(`${month}-01`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })

/** "3 hours ago", "yesterday", "12 Sep": how long since a moment. */
export function sinceWhen(moment: string, now = Date.now()): string {
    const then = new Date(moment).getTime()
    const minutes = Math.round((now - then) / 60_000)
    if (minutes < 1) return "just now"
    if (minutes < 60) return `${minutes} min ago`
    const hours = Math.round(minutes / 60)
    if (hours < 24) return `${hours} h ago`
    const days = Math.round(hours / 24)
    if (days === 1) return "yesterday"
    if (days < 7) return `${days} days ago`
    return shortDay(moment)
}
