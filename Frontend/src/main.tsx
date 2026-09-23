
import AppRouter from '@routes/AppRouter.tsx'
import { store } from './store/store'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'





createRoot(document.getElementById('root')!).render(
        <Provider store={store}>
            <AppRouter />
        </Provider>
)
