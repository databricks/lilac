/** The store for runtime information about the dataset, like the schema and stats. */
import type {
  ApiError,
  DatasetSettings,
  LilacField,
  LilacSchema,
  LilacSelectRowsSchema,
  Path,
  StatsResult
} from '$lilac';
import type {QueryObserverResult} from '@tanstack/svelte-query';
import {getContext, hasContext, setContext} from 'svelte';
import {writable, type Readable, type Writable} from 'svelte/store';
import {datasetKey} from './datasetViewStore';

const DATASET_INFO_CONTEXT = 'DATASET_INFO_CONTEXT';
export const datasetStores: {[key: string]: DatasetStore} = {};

export interface DatasetState {
  schema: LilacSchema | null;
  stats: StatsInfo[] | null;
  selectRowsSchema: QueryObserverResult<LilacSelectRowsSchema, ApiError> | null;
  visibleFields: LilacField[] | null;
  settings: DatasetSettings | null;
}

export interface StatsInfo {
  path: Path;
  stats: QueryObserverResult<StatsResult, unknown>;
}

export type DatasetStore = ReturnType<typeof createDatasetStore>;

export const createDatasetStore = (namespace: string, datasetName: string) => {
  const initialState: DatasetState = {
    schema: null,
    stats: null,
    selectRowsSchema: null,
    visibleFields: null,
    settings: null
  };

  const {subscribe, set, update} = writable<DatasetState>(initialState);

  const store = {
    subscribe,
    set,
    update,
    reset: () => {
      set(initialState);
    },

    setSchema: (schema: LilacSchema) =>
      update(state => {
        state.schema = schema;
        return state;
      }),
    setStats: (stats: StatsInfo[]) =>
      update(state => {
        state.stats = stats;
        return state;
      }),
    setVisibleFields: (visibleFields: LilacField[]) =>
      update(state => {
        state.visibleFields = visibleFields;
        return state;
      }),
    setSelectRowsSchema: (
      selectRowsSchema: QueryObserverResult<LilacSelectRowsSchema, ApiError> | null
    ) =>
      update(state => {
        state.selectRowsSchema = selectRowsSchema;
        return state;
      }),
    setSettings: (settings: DatasetSettings) =>
      update(state => {
        state.settings = settings;
        return state;
      })
  };
  datasetStores[datasetKey(namespace, datasetName)] = store;
  return store;
};

export function setDatasetContext(store: Writable<DatasetState>) {
  setContext(DATASET_INFO_CONTEXT, store);
}

export function getDatasetContext() {
  if (!hasContext(DATASET_INFO_CONTEXT)) throw new Error('DatasetViewContext not found');
  return getContext<Readable<DatasetState>>(DATASET_INFO_CONTEXT);
}
