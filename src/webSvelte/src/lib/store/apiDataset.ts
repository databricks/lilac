import {
  DataLoadersService,
  DatasetsService,
  UUID_COLUMN,
  type DataType,
  type Filter,
  type SelectRowsOptions
} from '$lilac';
import { createInfiniteQuery } from '@tanstack/svelte-query';
import { createApiMutation, createApiQuery } from './apiUtils';

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
  'boolean'
];

const DATASETS_TAG = 'datasets';

export const useGetDatasetsQuery = createApiQuery(DatasetsService.getDatasets, DATASETS_TAG);
export const useGetManifestQuery = createApiQuery(DatasetsService.getManifest, DATASETS_TAG);

export const useGetSourcesQuery = createApiQuery(DataLoadersService.getSources, DATASETS_TAG);
export const useGetSourceSchemaQuery = createApiQuery(
  DataLoadersService.getSourceSchema,
  DATASETS_TAG
);
export const useLoadDatasetMutation = createApiMutation(DataLoadersService.load, DATASETS_TAG);
export const useComputeSignalColumnMutation = createApiMutation(
  DatasetsService.computeSignalColumn,
  DATASETS_TAG
);
export const useGetStatsQuery = createApiQuery(DatasetsService.getStats, DATASETS_TAG);
export const useSelectRowsQuery = createApiQuery(DatasetsService.selectRows, DATASETS_TAG);
export const useSelectGroupsQuery = createApiQuery(DatasetsService.selectGroups, DATASETS_TAG);

export const useSelectRowsInfiniteQuery = (
  namespace: string,
  datasetName: string,
  options: SelectRowsOptions
) =>
  createInfiniteQuery({
    queryKey: [DATASETS_TAG, 'selectRows', namespace, datasetName, options],
    queryFn: ({ pageParam = 0 }) =>
      DatasetsService.selectRows(namespace, datasetName, {
        ...options,
        offset: pageParam * (options.limit || 40)
      }),
    getNextPageParam: (lastPage, pages) => pages.length
  });

export const useSelectRowByUUIDQuery = (namespace: string, datasetName: string, uuid: string) => {
  const filters: Filter[] = [{ path: [UUID_COLUMN], comparison: 'equals', value: uuid }];
  return useSelectRowsQuery(namespace, datasetName, { filters });
};
