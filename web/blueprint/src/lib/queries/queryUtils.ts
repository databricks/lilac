/**
 * Utils for Lilac APIs.
 */

import type {ApiError} from '$lilac';
import {
  createMutation,
  createQueries,
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
  TError = ApiError,
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

export function createParallelApiQueries<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TQueryFn extends (...args: any[]) => ReturnType<TQueryFn>,
  TQueryFnData = Awaited<ReturnType<TQueryFn>>,
  TError = ApiError,
  TData = TQueryFnData
>(
  endpoint: TQueryFn,
  tags: string | string[],
  queriesArgs: Array<CreateQueryOptions<TQueryFnData, TError, TData>> = []
) {
  tags = Array.isArray(tags) ? tags : [tags];

  return (queryArgs: Array<Parameters<TQueryFn>>) => {
    const queries = queryArgs.map(queryArg => {
      return {
        queryKey: apiQueryKey(tags as string[], endpoint.name, ...queryArg),
        queryFn: () => endpoint(...queryArg),
        ...queriesArgs
      };
    });
    return createQueries(queries);
  };
}

export function createApiMutation<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  TMutationFn extends (...args: any[]) => Promise<any>,
  TData = Awaited<ReturnType<TMutationFn>>,
  TError = ApiError,
  TVariables = Parameters<TMutationFn>
>(endpoint: TMutationFn, mutationArgs: CreateMutationOptions<TData, TError, TVariables> = {}) {
  return () =>
    createMutation<TData, TError, TVariables>({
      mutationFn: args => endpoint(...(args as unknown[])),
      ...mutationArgs
    });
}
