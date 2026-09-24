import { useDispatch, useSelector } from "react-redux"

import { signOut } from "@api/reportingApi"
import { MODULES, type ModuleNav } from "@config/navigation"
import type { AppDispatch, RootState } from "@store/store"
import { signedOut } from "@store/userSlice"

/**
 * The signed-in account, and the modules it can use, in navigation order.
 *
 * `me` is null for a visitor. `modules` is what the tabs, the dashboard and
 * the guide are built from; the API applies the same rule to every call.
 */
export function useCurrentUser() {
    const me = useSelector((state: RootState) => state.user.me)
    const dispatch = useDispatch<AppDispatch>()

    const granted = new Set(me?.modules.map((grant) => grant.key) ?? [])
    const modules: ModuleNav[] = MODULES.filter((module) => granted.has(module.key))

    return {
        me,
        modules,
        canUse: (key: string) => granted.has(key),
        validUntil: (key: string) => me?.modules.find((grant) => grant.key === key)?.valid_until ?? null,
        signOut: async () => {
            try {
                await signOut()
            } finally {
                dispatch(signedOut())
            }
        },
    }
}
