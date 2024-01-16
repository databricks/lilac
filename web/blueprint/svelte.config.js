import adapter from '@sveltejs/adapter-static';
import {vitePreprocess} from '@sveltejs/kit/vite';
// See https://github.com/carbon-design-system/carbon-preprocess-svelte#sample-sveltekit-set-up
import {optimizeImports} from 'carbon-preprocess-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Consult https://kit.svelte.dev/docs/integrations#preprocessors
  // for more information about preprocessors
  preprocess: [vitePreprocess(), optimizeImports()],

  kit: {
    // See https://kit.svelte.dev/docs/adapters for more information about adapters.
    adapter: adapter(),
    alias: {
      $lilac: '../lib'
    }
  }
};

export default config;
