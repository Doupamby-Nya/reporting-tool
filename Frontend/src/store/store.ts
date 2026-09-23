import { configureStore } from '@reduxjs/toolkit'

import chainReducer from './chainSlice'
import userReducer from './userSlice'

/**
 * The client store.
 *
 * Redux rejects an empty `reducer` object — it warns on every render that the
 * store has no valid reducer — so the store carries the state the app
 * actually shares: who is preparing the filing, which every audit entry is
 * written against.
 */

// Ensure client store matches server initial state to prevent hydration mismatches

export const store = configureStore({
    reducer: {
        user: userReducer,
        chains: chainReducer,
    },
})



export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
