/**
 * RTK Query APIs for the data loader service: 'data_loader' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {JSONSchema7} from 'json-schema';
import {DataLoaderService, LoadDatasetOptions, SourcesList} from '../../fastapi_client';

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
    getSourceSchema: builder.query<JSONSchema7, {sourceName: string}>({
      queryFn: async ({sourceName}: {sourceName: string}) => {
        return {data: await DataLoaderService.getSourceSchema(sourceName)};
      },
    }),
    loadDataset: builder.mutation<null, {sourceName: string; options: LoadDatasetOptions}>({
      queryFn: async ({sourceName, options}: {sourceName: string; options: LoadDatasetOptions}) => {
        return {data: await DataLoaderService.load(sourceName, options)};
      },
    }),
  }),
});

export const {useGetSourcesQuery, useGetSourceSchemaQuery, useLoadDatasetMutation} = dataLoaderApi;
