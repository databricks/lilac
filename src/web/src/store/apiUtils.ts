/**
 * Utils for RTK Query APIs.
 */

import {BaseQueryFn} from '@reduxjs/toolkit/dist/query/baseQueryTypes';
import {ApiError} from '../../fastapi_client';

export const fastAPIBaseQuery = <T>(): BaseQueryFn<() => T | Promise<T>, T, unknown> => {
  async function inner(fn: () => T | Promise<T>): Promise<{data: T} | {error: unknown}> {
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
  }
  return inner;
};
