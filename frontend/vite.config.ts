/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxyTarget = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // SPA and API are same-origin through this proxy, so session cookies + CSRF just work.
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: false, xfwd: true },
    },
    // Test artifacts must not trigger dev-server page reloads during e2e runs.
    watch: { usePolling: true, interval: 300, ignored: ['**/playwright-report/**', '**/test-results/**', '**/tests/**'] },
  },
  optimizeDeps: {
    include: ['react', 'react-dom/client', 'react-router-dom', '@tanstack/react-query', 'dompurify'],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
