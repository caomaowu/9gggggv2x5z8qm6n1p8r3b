import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    https: fs.existsSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/private.key.pem')) && 
           fs.existsSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/domain.cert.pem')) ? {
      key: fs.readFileSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/private.key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/domain.cert.pem'))
    } : undefined
  }
})
