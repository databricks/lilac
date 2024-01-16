import {sveltekit} from '@sveltejs/kit/vite';
import {defineConfig} from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    globals: true,
    environment: 'jsdom'
  },
  base: '/blueprint/',
  server: {
    proxy: {
      '^/blueprint/$': {
        rewrite: path => {
          if (path.includes('_app')) {
            return path;
          }
          return path.replace('/blueprint', '');
        },
        target: 'http://127.0.0.1:5432'
      },
      '^/blueprint/api': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      // Listing data files.
      '^/blueprint/_data': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      // Google login.
      '^/blueprint/google': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      '/blueprint/auth_info': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      '/blueprint/status': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      '/blueprint/load_config': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      // OpenAPI docs
      '^/blueprint/docs': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      },
      '/blueprint/openapi.json': {
        rewrite: path => path.replace('/blueprint', ''),
        target: 'http://127.0.0.1:5432'
      }
    }
  }
});
