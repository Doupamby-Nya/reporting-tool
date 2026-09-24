import { createSlice, type PayloadAction } from "@reduxjs/toolkit"

import type { Me } from "src/types/reportingType"

/**
 * Who is signed in, and which modules they can use.
 *
 * The server renders every page with this already filled in (see
 * entry-server.tsx), so the tabs a user sees are right from the first paint
 * rather than appearing once the browser has asked. `null` is a visitor.
 *
 * The API enforces the same rule on every call; this state only decides what
 * to show.
 */
export type UserState = {
    me: Me | null
}

const initialState: UserState = {
    me: null,
}

const userSlice = createSlice({
    name: "user",
    initialState,
    reducers: {
        signedIn(state, action: PayloadAction<Me>) {
            state.me = action.payload
        },
        signedOut(state) {
            state.me = null
        },
    },
})

export const { signedIn, signedOut } = userSlice.actions
export default userSlice.reducer
