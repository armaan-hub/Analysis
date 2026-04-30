import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import os from 'os'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Store Vite's dep-prebundle cache in the system temp dir (outside OneDrive).
  // Without this, OneDrive syncs every cache write and first startup takes several minutes.
  cacheDir: path.join(os.tmpdir(), 'vite-legal-chatbot'),
  server: {
    port: 5173,
    strictPort: true,       // Fail fast if 5173 is busy (vs silently bumping to 5174/5175)
    closeOnStdinEnd: false,  // Keep running when stdin closes (needed for PowerShell Start-Job / non-TTY environments)
    warmup: {
      clientFiles: ['./src/main.tsx', './src/App.tsx'],
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
  build: {
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          const nm = id.replace(/\\/g, '/');
          if (/node_modules\/(react|react-dom|react-router-dom)\//.test(nm)) return 'vendor';
          if (/node_modules\/(react-markdown|remark-gfm|remark-|micromark|mdast|unist|vfile|hast)/.test(nm)) return 'markdown';
          if (/node_modules\/(docx|file-saver|xlsx)\//.test(nm)) return 'docx';
          if (/node_modules\/axios\//.test(nm)) return 'http';
        },
      },
    },
  },
})
