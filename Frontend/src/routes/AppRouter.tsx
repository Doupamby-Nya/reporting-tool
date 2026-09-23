import { BrowserRouter } from "react-router-dom"
import { ToastContainer } from "react-toastify"
import "react-toastify/dist/ReactToastify.css"

import SSRRouter from "@routes/SSRRouter"

/**
 * The client-only entry point (see main.tsx).
 *
 * It wraps the same route definition the server renders rather than keeping
 * its own copy: two lists of routes drift, and a route that exists on one
 * side only is a page that works until it is reloaded.
 */
const AppRouter: React.FC = () => (
    <>
        <BrowserRouter>
            <SSRRouter />
        </BrowserRouter>
        <ToastContainer
            position="bottom-right"
            autoClose={5000}
            hideProgressBar={false}
            newestOnTop={false}
            closeOnClick
            rtl={false}
            pauseOnFocusLoss
            draggable
            pauseOnHover
            theme="light"
        />
    </>
)

export default AppRouter
