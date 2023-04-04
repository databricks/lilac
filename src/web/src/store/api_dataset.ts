/**
 * RTK Query APIs for the dataset service: 'dataset' tag in FastAPI.
 */
import {createApi} from '@reduxjs/toolkit/dist/query/react';
import {
  ComputeEmbeddingIndexOptions,
  ComputeSignalOptions,
  DatasetInfo,
  DatasetService,
  SortOrder,
  WebManifest,
} from '../../fastapi_client';

export interface SelectRowsQueryArg {
  namespace: string;
  datasetName: string;
  columns?: string;
  filters?: string;
  sortBy?: string;
  sortOrder?: SortOrder;
  limit?: number;
}

export interface ComputeEmbeddingQueryArg {
  namespace: string;
  datasetName: string;
  options: ComputeEmbeddingIndexOptions;
}

export interface ComputeSignalColumnQueryArg {
  namespace: string;
  datasetName: string;
  options: ComputeSignalOptions;
}

export const datasetApi = createApi({
  reducerPath: 'datasetApi',
  baseQuery: () => {
    return {error: 'baseQuery should never be called.'};
  },
  endpoints: (builder) => ({
    getDatasets: builder.query<DatasetInfo[], void>({
      queryFn: async () => {
        return {data: await DatasetService.getDatasets()};
      },
    }),
    getManifest: builder.query<WebManifest, {namespace: string; datasetName: string}>({
      queryFn: async ({namespace, datasetName}) => {
        return {data: await DatasetService.getManifest(namespace, datasetName)};
      },
    }),
    selectRows: builder.query<Array<unknown>, SelectRowsQueryArg>({
      queryFn: async ({namespace, datasetName, columns, filters, sortBy, sortOrder, limit}) => {
        return {
          data: await DatasetService.selectRows(
            namespace,
            datasetName,
            columns,
            filters,
            sortBy,
            sortOrder,
            limit
          ),
        };
      },
    }),
    computeEmbeddingIndex: builder.query<Record<string, never>, ComputeEmbeddingQueryArg>({
      queryFn: async ({namespace, datasetName, options: body}) => {
        return {
          data: await DatasetService.computeEmbeddingIndex(namespace, datasetName, body),
        };
      },
    }),
    computeSignalColumn: builder.query<Record<string, never>, ComputeSignalColumnQueryArg>({
      queryFn: async ({namespace, datasetName, options: body}) => {
        return {
          data: await DatasetService.computeSignalColumn(namespace, datasetName, body),
        };
      },
    }),
  }),
});

export const {
  useGetDatasetsQuery,
  useComputeEmbeddingIndexQuery,
  useComputeSignalColumnQuery,
  useGetManifestQuery,
  useSelectRowsQuery,
} = datasetApi;
