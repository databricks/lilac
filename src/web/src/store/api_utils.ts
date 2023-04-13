/**
 * Utils for RTK Query APIs.
 */

import {BaseQueryFn, QueryReturnValue} from '@reduxjs/toolkit/dist/query/baseQueryTypes';
import {ApiError} from '../../fastapi_client';

/**
 * Wraps an RTK Query queryFn in a method that pretty formats error messages.
 * @param fn The queryFn to wrap.
 * @returns A queryFn with error messages handled.
 */
export async function query<T>(
  fn: (() => Promise<T>) | (() => T)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
): Promise<QueryReturnValue<T, any>> {
  try {
    const data = await fn();
    return {data};
  } catch (e) {
    if (e instanceof ApiError) {
      console.error(e);
      console.error('Request:', e.request);
      return {
        error: {
          name: `${e.request.method} ${e.url} ${e.status} (${e.statusText})`,
          message: `${e.body['detail']}`,
        },
      };
    }
    return {error: e.toString()};
  }
}

export const fastAPIBaseQuery =
  (): BaseQueryFn<() => Promise<unknown>, unknown, unknown> => async (fn) => {
    try {
      const data = await fn();
      return {data};
    } catch (e) {
      if (e instanceof ApiError) {
        return {
          error: {
            name: `${e.request.method} ${e.url} ${e.status} (${e.statusText})`,
            message: `${e.body['detail']}`,
          },
        };
      }
      return {error: e.toString()};
    }
  };
