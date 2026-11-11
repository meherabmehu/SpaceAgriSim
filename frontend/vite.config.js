import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Long-lived dependencies get their own chunks so a deploy that only touches application code
// leaves the browser's cached copy of React, the icon set and three.js untouched.
//
// Only *named* groups are chunked. The previous catch-all `vendor` bucket created a dependency
// cycle (vendor-charts -> vendor -> vendor-charts) and merged unrelated packages into one module.
//
// On the remaining size warning: three.js is ~800 kB minified even when a module imports only
// {WebGLRenderer, Scene}, so no bundling choice below 500 kB exists while the 3D twin is a
// three.js scene. The guarantee this project enforces instead is that no oversized chunk is on
// the initial route - `npm run build:check` fails if one is statically reachable from the entry.
const VENDOR_GROUPS = [
  // three.js and the React renderer for it are separate chunks: a scene change should not
  // invalidate the 700 kB library, and the library should not be re-downloaded for a scene edit.
  ['vendor-three', ['three']],
  ['vendor-r3f', ['@react-three/fiber', '@react-three/drei']],
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
  preview: {
    // The browser suite runs against the production build, so the same proxy the dev server uses
    // has to exist here; without it `/api` would 404 under `vite preview`.
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
          // Everything else is left to Rollup. A catch-all bucket is what produced the
          // `vendor-charts -> vendor -> vendor-charts` cycle: it swept in modules that the chart
          // library imports, while the chart library itself was already inside a named chunk.
          return match ? match[0] : undefined
        },
      },
    },
  },
})
