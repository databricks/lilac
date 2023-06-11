/** The store for runtime information about the dataset, like the schema and stats. */
import type {
  ApiError,
  LilacField,
  LilacSchema,
  LilacSelectRowsSchema,
  Path,
  StatsResult
} from '$lilac';
import type {QueryObserverResult} from '@tanstack/svelte-query';
import {getContext, hasContext, setContext} from 'svelte';
import {writable, type Readable, type Writable} from 'svelte/store';

const DATASET_INFO_CONTEXT = 'DATASET_INFO_CONTEXT';

export interface DatasetStore {
  schema: LilacSchema | null;
  stats: StatsInfo[] | null;
  selectRowsSchema: QueryObserverResult<LilacSelectRowsSchema, ApiError> | null;
  visibleFields: LilacField[] | null;
}
export interface StatsInfo {
  path: Path;
  stats: QueryObserverResult<StatsResult, unknown>;
}

export const createDatasetStore = () => {
  const initialState: DatasetStore = {
    schema: null,
    stats: null,
    selectRowsSchema: null,
    visibleFields: null
  };

  const {subscribe, set, update} = writable<DatasetStore>(initialState);

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
      })
  };
  return store;
};

export function setDatasetContext(stats: Writable<DatasetStore>) {
  setContext(DATASET_INFO_CONTEXT, stats);
}

export function getDatasetContext() {
  if (!hasContext(DATASET_INFO_CONTEXT)) throw new Error('DatasetViewContext not found');
  return getContext<Readable<DatasetStore>>(DATASET_INFO_CONTEXT);
}
