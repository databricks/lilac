import {sveltekit} from '@sveltejs/kit/vite';
import {defineConfig} from 'vitest/config';

const PORT = 5173;

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    globals: true,
    environment: 'jsdom'
  },
  server: {
    port: PORT,
    proxy: {
      '^/api': 'http://127.0.0.1:5432',
      // Listing data files.
      '^/_data': 'http://127.0.0.1:5432',
      // Google login.
      '^/google': 'http://127.0.0.1:5432',
      '/auth_info': 'http://127.0.0.1:5432',
      '/status': 'http://127.0.0.1:5432',
      '/load_config': 'http://127.0.0.1:5432',
      // OpenAPI docs
      '^/docs': 'http://127.0.0.1:5432',
      '/openapi.json': 'http://127.0.0.1:5432',
      // Simulate the app being served under /blueprint base path for testing.
      '^/blueprint': {
        rewrite: path => path.replace('/blueprint', ''),
        target: `http://localhost:${PORT}/`
      }
    }
  }
});
