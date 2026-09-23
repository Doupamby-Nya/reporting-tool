import { store } from "@store/store";
import { StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

import SSRRouter from "@routes/SSRRouter";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import './main.css'



const bootstrapMsalAndHydrate = async () => {
       
        hydrateRoot(
            document.getElementById('root')!,
            <StrictMode>
                    <Provider store={store}>
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
                    </Provider>
            </StrictMode>
        )
}

bootstrapMsalAndHydrate();