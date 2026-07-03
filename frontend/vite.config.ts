import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The SPA is served same-origin as the FastAPI backend in production (base '/').
// In dev, proxy /api to the local FastAPI server so cookies + SSE stay same-origin.
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE endpoints stream indefinitely; do not buffer.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache';
            }
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
