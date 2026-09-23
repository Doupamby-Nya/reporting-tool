
import { renderToString } from 'react-dom/server'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

import './main.css'

import { StaticRouter } from "react-router-dom/server";
import SSRRouter from './routes/SSRRouter'
import chainReducer from './store/chainSlice'
import userReducer from './store/userSlice'

export function render(url: string) {
  // Create a fresh store for each SSR request to ensure consistency.
  // The reducer map has to match the client store in src/store/store.ts: the
  // client hydrates into this markup, so a different shape here is a
  // hydration mismatch.
  const store = configureStore({
    reducer: {
      user: userReducer,
      chains: chainReducer,
    },
  })

  const html = renderToString(
      <Provider store={store}>
        <StaticRouter location={url}>
          <SSRRouter />
        </StaticRouter>
      </Provider>
  )
  
  // Return only the HTML string directly - no object wrapper
  // This prevents any object serialization issues that could cause the store/state to appear
  return html
} 