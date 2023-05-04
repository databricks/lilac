import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}']
  },
  server: {
    proxy: {
      '^/api': 'http://0.0.0.0:5432',
      // OpenAPI docs
      '^/docs': 'http://0.0.0.0:5432',
      '/openapi.json': 'http://0.0.0.0:5432'
    }
  }
});
