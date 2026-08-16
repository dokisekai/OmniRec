import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      },
      '/search': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/recommend': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/metrics': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
