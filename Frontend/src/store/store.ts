import { configureStore } from '@reduxjs/toolkit'

import chainReducer from './chainSlice'
import userReducer from './userSlice'

/**
 * The client store.
 *
 * It starts from the state the server rendered the page with (written into
 * the page by server.js as window.__PRELOADED_STATE__), so the signed-in
 * user and their tabs are the same on both sides of hydration.
 */
declare global {
    interface Window {
        __PRELOADED_STATE__?: unknown
    }
}

const preloadedState = typeof window !== 'undefined'
    ? window.__PRELOADED_STATE__ as Parameters<typeof configureStore>[0]['preloadedState']
    : undefined

export const store = configureStore({
    reducer: {
        user: userReducer,
        chains: chainReducer,
    },
    preloadedState,
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
