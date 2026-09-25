import { renderToString } from 'react-dom/server'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

import './main.css'

import { StaticRouter } from "react-router-dom/server";
import { ToastContainer } from 'react-toastify'
import SSRRouter from './routes/SSRRouter'
import chainReducer from './store/chainSlice'
import userReducer from './store/userSlice'
import type { ApiEnvelope, Me } from './types/reportingType'

/**
 * Who the browser is signed in as, asked of the API with the browser's own
 * cookie. The page is rendered for that user — their tabs, their home page —
 * and the answer is handed to the client store, so hydration starts from the
 * same state rather than flashing the visitor's page first.
 *
 * SSR_BACKEND_URL is for deployments where the server reaches the API at an
 * address the browser does not use (a container network, say).
 */
async function fetchMe(cookie: string | undefined): Promise<Me | null> {
  if (!cookie || !cookie.includes('rr_session=')) return null
  const base = process.env.SSR_BACKEND_URL || import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
  try {
    const response = await fetch(`${base.replace(/\/$/, '')}/auth/me`, { headers: { cookie } })
    if (!response.ok) return null
    const body = await response.json() as ApiEnvelope<Me>
    return body.success ? body.result ?? null : null
  } catch {
    return null
  }
}

export async function render(url: string, cookie?: string) {
  // A fresh store for each request. The reducer map has to match the client
  // store in src/store/store.ts: the client hydrates into this markup.
  const store = configureStore({
    reducer: {
      user: userReducer,
      chains: chainReducer,
    },
    preloadedState: { user: { me: await fetchMe(cookie) } },
  })

  const html = renderToString(
      <Provider store={store}>
        <StaticRouter location={url}>
          <SSRRouter />
        </StaticRouter>
        {/* The client renders the same container (entry-client.tsx); without it
            here the markup differs and React discards the whole server render. */}
        <ToastContainer position="bottom-right" autoClose={5000} hideProgressBar={false}
          newestOnTop={false} closeOnClick rtl={false} pauseOnFocusLoss draggable pauseOnHover theme="light" />
      </Provider>
  )

  // Escaped so a value in the state cannot close the script tag it travels in.
  const state = JSON.stringify(store.getState()).replace(/</g, '\\u003c')
  return { html, state }
}
