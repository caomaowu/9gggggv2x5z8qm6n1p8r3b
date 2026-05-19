import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 18521,
    proxy: {
      '/api': 'http://localhost:18520',
      '/ws': {
        target: 'ws://localhost:18520',
        ws: true,
      },
    },
  },
})
