import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Use '/api/' so /api.ts (module) is not proxied; only /api/search, /api/health, etc. are
      '/api/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
