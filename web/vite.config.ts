import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  base: loadEnv(mode, '.', 'VITE_').VITE_BASE || '/',
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
}))
