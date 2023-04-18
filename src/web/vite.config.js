import {defineConfig} from 'vite';

export default defineConfig({
  root: 'src',
  clearScreen: false,
  server: {
    proxy: {
      '^/api': 'http://0.0.0.0:5432',
    },
  },
  build: {
    // Relative to the root
    outDir: '../dist',
  },
});
