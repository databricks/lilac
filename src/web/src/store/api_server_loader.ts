/**
 * RTK Query APIs for the loader service: 'loader' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {SourceFieldsResponse, SourcesList} from '../../fastapi_client';
import {LoaderService} from '../../fastapi_client/services/LoaderService';

const serverReducerPath = 'serverApi';
export const serverApi = createApi({
  reducerPath: serverReducerPath,
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    loaderSources: builder.query<SourcesList, void>({
      queryFn: async () => {
        return {data: await LoaderService.loaderSources()};
      },
    }),
    loaderSourceFields: builder.query<SourceFieldsResponse, {sourceName: string}>({
      queryFn: async ({sourceName}: {sourceName: string}) => {
        return {data: await LoaderService.loaderSourceFields(sourceName)};
      },
    }),
  }),
});

export const {useLoaderSourcesQuery, useLoaderSourceFieldsQuery} = serverApi;
