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
    // 在 Windows 本地开发时关闭 HTTPS 以解决加载缓慢问题，在 VPS (Linux) 上自动开启
    https: process.platform !== 'win32' && 
           fs.existsSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/private.key.pem')) && 
           fs.existsSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/domain.cert.pem')) ? {
      key: fs.readFileSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/private.key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, '../caomao.xyz-ssl-bundle/domain.cert.pem'))
    } : undefined
  }
})
