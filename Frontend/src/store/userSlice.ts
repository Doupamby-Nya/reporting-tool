import { createSlice, type PayloadAction } from "@reduxjs/toolkit"

/**
 * Who is preparing a filing.
 *
 * Every generation and every review step is written to the audit trail
 * against this name, so it is the one piece of state the whole app shares.
 * It is held here rather than passed down because three unrelated pages need
 * it, and because it is where a real identity will land once the platform
 * has authentication — today it is typed in, which is exactly what the audit
 * trail's "who approved this" column depends on.
 */
export type UserState = {
    name: string
}

const initialState: UserState = {
    name: "",
}

const userSlice = createSlice({
    name: "user",
    initialState,
    reducers: {
        setUser(state, action: PayloadAction<string>) {
            state.name = action.payload.trim()
        },
    },
})

export const { setUser } = userSlice.actions
export default userSlice.reducer
