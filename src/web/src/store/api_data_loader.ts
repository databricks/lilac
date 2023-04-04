/**
 * RTK Query APIs for the data loader service: 'data_loader' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {SourceFieldsResponse, SourcesList} from '../../fastapi_client';
import {DataLoaderService} from '../../fastapi_client/services/DataLoaderService';

const serverReducerPath = 'serverApi';
export const serverApi = createApi({
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
    getSourceFields: builder.query<SourceFieldsResponse, {sourceName: string}>({
      queryFn: async ({sourceName}: {sourceName: string}) => {
        return {data: await DataLoaderService.getSourceFields(sourceName)};
      },
    }),
  }),
});

export const {useGetSourcesQuery, useGetSourceFieldsQuery} = serverApi;
