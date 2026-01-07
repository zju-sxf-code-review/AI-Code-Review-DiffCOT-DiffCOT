import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // 使用相对路径，支持 Electron 打包后的 file:// 协议
  base: './',
})
