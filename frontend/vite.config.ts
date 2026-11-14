import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Same origin for the browser: no CORS, cookies just work (spec 4).
    proxy: { '/api': 'http://127.0.0.1:8080' },
  },
})
