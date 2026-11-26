import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/three/examples/jsm/')) return 'three-addons'
          if (id.includes('/node_modules/three/build/three.module.js')) return 'three-core'
        },
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/api-root': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api-root$/, '/'),
      },
      '/symptoms': 'http://127.0.0.1:8000',
      '/mood-sleep': 'http://127.0.0.1:8000',
      '/analytics': 'http://127.0.0.1:8000',
      '/ai': 'http://127.0.0.1:8000',
      '/rag': 'http://127.0.0.1:8000',
    },
  },
})
