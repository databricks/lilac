import {
  ApiError,
  DataLoadersService,
  DatasetsService,
  UUID_COLUMN,
  deserializeRow,
  deserializeSchema,
  type DataType,
  type Filter,
  type LilacSchema,
  type SelectRowsOptions
} from '$lilac';
import {createInfiniteQuery, type CreateInfiniteQueryResult} from '@tanstack/svelte-query';
import type {JSONSchema7} from 'json-schema';
import {TASKS_TAG} from './apiServer';
import {createApiMutation, createApiQuery} from './apiUtils';
import {queryClient} from './queryClient';
import {watchTask} from './taskMonitoring';

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
export const useGetManifestQuery = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {});

export const useGetSchemaQuery = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {
  select: res => deserializeSchema(res.dataset_manifest.data_schema)
});

export const useGetSourcesQuery = createApiQuery(DataLoadersService.getSources, DATASETS_TAG);
export const useGetSourceSchemaQuery = createApiQuery(
  DataLoadersService.getSourceSchema,
  DATASETS_TAG,
  {select: res => res as JSONSchema7}
);
export const useLoadDatasetMutation = createApiMutation(DataLoadersService.load);
export const useComputeSignalColumnMutation = createApiMutation(
  DatasetsService.computeSignalColumn,
  {
    onSuccess: resp => {
      queryClient.invalidateQueries([TASKS_TAG]);

      watchTask(resp.task_id, () => {
        queryClient.invalidateQueries([DATASETS_TAG, 'getManifest']);
        queryClient.invalidateQueries([DATASETS_TAG, 'selectRows']);
      });
    }
  }
);
export const useGetStatsQuery = createApiQuery(DatasetsService.getStats, DATASETS_TAG);
export const useSelectRowsQuery = createApiQuery(function selectRows(
  namespace: string,
  datasetName: string,
  requestBody: SelectRowsOptions,
  schema: LilacSchema
) {
  return DatasetsService.selectRows(namespace, datasetName, requestBody).then(res =>
    res.map(row => deserializeRow(row, schema))
  );
},
DATASETS_TAG);
export const useSelectGroupsQuery = createApiQuery(DatasetsService.selectGroups, DATASETS_TAG);

export const useSelectRowsInfiniteQuery = (
  namespace: string,
  datasetName: string,
  selectRowOptions: SelectRowsOptions,
  schema: LilacSchema | undefined
): CreateInfiniteQueryResult<Awaited<ReturnType<typeof DatasetsService.selectRows>>, ApiError> =>
  createInfiniteQuery({
    queryKey: [DATASETS_TAG, 'selectRows', namespace, datasetName, selectRowOptions],
    queryFn: ({pageParam = 0}) =>
      DatasetsService.selectRows(namespace, datasetName, {
        ...selectRowOptions,
        offset: pageParam * (selectRowOptions.limit || 40)
      }),
    select: data => ({
      ...data,
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      pages: data.pages.map(page => page.map(row => deserializeRow(row, schema!)))
    }),
    getNextPageParam: (_, pages) => pages.length,
    enabled: !!schema
  });

export const useSelectRowByUUIDQuery = (
  namespace: string,
  datasetName: string,
  uuid: string,
  schema: LilacSchema
) => {
  const filters: Filter[] = [{path: [UUID_COLUMN], comparison: 'equals', value: uuid}];
  return useSelectRowsQuery(namespace, datasetName, {filters}, schema);
};
