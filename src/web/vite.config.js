import react from '@vitejs/plugin-react';
import path from 'node:path';
import {defineConfig} from 'vite';
import {viteStaticCopy} from 'vite-plugin-static-copy';

export default defineConfig({
  root: 'src',
  clearScreen: false,
  server: {
    proxy: {
      '^/api': 'http://0.0.0.0:5432',
      // OpenAPI docs
      '^/docs': 'http://0.0.0.0:5432',
      '/openapi.json': 'http://0.0.0.0:5432',
    },
  },

  build: {
    // Relative to the root
    outDir: '../dist',
    emptyOutDir: true,
  },
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: path.resolve(__dirname, '../../node_modules/@shoelace-style/shoelace/dist/assets'),
          dest: 'static/shoelace',
        },
      ],
    }),
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: '../tests/setup.ts',
    coverage: {reporter: ['lcov']},
  },
});
