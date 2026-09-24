import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import express from 'express'
import { JSDOM } from 'jsdom';

// Polyfills for SSR
const { window } = new JSDOM('<!DOCTYPE html>', {
  pretendToBeVisual: true,
});
global.window = window;
global.document = window.document;
global.DOMMatrix = window.DOMMatrix;
global.DOMParser = window.DOMParser;
global.navigator = window.navigator;

const __dirname = path.dirname(fileURLToPath(import.meta.url))


async function createServer() {
  const app = express()
  const port = Number(process.env.PORT) || 3000
  const host = process.env.HOST || 'localhost'

  // Paths for production build
  const clientRoot = path.resolve(__dirname, 'dist/client')
  const serverEntry = path.resolve(__dirname, 'dist/server/entry-server.js')

  // Check if built files exist
  if (!fs.existsSync(clientRoot) || !fs.existsSync(serverEntry)) {
    console.error('Build files not found. Please run "npm run build" first.')
    process.exit(1)
  }

  const templateHtml = fs.readFileSync(path.resolve(clientRoot, 'index.html'), 'utf-8')

  // Serve static assets from dist/client
  // 'index: false' ensures we don't serve index.html for root path, letting SSR handle it
  app.use(express.static(clientRoot, { index: false }))

  // Middleware to clear problematic MSAL cookies that trigger WAF false positives
  // app.use((req, res, next) => {
  //   const cookies = req.headers.cookie;
  //   if (cookies && cookies.includes('msal.cache.encryption')) {
  //       // Clear the cookie on the domain path
  //       res.clearCookie('msal.cache.encryption', { path: '/' });
  //   }
  //   next();
  // });

  app.get('/healthcheck', (req, res) => {
    // Basic health check
    res.status(200).send('ok')
  })
  app.get('/liveness', (req, res) => {
    // Basic health check
    res.status(200).send('ok')
  })

  // SSR Handler
  app.use('/', async (req, res, next) => {
    try {
      const url = req.originalUrl

      // Dynamic import of the built server entry
      const { render } = await import(fileURLToPath(new URL('./dist/server/entry-server.js', import.meta.url)))

      // Rendered for the signed-in user; the state goes to the client store.
      const { html: appHtml, state } = await render(url, req.headers.cookie)

      const html = templateHtml
        .replace(`<!--ssr-outlet-->`, appHtml)
        .replace(`<!--ssr-state-->`, `<script>window.__PRELOADED_STATE__=${state}</script>`)

      res.status(200).set({ 'Content-Type': 'text/html' }).end(html)
    } catch (e) {
      console.error('SSR Error:', e)
      next(e)
    }
  })

  app.listen(port, host, () => {
    console.log(`Production Server running at http://${host}:${port}`)
  })
}

createServer()
