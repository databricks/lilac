<script lang="ts">
  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import {apiErrors, queryClient} from '$lib/queries/queryClient';
  import TaskMonitor from '$lib/stores/TaskMonitor.svelte';
  import type {ApiError} from '$lilac';
  import {QueryClientProvider} from '@tanstack/svelte-query';
  import {Theme, ToastNotification} from 'carbon-components-svelte';
  import {onMount} from 'svelte';
  // Styles
  import '../tailwind.css';
  // Carbon component must be imported after tailwind.css
  import {urlHash} from '$lib/stores/urlHashStore';
  // This import is so we can override the carbon icon theme below.
  import Navigation from '$lib/components/Navigation.svelte';
  import {createSettingsStore, setSettingsContext} from '$lib/stores/settingsStore';
  import 'carbon-components-svelte/css/all.css';
  import '../app.css';

  let showError: ApiError | undefined = undefined;

  onMount(() => {
    // This fixes a cross-origin error when the app is embedding in an iframe. Some carbon
    // components attach listeners to window.parent, which is not allowed in an iframe, so we set
    // the parent to window.
    window.parent = window;

    urlHash.set(location.hash);
    history.pushState = function (_state, _unused, url) {
      if (url instanceof URL) {
        urlHash.set(url.hash);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return History.prototype.pushState.apply(history, arguments as any);
    };
  });

  $: settingsStore = createSettingsStore();
  $: setSettingsContext(settingsStore);
</script>

<!-- Monitor for hash changes in the URL. -->
<svelte:window
  on:hashchange={() => urlHash.set(location.hash)}
  on:popstate={() => urlHash.set(location.hash)}
/>

<!-- https://carbondesignsystem.com/guidelines/themes/overview#customizing-a-theme -->
<Theme
  theme="white"
  tokens={{
    // Controls the bottom border of the searchbox.
    'border-strong': 'transparent',
    // Typography
    'label-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'helper-text-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'productive-heading-01-font-weight': 600
  }}
/>

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen w-full flex-row">
    <div class="w-20 flex-shrink-0 bg-neutral-100">
      <Navigation />
    </div>
    <div class="h-full w-full overflow-hidden">
      <slot />
    </div>
  </main>

  <div class="absolute bottom-4 right-4">
    {#each $apiErrors as error}
      <ToastNotification
        lowContrast
        title={error.name || 'Error'}
        subtitle={error.message}
        on:close={() => {
          $apiErrors = $apiErrors.filter(e => e !== error);
        }}
      >
        <div slot="caption">
          <button class="underline" on:click={() => (showError = error)}>Show error</button>
        </div>
      </ToastNotification>
    {/each}

    {#if showError}
      <ApiErrorModal error={showError} />
    {/if}
  </div>
  <TaskMonitor />
</QueryClientProvider>
