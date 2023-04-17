/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {JSONSchema7} from 'json-schema';
import {
  ComputeEmbeddingIndexOptions,
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
  SourcesList,
  StatsResult,
  WebManifest,
} from '../../fastapi_client';
import {Item, LeafValue, Path} from '../schema';
import {fastAPIBaseQuery} from './api_utils';

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

export interface ComputeEmbeddingIndexQueryArg {
  namespace: string;
  datasetName: string;
  options: ComputeEmbeddingIndexOptions;
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
  baseQuery: fastAPIBaseQuery(),
  tagTypes: [DATASETS_TAG],
  endpoints: (builder) => ({
    getDatasets: builder.query<DatasetInfo[], void>({
      query: () => () => DatasetsService.getDatasets(),
      providesTags: [DATASETS_TAG],
    }),
    // Loading datasets APIs.
    getSources: builder.query<SourcesList, void>({
      query: () => () => DataLoadersService.getSources(),
    }),
    getSourceSchema: builder.query<JSONSchema7, {sourceName: string}>({
      query:
        ({sourceName}: {sourceName: string}) =>
        () =>
          DataLoadersService.getSourceSchema(sourceName),
    }),
    loadDataset: builder.mutation<
      LoadDatasetResponse,
      {sourceName: string; options: LoadDatasetOptions}
    >({
      query:
        ({sourceName, options}: {sourceName: string; options: LoadDatasetOptions}) =>
        () =>
          DataLoadersService.load(sourceName, options),
      invalidatesTags: [DATASETS_TAG],
    }),
    // Dataset specific APIs.
    getManifest: builder.query<WebManifest, {namespace: string; datasetName: string}>({
      query:
        ({namespace, datasetName}) =>
        () =>
          DatasetsService.getManifest(namespace, datasetName),
    }),
    computeEmbeddingIndex: builder.mutation<Record<string, never>, ComputeEmbeddingIndexQueryArg>({
      query:
        ({namespace, datasetName, options: body}) =>
        () =>
          DatasetsService.computeEmbeddingIndex(namespace, datasetName, body),
    }),
    computeSignalColumn: builder.mutation<Record<string, never>, ComputeSignalColumnQueryArg>({
      query:
        ({namespace, datasetName, options: body}) =>
        () =>
          DatasetsService.computeSignalColumn(namespace, datasetName, body),
    }),
    getStats: builder.query<StatsResult, StatsQueryArg>({
      query:
        ({namespace, datasetName, options}) =>
        () =>
          DatasetsService.getStats(namespace, datasetName, options),
    }),
    selectRows: builder.query<Item[], SelectRowsQueryArg>({
      query:
        ({namespace, datasetName, options}) =>
        () =>
          DatasetsService.selectRows(namespace, datasetName, options),
    }),
    selectGroups: builder.query<[LeafValue, number][], SelectGroupsQueryArg>({
      query:
        ({namespace, datasetName, options}) =>
        () =>
          DatasetsService.selectGroups(namespace, datasetName, options),
    }),
    getMediaURL: builder.query<string, GetMediaQueryArg>({
      query:
        ({namespace, datasetName, itemId, leafPath}) =>
        () => {
          const url = new URL(`/api/v1/datasets/${namespace}/${datasetName}/media`);
          const params = {item_id: itemId, leaf_path: leafPath.join(',')};
          url.search = new URLSearchParams(params).toString();
          return url.toString();
        },
    }),
    getMultipleStats: builder.query<StatsResult[], MultipleStatsQueryArg>({
      query:
        ({namespace, datasetName, leafPaths}) =>
        async () => {
          const ps: Promise<StatsResult>[] = [];
          for (const leafPath of leafPaths) {
            ps.push(DatasetsService.getStats(namespace, datasetName, {leaf_path: leafPath}));
          }
          const statResults = await Promise.all(ps);
          return statResults;
        },
    }),
  }),
});

export const {
  useGetSourcesQuery,
  useComputeEmbeddingIndexMutation,
  useComputeSignalColumnMutation,
  useGetManifestQuery,
  useSelectRowsQuery,
  useSelectGroupsQuery,
  useGetStatsQuery,
  useGetMediaURLQuery,
  useGetMultipleStatsQuery,
  useGetDatasetsQuery,
  useGetSourceSchemaQuery,
  useLoadDatasetMutation,
} = datasetApi;
