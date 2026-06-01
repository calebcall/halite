import fs from 'node:fs'
import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Resolve the build hash that the sidebar footer surfaces as the deployed
// version. Two sources, in priority order:
//   1. BUILD_HASH env var — set by CI (github.sha) or `docker compose build`.
//   2. A BUILD_HASH.txt file next to this config — written by a pre-build step
//      in environments that can't pass a build arg but can run a command. With
//      Komodo, set Pre Build to: git rev-parse --short HEAD > frontend/BUILD_HASH.txt
// Empty in local dev, which the footer renders as "Dev".
function resolveBuildHash(): string {
  if (process.env.BUILD_HASH) return process.env.BUILD_HASH.trim()
  try {
    return fs.readFileSync(path.resolve(__dirname, 'BUILD_HASH.txt'), 'utf8').trim()
  } catch {
    return ''
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_HASH__: JSON.stringify(resolveBuildHash()),
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: false,
      },
    },
  },
  build: {
    // Split recharts + its d3 deps into their own chunk so the initial
    // payload stays lean and the charts cache independently from app code.
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
  },
})
