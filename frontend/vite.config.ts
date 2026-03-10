import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()], // 使用默认的自动JSX运行时
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: ['www.aisimulationplatform.cloud', 'aisimulationplatform.cloud'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      }
    }
  },
  optimizeDeps: {
    force: true, // 强制重新构建依赖
    include: ['react', 'react-dom', 'react/jsx-runtime']
  }
})