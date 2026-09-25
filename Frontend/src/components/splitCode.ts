/**
 * The regulators' field labels arrive as "4010 — CSSF code of the unit/share
 * class": the item code, a dash, the wording. The API keeps them that way
 * (the workbooks and the Streamlit parity depend on it); the screen shows the
 * code as a quiet monospace token and the wording on its own.
 */
const CODE_PREFIX = /^\s*([\w.-]+)\s+[—–]\s+(.+)$/s

export function splitCode(label: string): { code: string | null; text: string } {
    const match = CODE_PREFIX.exec(label)
    return match ? { code: match[1], text: match[2] } : { code: null, text: label }
}
