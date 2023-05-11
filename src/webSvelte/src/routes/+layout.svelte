<script lang="ts">
  import {QueryClientProvider} from '@tanstack/svelte-query';

  import ApiErrorModal from '$lib/components/ApiErrorModal.svelte';
  import TaskStatus from '$lib/components/TaskStatus.svelte';
  import TaskMonitor from '$lib/store/TaskMonitor.svelte';
  import {apiErrors, queryClient} from '$lib/store/queryClient';
  import type {ApiError} from '$lilac';
  import {ToastNotification} from 'carbon-components-svelte';
  // Styles
  import '../tailwind.css';
  // Carbon component must be imported after tailwind.css
  import 'carbon-components-svelte/css/white.css';
  import '../app.css';

  let showError: ApiError | undefined = undefined;
</script>

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen flex-col">
    <div class="flex flex-row items-center justify-between border-b border-gray-200 px-4 py-2">
      <a class="text-xl normal-case" href="/">Lilac Inspector</a>
      <TaskStatus />
    </div>

    <div class="h-full overflow-y-scroll">
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
