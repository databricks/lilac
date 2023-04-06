/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {
  ComputeSignalOptions,
  DatasetInfo,
  DatasetService,
  GetStatsOptions,
  SelectGroupsOptions,
  SelectRowsOptions,
  StatsResult,
  WebManifest,
} from '../../fastapi_client';
import {Item, LeafValue, Path} from '../schema';
import {query} from './api_utils';

export interface SelectRowsQueryArg {
  namespace: string;
  datasetName: string;
  options: SelectRowsOptions;
}

export interface SelectGroupsQueryArg {
  namespace: string;
  datasetName: string;
  options: SelectGroupsOptions;
}

export interface GetMediaQueryArg {
  namespace: string;
  datasetName: string;
  itemId: string;
  leafPath: Path;
}

export interface StatsQueryArg {
  namespace: string;
  datasetName: string;
  options: GetStatsOptions;
}

export interface ComputeEmbeddingQueryArg {
  namespace: string;
  datasetName: string;
  embedding: string;
  column: string;
}

export interface ComputeSignalColumnQueryArg {
  namespace: string;
  datasetName: string;
  options: ComputeSignalOptions;
}

export interface MultipleStatsQueryArg {
  namespace: string;
  datasetName: string;
  leafPaths: Path[];
}

export const datasetApi = createApi({
  reducerPath: 'datasetApi',
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    getDatasets: builder.query<DatasetInfo[], void>({
      queryFn: () => query(() => DatasetService.getDatasets()),
    }),
    getManifest: builder.query<WebManifest, {namespace: string; datasetName: string}>({
      queryFn: async ({namespace, datasetName}) =>
        query(() => DatasetService.getManifest(namespace, datasetName)),
    }),
    computeEmbeddingIndex: builder.query<Record<string, never>, ComputeEmbeddingQueryArg>({
      queryFn: async ({namespace, datasetName, embedding, column}) =>
        query(() =>
          DatasetService.computeEmbeddingIndex(namespace, datasetName, embedding, column)
        ),
    }),
    computeSignalColumn: builder.query<Record<string, never>, ComputeSignalColumnQueryArg>({
      queryFn: async ({namespace, datasetName, options: body}) =>
        query(() => DatasetService.computeSignalColumn(namespace, datasetName, body)),
    }),
    getStats: builder.query<StatsResult, StatsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(() => DatasetService.getStats(namespace, datasetName, options)),
    }),
    selectRows: builder.query<Item[], SelectRowsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(() => DatasetService.selectRows(namespace, datasetName, options)),
    }),
    selectGroups: builder.query<[LeafValue, number][], SelectGroupsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(
          async () =>
            (await DatasetService.selectGroups(namespace, datasetName, options)) as [
              LeafValue,
              number
            ][]
        ),
    }),
    getMediaURL: builder.query<string, GetMediaQueryArg>({
      queryFn: async ({namespace, datasetName, itemId, leafPath}) =>
        query(() => {
          const url = new URL(`/api/v1/datasets/${namespace}/${datasetName}/media`);
          const params = {item_id: itemId, leaf_path: leafPath.join(',')};
          url.search = new URLSearchParams(params).toString();
          return url.toString();
        }),
    }),
    getMultipleStats: builder.query<StatsResult[], MultipleStatsQueryArg>({
      queryFn: async ({namespace, datasetName, leafPaths}) =>
        query(async () => {
          const ps: Promise<StatsResult>[] = [];
          for (const leafPath of leafPaths) {
            ps.push(DatasetService.getStats(namespace, datasetName, {leaf_path: leafPath}));
          }
          const statResults = await Promise.all(ps);
          return statResults;
        }),
    }),
  }),
});

export const {
  useGetDatasetsQuery,
  useComputeEmbeddingIndexQuery,
  useComputeSignalColumnQuery,
  useGetManifestQuery,
  useSelectRowsQuery,
  useSelectGroupsQuery,
  useGetStatsQuery,
  useGetMediaURLQuery,
  useGetMultipleStatsQuery,
} = datasetApi;
