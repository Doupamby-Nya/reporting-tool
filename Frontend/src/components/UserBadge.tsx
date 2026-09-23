import { useCurrentUser } from "@hooks/useCurrentUser"

/**
 * The preparer's name, entered once and reused by every page.
 *
 * It sits in the header because it is what the audit trail signs each
 * generation and each review step with — a filing that cannot say who
 * produced it fails the four-eyes control it exists to support.
 */
const UserBadge: React.FC = () => {
    const { name, setName } = useCurrentUser()
    return (
        <label className="flex items-center gap-2 text-xs text-slate-600">
            <span className="whitespace-nowrap">Preparer</span>
            <input value={name} onChange={(e) => setName(e.target.value)}
                placeholder="your name"
                className={[
                    "w-36 rounded-md border px-2 py-1 text-sm outline-none focus:border-[#0A2647]",
                    name ? "border-slate-300" : "border-amber-400 bg-amber-50",
                ].join(" ")} />
        </label>
    )
}

export default UserBadge
