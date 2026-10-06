import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Host, polling and the proxy target are fixed for the Compose service
// (P1-18): the container listens on all interfaces, polls because file events
// do not cross the WSL2 mount, and reaches Django as http://backend:8000.
// API_PROXY_TARGET only exists so the dev server can be pointed elsewhere
// when it runs outside Compose.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: ['localhost', '127.0.0.1'],
    watch: { usePolling: true, interval: 1000 },
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://backend:8000',
        changeOrigin: false,
      },
    },
  },
})
