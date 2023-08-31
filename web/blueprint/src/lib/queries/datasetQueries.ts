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
import {createApiMutation, createApiQuery} from './queryUtils';
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
export const DATASETS_CONFIG_TAG = 'config';
export const DATASETS_SETTINGS_TAG = 'settings';

export const DEFAULT_SELECT_ROWS_LIMIT = 20;

export const queryDatasets = createApiQuery(DatasetsService.getDatasets, DATASETS_TAG);
export const queryDatasetManifest = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {});

export const queryDatasetSchema = createApiQuery(DatasetsService.getManifest, DATASETS_TAG, {
  select: res => deserializeSchema(res.dataset_manifest.data_schema)
});

export const maybeQueryDatasetSchema = createApiQuery(
  function getManifest(namespace?: string, datasetName?: string) {
    return namespace && datasetName
      ? DatasetsService.getManifest(namespace, datasetName)
      : Promise.resolve(undefined);
  },
  DATASETS_TAG,
  {
    select: res => (res ? deserializeSchema(res.dataset_manifest.data_schema) : undefined)
  }
);

export const querySources = createApiQuery(DataLoadersService.getSources, DATASETS_TAG);
export const querySourcesSchema = createApiQuery(DataLoadersService.getSourceSchema, DATASETS_TAG, {
  select: res => res as JSONSchema7
});
export const loadDatasetMutation = createApiMutation(DataLoadersService.load, {
  onSuccess: resp => {
    queryClient.invalidateQueries([TASKS_TAG]);

    watchTask(resp.task_id, () => {
      queryClient.invalidateQueries([DATASETS_TAG, 'getDatasets']);
    });
  }
});
export const computeSignalMutation = createApiMutation(DatasetsService.computeSignal, {
  onSuccess: resp => {
    queryClient.invalidateQueries([TASKS_TAG]);

    watchTask(resp.task_id, () => {
      queryClient.invalidateQueries([DATASETS_TAG, 'getManifest']);
      queryClient.invalidateQueries([DATASETS_TAG, 'selectRowsSchema']);
      queryClient.invalidateQueries([DATASETS_TAG, 'selectRows']);
      queryClient.invalidateQueries([DATASETS_CONFIG_TAG]);
    });
  }
});

export const deleteDatasetMutation = createApiMutation(DatasetsService.deleteDataset, {
  onSuccess: () => {
    queryClient.invalidateQueries([DATASETS_TAG]);
  }
});

export const deleteSignalMutation = createApiMutation(DatasetsService.deleteSignal, {
  onSuccess: () => {
    queryClient.invalidateQueries([DATASETS_TAG, 'getManifest']);
    queryClient.invalidateQueries([DATASETS_TAG, 'selectRowsSchema']);
    queryClient.invalidateQueries([DATASETS_TAG, 'selectRows']);
    queryClient.invalidateQueries([DATASETS_CONFIG_TAG]);
  }
});

export const queryDatasetStats = createApiQuery(DatasetsService.getStats, DATASETS_TAG);
export const queryManyDatasetStats = createApiQuery(function getStats(
  namespace: string,
  datasetName: string,
  leafs: Path[]
) {
  const ps = leafs.map(leaf => DatasetsService.getStats(namespace, datasetName, {leaf_path: leaf}));
  return Promise.all(ps);
},
DATASETS_TAG);

export const querySelectRows = createApiQuery(async function selectRows(
  namespace: string,
  datasetName: string,
  requestBody: SelectRowsOptions,
  schema?: LilacSchema
) {
  const res = await DatasetsService.selectRows(namespace, datasetName, requestBody);
  return {
    rows: schema == null ? res.rows : res.rows.map(row => deserializeRow(row, schema)),
    total_num_rows: res.total_num_rows
  };
},
'DATASETS_TAG');

export const querySelectRowsSchema = createApiQuery(
  DatasetsService.selectRowsSchema,
  DATASETS_TAG,
  {
    select: res => {
      return {
        schema: deserializeSchema(res.data_schema),
        ...res
      };
    }
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
        limit: selectRowOptions.limit || DEFAULT_SELECT_ROWS_LIMIT,
        offset: pageParam * (selectRowOptions.limit || DEFAULT_SELECT_ROWS_LIMIT)
      }),
    select: data => ({
      ...data,
      pages: data.pages.map(page => ({
        rows: page.rows.map(row => deserializeRow(row, schema!)),
        total_num_rows: page.total_num_rows
      }))
    }),
    getNextPageParam: (_, pages) => pages.length,
    enabled: !!schema
  });

export const queryConfig = createApiQuery(DatasetsService.getConfig, DATASETS_CONFIG_TAG);
export const querySettings = createApiQuery(DatasetsService.getSettings, DATASETS_SETTINGS_TAG);
export const updateDatasetSettingsMutation = createApiMutation(DatasetsService.updateSettings, {
  onSuccess: () => {
    queryClient.invalidateQueries([DATASETS_SETTINGS_TAG]);
    queryClient.invalidateQueries([DATASETS_CONFIG_TAG]);
  }
});
