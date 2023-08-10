import {sveltekit} from '@sveltejs/kit/vite';
import {defineConfig} from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    globals: true,
    environment: 'jsdom'
  },
  server: {
    proxy: {
      '^/api': 'http://0.0.0.0:5432',
      // Listing data files.
      '^/_data': 'http://0.0.0.0:5432',
      // Google login.
      '^/google': 'http://0.0.0.0:5432',
      '/auth_info': 'http://0.0.0.0:5432',
      // OpenAPI docs
      '^/docs': 'http://0.0.0.0:5432',
      '/openapi.json': 'http://0.0.0.0:5432'
    }
  }
});
