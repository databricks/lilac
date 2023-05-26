import {
  ApiError,
  DataLoadersService,
  DatasetsService,
  deserializeRow,
  deserializeSchema,
  type DataType,
  type LilacSchema,
  type Path,
  type SelectRowsOptions
} from '$lilac';
import {createInfiniteQuery, type CreateInfiniteQueryResult} from '@tanstack/svelte-query';
import type {JSONSchema7} from 'json-schema';
import {watchTask} from '../stores/taskMonitoringStore';
import {queryClient} from './queryClient';
import {createApiMutation, createApiQueries, createApiQuery} from './queryUtils';
import {TASKS_TAG} from './taskQueries';

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

export const DATASETS_TAG = 'datasets';

export const queryDatasets = createApiQuery(DatasetsService.getDatasets, DATASETS_TAG);
export const queryDatasetManifest = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {});

export const queryDatasetSchema = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {
  select: res => deserializeSchema(res.dataset_manifest.data_schema)
});

export const querySources = createApiQuery(DataLoadersService.getSources, DATASETS_TAG);
export const querySourcesSchema = createApiQuery(DataLoadersService.getSourceSchema, DATASETS_TAG, {
  select: res => res as JSONSchema7
});
export const loadDatasetMutation = createApiMutation(DataLoadersService.load);
export const computeSignalColumnMutation = createApiMutation(DatasetsService.computeSignalColumn, {
  onSuccess: resp => {
    queryClient.invalidateQueries([TASKS_TAG]);

    watchTask(resp.task_id, () => {
      queryClient.invalidateQueries([DATASETS_TAG, 'getManifest']);
      queryClient.invalidateQueries([DATASETS_TAG, 'selectRowsSchema']);
      queryClient.invalidateQueries([DATASETS_TAG, 'selectRows']);
    });
  }
});
export const queryDatasetStats = createApiQuery(DatasetsService.getStats, DATASETS_TAG);
export const queriesDatasetStats = createApiQueries(DatasetsService.getStats, DATASETS_TAG);
export const querySelectRows = createApiQuery(function selectRows(
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
export const querySelectRowsSchema = createApiQuery(
  DatasetsService.selectRowsSchema,
  DATASETS_TAG,
  {
    select: res => deserializeSchema(res.data_schema, res.alias_udf_paths as Record<string, Path>)
  }
);

export const querySelectRowsAliasUdfPaths = createApiQuery(
  DatasetsService.selectRowsSchema,
  DATASETS_TAG,
  {
    select: res => res.alias_udf_paths
  }
);
export const querySelectGroups = createApiQuery(DatasetsService.selectGroups, DATASETS_TAG);

export const infiniteQuerySelectRows = (
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
