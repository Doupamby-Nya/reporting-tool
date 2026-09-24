import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import express from 'express'
import { createServer as createViteServer } from 'vite'
// Add at the TOP of server.js
import { JSDOM } from 'jsdom';

const { window } = new JSDOM('<!DOCTYPE html>', {
  pretendToBeVisual: true,
});
global.window = window;
global.document = window.document;
global.DOMMatrix = window.DOMMatrix;
global.DOMParser = window.DOMParser;


const __dirname = path.dirname(fileURLToPath(import.meta.url))

async function createServer() {
  const app = express()

  // Create Vite server in middleware mode and configure the app type as
  // 'custom', disabling Vite's own HTML serving logic so parent server
  // can take control
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: 'custom'
  })

  // Use vite's connect instance as middleware. If you use your own
  // express router (express.Router()), you should use router.use
  // When the server restarts (for example after the user modifies
  // vite.config.js), `vite.middlewares` is still going to be the same
  // reference (with a new internal stack of Vite and plugin-injected
  // middlewares). The following is valid even after restarts.
  app.use(vite.middlewares)

  app.use('*all', async (req, res, next) => {
    const url = req.originalUrl
  
    try {
      // 1. Read index.html
      let template = fs.readFileSync(
        path.resolve(__dirname, 'index.html'),
        'utf-8',
      )
  
      // 2. Apply Vite HTML transforms. This injects the Vite HMR client,
      //    and also applies HTML transforms from Vite plugins, e.g. global
      //    preambles from @vitejs/plugin-react
      template = await vite.transformIndexHtml(url, template)
  
      // 3. Load the server entry. ssrLoadModule automatically transforms
      //    ESM source code to be usable in Node.js! There is no bundling
      //    required, and provides efficient invalidation similar to HMR.
      const { render } = await vite.ssrLoadModule('/src/entry-server.tsx')
  
      // 4. render the app HTML. This assumes entry-server.js's exported
      //     `render` function calls appropriate framework SSR APIs,
      //    e.g. ReactDOMServer.renderToString()
      // render() returns { html, state }, so we need to destructure to get the html string
      //    The browser's cookie goes along so the page is rendered for the
      //    signed-in user, and the resulting state is handed to the client.
      const { html: appHtml, state } = await render(url, req.headers.cookie)

      // 5. Inject the app-rendered HTML and its state into the template.
      const html = template
        .replace(`<!--ssr-outlet-->`, appHtml)
        .replace(`<!--ssr-state-->`, `<script>window.__PRELOADED_STATE__=${state}</script>`)
  
      // 6. Send the rendered HTML back.
      res.status(200).set({ 'Content-Type': 'text/html' }).end(html)
    } catch (e) {
        console.error(e)
      // If an error is caught, let Vite fix the stack trace so it maps back
      // to your actual source code.
      vite.ssrFixStacktrace(e)
      next(e)
    }
  })

  const port = Number(process.env.PORT) || 4000
  app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
  });
}

createServer()