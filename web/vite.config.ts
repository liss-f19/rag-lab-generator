/**
 * Role:   Vite build and dev-server configuration of the web client.
 * Input:  Environment of the dev server; the React and Tailwind plugins.
 * Output: A dev server on :5173 proxying /api to the FastAPI backend, and a production bundle.
 * Flow:   Registers the React and Tailwind v4 plugins and forwards every /api request to
 *         127.0.0.1:8000 so the browser never needs CORS during development.
 */
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
    },
  },
})
