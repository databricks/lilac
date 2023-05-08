<script>
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import '../app.css';
  // Carbon component must be imported after app.css
  import 'carbon-components-svelte/css/white.css';

  // Create query client
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Dont refetch on window focus
        refetchOnWindowFocus: false,
        // Treat data as never stale, avoiding repeated fetches
        staleTime: Infinity
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
</QueryClientProvider>
