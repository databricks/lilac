<script lang="ts">
  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import TaskStatus from '$lib/components/TaskStatus.svelte';
  import {apiErrors, queryClient} from '$lib/queries/queryClient';
  import TaskMonitor from '$lib/stores/TaskMonitor.svelte';
  import type {ApiError} from '$lilac';
  import {QueryClientProvider} from '@tanstack/svelte-query';
  import {ToastNotification} from 'carbon-components-svelte';
  import {onMount} from 'svelte';
  // Styles
  import '../tailwind.css';
  // Carbon component must be imported after tailwind.css
  import {urlHash} from '$lib/stores/urlHashStore';
  import 'carbon-components-svelte/css/white.css';
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

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen flex-col">
    <div class="flex flex-row items-center gap-x-8 border-b border-gray-200 px-4 py-2">
      <a class="text-xl normal-case" href="/">Lilac Blueprint</a>
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
