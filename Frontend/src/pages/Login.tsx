import { useState } from "react"
import { useDispatch } from "react-redux"
import { Link, useNavigate, useSearchParams } from "react-router-dom"

import { signIn } from "@api/reportingApi"
import type { AppDispatch } from "@store/store"
import { signedIn } from "@store/userSlice"

/**
 * Signing in with a platform account.
 *
 * Microsoft sign-in is shown but not wired yet: internal users will use it
 * once the Azure app registration exists, and the button says so rather
 * than failing when pressed.
 */

/** Only a path inside the platform, so the page cannot be used to send
 *  someone to another site after they sign in. */
const safeNext = (value: string | null): string | null =>
    value && value.startsWith("/") && !value.startsWith("//") ? value : null

const Login: React.FC = () => {
    const dispatch = useDispatch<AppDispatch>()
    const navigate = useNavigate()
    const [params] = useSearchParams()
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const [busy, setBusy] = useState(false)

    const submit = async (event: React.FormEvent) => {
        event.preventDefault()
        setBusy(true)
        setError("")
        try {
            const me = await signIn(email, password)
            dispatch(signedIn(me))
            navigate(safeNext(params.get("next")) ?? (me.modules.length > 0 ? "/dashboard" : "/"), { replace: true })
        } catch (failure) {
            setError((failure as Error).message)
        } finally {
            setBusy(false)
        }
    }

    const field = "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#0A2647] focus:ring-2 focus:ring-[#1F5FA8]/20"

    return (
        <section className="flex justify-center py-10">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
                <h1 className="text-2xl font-black text-[#0A2647]">Sign in</h1>
                <p className="mt-1 text-sm text-slate-600">
                    Your modules appear once you are signed in.
                </p>

                <button type="button" disabled
                    title="Available once the platform is registered with Microsoft Entra ID"
                    className="mt-6 flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-400">
                    <svg width="18" height="18" viewBox="0 0 23 23" aria-hidden="true">
                        <path fill="#f25022" d="M1 1h10v10H1z" /><path fill="#7fba00" d="M12 1h10v10H12z" />
                        <path fill="#00a4ef" d="M1 12h10v10H1z" /><path fill="#ffb900" d="M12 12h10v10H12z" />
                    </svg>
                    Sign in with Microsoft — coming soon
                </button>

                <div className="my-6 flex items-center gap-3 text-xs text-slate-400">
                    <span className="h-px flex-1 bg-slate-200" /> or with your platform account <span className="h-px flex-1 bg-slate-200" />
                </div>

                <form onSubmit={submit} className="flex flex-col gap-4">
                    <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
                        Email
                        <input type="email" autoComplete="username" required value={email}
                            onChange={(event) => setEmail(event.target.value)} className={field} />
                    </label>
                    <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
                        Password
                        <input type="password" autoComplete="current-password" required value={password}
                            onChange={(event) => setPassword(event.target.value)} className={field} />
                    </label>
                    {error && (
                        <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
                    )}
                    <button type="submit" disabled={busy}
                        className="rounded-lg bg-[#0A2647] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#123A6B] disabled:opacity-50">
                        {busy ? "Signing in…" : "Sign in"}
                    </button>
                </form>

                <p className="mt-6 text-xs text-slate-500">
                    No account yet? Accounts are opened by your administrator once your organisation has
                    subscribed. Meanwhile, the <Link to="/guide" className="font-semibold text-[#1F5FA8] underline">user guide</Link> shows
                    what the platform does.
                </p>
            </div>
        </section>
    )
}

export default Login
