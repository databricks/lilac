/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {JSONSchema7} from 'json-schema';
import {
  ComputeSignalOptions,
  DataLoadersService,
  DatasetInfo,
  DatasetsService,
  DataType,
  GetStatsOptions,
  LoadDatasetOptions,
  LoadDatasetResponse,
  SelectGroupsOptions,
  SelectRowsOptions,
  SignalInfo,
  SignalsService,
  SourcesList,
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

export const SELECT_GROUPS_SUPPORTED_DTYPES: DataType[] = [
  'string',
  'int8',
  'int16',
  'int32',
  'int64',
  'uint8',
  'uint16',
  'uint32',
  'uint64',
  'float16',
  'float32',
  'float64',
  'boolean',
];

const DATASETS_TAG = 'datasets';
export const datasetApi = createApi({
  reducerPath: 'datasetApi',
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  tagTypes: [DATASETS_TAG],
  endpoints: (builder) => ({
    getDatasets: builder.query<DatasetInfo[], void>({
      queryFn: () => query(() => DatasetsService.getDatasets()),
      providesTags: [DATASETS_TAG],
    }),
    // Loading datasets APIs.
    getSources: builder.query<SourcesList, void>({
      queryFn: () => query(() => DataLoadersService.getSources()),
    }),
    getSourceSchema: builder.query<JSONSchema7, {sourceName: string}>({
      queryFn: async ({sourceName}: {sourceName: string}) =>
        query(() => DataLoadersService.getSourceSchema(sourceName)),
    }),
    loadDataset: builder.mutation<
      LoadDatasetResponse,
      {sourceName: string; options: LoadDatasetOptions}
    >({
      queryFn: ({sourceName, options}: {sourceName: string; options: LoadDatasetOptions}) =>
        query(() => DataLoadersService.load(sourceName, options)),
      invalidatesTags: [DATASETS_TAG],
    }),
    // Dataset specific APIs.
    getManifest: builder.query<WebManifest, {namespace: string; datasetName: string}>({
      queryFn: async ({namespace, datasetName}) =>
        query(() => DatasetsService.getManifest(namespace, datasetName)),
    }),
    computeEmbeddingIndex: builder.query<Record<string, never>, ComputeEmbeddingQueryArg>({
      queryFn: async ({namespace, datasetName, embedding, column}) =>
        query(() =>
          DatasetsService.computeEmbeddingIndex(namespace, datasetName, embedding, column)
        ),
    }),
    computeSignalColumn: builder.query<Record<string, never>, ComputeSignalColumnQueryArg>({
      queryFn: async ({namespace, datasetName, options: body}) =>
        query(() => DatasetsService.computeSignalColumn(namespace, datasetName, body)),
    }),
    getStats: builder.query<StatsResult, StatsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(() => DatasetsService.getStats(namespace, datasetName, options)),
    }),
    selectRows: builder.query<Item[], SelectRowsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(() => DatasetsService.selectRows(namespace, datasetName, options)),
    }),
    selectGroups: builder.query<[LeafValue, number][], SelectGroupsQueryArg>({
      queryFn: async ({namespace, datasetName, options}) =>
        query(
          async () =>
            (await DatasetsService.selectGroups(namespace, datasetName, options)) as [
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
            ps.push(DatasetsService.getStats(namespace, datasetName, {leaf_path: leafPath}));
          }
          const statResults = await Promise.all(ps);
          return statResults;
        }),
    }),

    getSignals: builder.query<SignalInfo[], void>({
      queryFn: async () => query(async () => await SignalsService.getSignals()),
    }),
  }),
});

export const {
  useGetSourcesQuery,
  useComputeEmbeddingIndexQuery,
  useComputeSignalColumnQuery,
  useGetManifestQuery,
  useSelectRowsQuery,
  useSelectGroupsQuery,
  useGetStatsQuery,
  useGetMediaURLQuery,
  useGetMultipleStatsQuery,
  useGetDatasetsQuery,
  useGetSourceSchemaQuery,
  useLoadDatasetMutation,
  useGetSignalsQuery,
} = datasetApi;
