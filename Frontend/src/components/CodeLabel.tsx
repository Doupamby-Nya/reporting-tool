import { splitCode } from "@components/splitCode"

/** A regulator's field label, with its item code as a quiet monospace token. */
const CodeLabel: React.FC<{ label: string }> = ({ label }) => {
    const { code, text } = splitCode(label)
    return (
        <>
            {code && <code className="mr-2 font-mono text-xs text-slate-500">{code}</code>}
            {text}
        </>
    )
}

export default CodeLabel
