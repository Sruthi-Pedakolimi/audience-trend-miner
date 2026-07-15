import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl =
    process.env.VITE_BACKEND_URL || env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/portfolio': backendUrl,
        '/rejected': backendUrl,
        '/generate': backendUrl,
        '/cached-article-limits': backendUrl,
        '/health': backendUrl,
      },
    },
  }
})
