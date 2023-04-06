/**
 * RTK Query APIs for the data loader service: 'data_loader' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {JSONSchema7} from 'json-schema';
import {DataLoaderService, LoadDatasetOptions, SourcesList} from '../../fastapi_client';
import {query} from './api_utils';

const serverReducerPath = 'dataLoaderApi';
export const dataLoaderApi = createApi({
  reducerPath: serverReducerPath,
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    getSources: builder.query<SourcesList, void>({
      queryFn: () => query(() => DataLoaderService.getSources()),
    }),
    getSourceSchema: builder.query<JSONSchema7, {sourceName: string}>({
      queryFn: async ({sourceName}: {sourceName: string}) =>
        query(() => DataLoaderService.getSourceSchema(sourceName)),
    }),
    loadDataset: builder.mutation<null, {sourceName: string; options: LoadDatasetOptions}>({
      queryFn: ({sourceName, options}: {sourceName: string; options: LoadDatasetOptions}) =>
        query(() => DataLoaderService.load(sourceName, options)),
    }),
  }),
});

export const {useGetSourcesQuery, useGetSourceSchemaQuery, useLoadDatasetMutation} = dataLoaderApi;
