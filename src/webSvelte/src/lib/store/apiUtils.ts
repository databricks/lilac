/**
 * Utils for RTK Query APIs.
 */

import { createMutation, createQuery } from '@tanstack/svelte-query';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createApiQuery<E extends (...args: any[]) => Promise<any>>(
  endpoint: E,
  rootKey: string
) {
  return (...args: Parameters<E>) =>
    createQuery<Awaited<ReturnType<E>>, Error>({
      queryKey: [rootKey, endpoint.name, ...args],
      queryFn: () => endpoint(...args)
    });
}

export function createApiMutation<E extends (...args: any[]) => Promise<any>>(
  endpoint: E,
  rootKey: string
) {
  return (...args: Parameters<E>) =>
    createMutation<Awaited<ReturnType<E>>, Error>({
      mutationKey: [rootKey, endpoint.name, ...args],
      mutationFn: () => endpoint(...args)
    });
}
