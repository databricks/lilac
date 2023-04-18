import path from 'node:path';
import {defineConfig} from 'vite';
import {viteStaticCopy} from 'vite-plugin-static-copy';

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
    emptyOutDir: true,
  },
  plugins: [
    viteStaticCopy({
      targets: [
        {
          src: path.resolve(__dirname, './node_modules/@shoelace-style/shoelace/dist/assets'),
          dest: 'static/shoelace',
        },
      ],
    }),
  ],
});
