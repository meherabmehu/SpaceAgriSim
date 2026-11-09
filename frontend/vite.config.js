import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Long-lived dependencies get their own chunks so a deploy that only touches application code
// leaves the browser's cached copy of React, the icon set and three.js untouched. The 3D scene is
// already loaded through a dynamic import; without this split it lands in one 900 kB chunk that a
// one-line scene change invalidates in full.
const VENDOR_GROUPS = [
  ['vendor-three', ['three', '@react-three/fiber', '@react-three/drei']],
  ['vendor-react', ['react', 'react-dom', 'scheduler']],
  ['vendor-icons', ['lucide-react']],
  // Charts are only needed once a research view is opened, so they stay out of the first paint.
  ['vendor-charts', ['recharts', 'd3-', 'victory-vendor', 'internmap']],
]

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // allow the dev server to be reached through tunnels / preview hosts
    allowedHosts: true,
    // every /api/* call from the browser is forwarded to the FastAPI backend,
    // so the frontend never has to know the backend's real address
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          const match = VENDOR_GROUPS.find(([, packages]) =>
            packages.some((name) => id.includes(`/node_modules/${name}/`)),
          )
          return match ? match[0] : 'vendor'
        },
      },
    },
  },
})
