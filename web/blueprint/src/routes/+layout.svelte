<script lang="ts">
  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import TaskStatus from '$lib/components/TaskStatus.svelte';
  import {apiErrors, queryClient} from '$lib/queries/queryClient';
  import TaskMonitor from '$lib/stores/TaskMonitor.svelte';
  import type {ApiError} from '$lilac';
  import {QueryClientProvider} from '@tanstack/svelte-query';
  import {ToastNotification} from 'carbon-components-svelte';
  import router from 'page';
  // Styles
  import '../tailwind.css';
  // Carbon component must be imported after tailwind.css
  import 'carbon-components-svelte/css/white.css';
  import {onMount} from 'svelte';
  import '../app.css';

  let showError: ApiError | undefined = undefined;

  onMount(() => {
    router.start({hashbang: true});
  });
</script>

<!-- Make page.js monitor for hash changes in the URL. -->
<svelte:window on:hashchange={() => router.replace(location.hash, null, true, true)} />

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
