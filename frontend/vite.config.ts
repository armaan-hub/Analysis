import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
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
