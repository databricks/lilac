/**
 * Utils for RTK Query APIs.
 */

import {
  createMutation,
  createQuery,
  type CreateMutationOptions,
  type CreateQueryOptions
} from '@tanstack/svelte-query';

const apiQueryKey = (tags: string[], endpoint: string, ...args: unknown[]) => [
  ...tags,
  endpoint,
  ...args
];

export function createApiQuery<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TQueryFn extends (...args: any[]) => Promise<any>,
  TQueryFnData = Awaited<ReturnType<TQueryFn>>,
  TError = Error,
  TData = TQueryFnData
>(
  endpoint: TQueryFn,
  tags: string | string[],
  queryArgs: CreateQueryOptions<TQueryFnData, TError, TData> = {}
) {
  tags = Array.isArray(tags) ? tags : [tags];
  return (...args: Parameters<TQueryFn>) =>
    createQuery<TQueryFnData, TError, TData>({
      queryKey: apiQueryKey(tags as string[], endpoint.name, ...args),
      queryFn: () => endpoint(...args),
      ...queryArgs
    });
}

export function createApiMutation<
  TMutationFn extends (...args: any[]) => Promise<any>,
  TData = Awaited<ReturnType<TMutationFn>>
>(endpoint: TMutationFn, mutationArgs: CreateMutationOptions<TData, Error> = {}) {
  return (...args: Parameters<TMutationFn>) =>
    createMutation<TData, Error>({
      mutationFn: () => endpoint(...args),
      ...mutationArgs
    });
}
