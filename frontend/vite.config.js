import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Long-lived dependencies get their own chunks so a deploy that only touches application code
// leaves the browser's cached copy of React and the icon set untouched.
//
// Only *named* groups are chunked. The previous catch-all `vendor` bucket created a dependency
// cycle (vendor-charts -> vendor -> vendor-charts) and merged unrelated packages into one module.
//
// Phase 33: the growth chamber stopped being a three.js scene, so the vendor-three and vendor-r3f
// groups are gone along with the libraries. Nothing in the app now ships a chunk above Vite's
// 500 kB warning threshold; `npm run build:check` still fails if an oversized chunk becomes
// statically reachable from the entry, or if the initial request grows past its budget.
const VENDOR_GROUPS = [
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
