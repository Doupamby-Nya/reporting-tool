import { useDispatch, useSelector } from "react-redux"

import type { AppDispatch, RootState } from "@store/store"
import { setUser } from "@store/userSlice"

/**
 * Who the audit trail records against.
 *
 * Until the platform has authentication this is typed in and kept in the
 * store, so every page writes the same name and a preparer only enters it
 * once. `name` is empty until they do, which is what lets a page refuse to
 * generate rather than silently signing a filing as nobody.
 */
export function useCurrentUser() {
    const name = useSelector((state: RootState) => state.user.name)
    const dispatch = useDispatch<AppDispatch>()
    return {
        name,
        setName: (value: string) => dispatch(setUser(value)),
    }
}
