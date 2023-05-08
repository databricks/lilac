<script>
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import '../app.css';

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
  <main class="flex h-screen flex-col">
    <div class="navbar bg-base-100">
      <a class="btn-ghost btn text-xl normal-case" href="/">Lilac Inspector</a>
    </div>

    <div class="overflow-y-scroll">
      <slot />
    </div>
  </main>
</QueryClientProvider>
