<script lang="ts">
  import { QueryClientProvider } from '@tanstack/svelte-query';
  import '../app.css';
  // Carbon component must be imported after app.css
  import TaskStatus from '$lib/components/TaskStatus.svelte';
  import { errors, queryClient } from '$lib/store/queryClient';
  import { ToastNotification } from 'carbon-components-svelte';
  import 'carbon-components-svelte/css/white.css';
</script>

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen flex-col py-2">
    <div class="bg-base-100 flex flex-row items-center justify-between px-4">
      <a class="text-xl normal-case" href="/">Lilac Inspector</a>
      <TaskStatus />
    </div>

    <div class="h-full overflow-y-scroll">
      <slot />
    </div>
  </main>

  <div class="absolute bottom-4 right-4">
    {#each $errors as error}
      <ToastNotification
        title={error.name || 'Error'}
        subtitle={error.message}
        on:close={() => {
          $errors = $errors.filter((e) => e !== error);
        }}
      />
    {/each}
  </div>
</QueryClientProvider>
