/**
 * Utils for RTK Query APIs.
 */

import {QueryReturnValue} from '@reduxjs/toolkit/dist/query/baseQueryTypes';
import {ApiError} from '../../fastapi_client';

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
          name: `${e.request.method} ${e.url} ${e.status} (${e.name})`,
          message: `${e.body['detail']}`,
        },
      };
    }
    return {error: e.toString()};
  }
}
