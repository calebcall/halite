/// <reference types="vitest/config" />
import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // Build hash injected at build time (see Dockerfile's BUILD_HASH arg) so the
  // sidebar footer can surface the deployed version. Empty in local dev, which
  // the footer renders as "Dev".
  define: {
    __BUILD_HASH__: JSON.stringify(process.env.BUILD_HASH ?? ''),
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
