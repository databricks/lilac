import { QueryClient } from '@tanstack/svelte-query';
import { writable } from 'svelte/store';

export const errors = writable<Error[]>([]);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Dont refetch on window focus
      refetchOnWindowFocus: false,
      // Treat data as never stale, avoiding repeated fetches
      staleTime: Infinity,
      onError: (err) => {
        console.error((err as any).body?.detail);
        errors.update((errs) => [...errs, err as Error]);
      }
    },
    mutations: {
      onError: (err) => {
        console.error((err as any).body?.detail);
        errors.update((errs) => [...errs, err as Error]);
      }
    }
  }
});
