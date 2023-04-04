/**
 * RTK Query APIs for the data loader service: 'data_loader' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {DataLoaderService, SourceFields, SourcesList} from '../../fastapi_client';

const serverReducerPath = 'dataLoaderApi';
export const dataLoaderApi = createApi({
  reducerPath: serverReducerPath,
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    getSources: builder.query<SourcesList, void>({
      queryFn: async () => {
        return {data: await DataLoaderService.getSources()};
      },
    }),
    getSourceFields: builder.query<SourceFields | null, {sourceName?: string}>({
      queryFn: async ({sourceName}: {sourceName?: string}) => {
        if (sourceName == null) {
          return {data: null};
        }
        return {data: await DataLoaderService.getSourceFields(sourceName)};
      },
    }),
  }),
});

export const {useGetSourcesQuery, useGetSourceFieldsQuery} = dataLoaderApi;
