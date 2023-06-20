<script lang="ts">
  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import TaskStatus from '$lib/components/TaskStatus.svelte';
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
  import 'carbon-components-svelte/css/all.css';
  import '../app.css';

  let showError: ApiError | undefined = undefined;

  onMount(() => {
    urlHash.set(location.hash);
    history.pushState = function (_state, _unused, url) {
      if (url instanceof URL) {
        urlHash.set(url.hash);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return History.prototype.pushState.apply(history, arguments as any);
    };
  });
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
    // Lilac colors taken from: https://www.color-hex.com/color-palette/5811
    // lightest: #e6d7ff
    // lighter: #e7d1ff
    // medium: #e1c4ff
    // darker: #d8b9ff
    // darkest: #d2afff

    // Button background color
    'interactive-01': '#e6d7ff', // lightest lilac
    'interactive-04': 'transparent',
    'hover-primary': '#e1c4ff', // medium lilac
    'active-primary': '#d8b9ff', // darker lilac
    'text-primary': 'black',
    // Hover color of buttons.
    'text-04': 'black',
    // Controls the bottom border of the searchbox.
    'border-strong': 'transparent',
    // Typography
    'label-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'helper-text-01-letter-spacing': 'var(--cds-productive-heading-01-letter-spacing)',
    'productive-heading-01-font-weight': 600
  }}
/>

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen flex-col">
    <div class="flex flex-row items-center gap-x-8 border-b border-gray-200 px-4 py-2">
      <a class="text-xl normal-case" href="/">Lilac <span>Blueprint</span></a>
      <a class="opacity-50 hover:underline" href="/">Datasets</a>
      <a class="opacity-50 hover:underline" href="/concepts">Concepts</a>
      <div class="ml-auto">
        <TaskStatus />
      </div>
    </div>

    <div class="h-full overflow-y-hidden">
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
