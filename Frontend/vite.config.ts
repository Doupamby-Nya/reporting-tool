import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";


export default defineConfig({
  plugins: [
    react(), 
    tsconfigPaths({
      root: './',
    }),
  ],
  preview: {
    port: 3000,
    strictPort: true,
   },
   server: {
    port: 3000,
    strictPort: true,
    host: true,
    hmr:{
      port: 3010,
      clientPort: 3010,
    },
    origin: "http://0.0.0.0:3000",
    allowedHosts: true,
    watch: {
      usePolling: true,
    },
   },
   build: {
    rollupOptions: {
      input: {
        main: './index.html',
        server: './src/entry-server.tsx'
      },
    }
   },
   ssr: {
     // Ensure React Router works in SSR
     noExternal: ['react-router-dom']
    }
})