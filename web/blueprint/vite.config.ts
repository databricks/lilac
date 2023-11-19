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
      '^/api': 'http://localhost:5432',
      // Listing data files.
      '^/_data': 'http://localhost:5432',
      // Google login.
      '^/google': 'http://localhost:5432',
      '/auth_info': 'http://localhost:5432',
      '/status': 'http://localhost:5432',
      '/load_config': 'http://localhost:5432',
      // OpenAPI docs
      '^/docs': 'http://localhost:5432',
      '/openapi.json': 'http://localhost:5432'
    }
  }
});
