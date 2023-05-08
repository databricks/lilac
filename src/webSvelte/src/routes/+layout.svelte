<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import '../app.css';
  // Carbon component must be imported after app.css
  import { ToastNotification } from 'carbon-components-svelte';
  import 'carbon-components-svelte/css/white.css';

  let errors: Error[] = [];

  // Create query client
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Dont refetch on window focus
        refetchOnWindowFocus: false,
        // Treat data as never stale, avoiding repeated fetches
        staleTime: Infinity,
        onError: (err) => {
          console.error((err as any).body?.detail);
          errors = [...errors, err as Error];
        }
      },
      mutations: {
        onError: (err) => {
          console.error((err as any).body?.detail);
          errors = [...errors, err as Error];
        }
      }
    }
  });
</script>

<QueryClientProvider client={queryClient}>
  <main class="flex h-screen flex-col py-2">
    <div class="bg-base-100 px-4">
      <a class="text-xl normal-case" href="/">Lilac Inspector</a>
    </div>

    <div class="overflow-y-scroll">
      <slot />
    </div>
  </main>

  <div class="absolute bottom-4 right-4">
    {#each errors as error}
      <ToastNotification
        title={error.name || 'Error'}
        subtitle={error.message}
        on:close={() => {
          errors = errors.filter((e) => e !== error);
        }}
      />
    {/each}
  </div>
</QueryClientProvider>
