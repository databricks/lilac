/* eslint-disable @typescript-eslint/no-explicit-any */
import type {ApiError} from '$lilac';
import {QueryClient} from '@tanstack/svelte-query';
import {writable} from 'svelte/store';

export const apiErrors = writable<ApiError[]>([]);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Dont refetch on window focus
      refetchOnWindowFocus: false,
      // Treat data as never stale, avoiding repeated fetches
      staleTime: Infinity,
      retry: false,
      onError: err => {
        console.error((err as ApiError).body?.detail);
        apiErrors.update(errs => [...errs, err as ApiError]);
      }
    },
    mutations: {
      onError: err => {
        console.error((err as ApiError).body?.detail);
        apiErrors.update(errs => [...errs, err as ApiError]);
      }
    }
  }
});
