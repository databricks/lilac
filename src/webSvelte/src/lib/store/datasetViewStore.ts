import type {Column, Filter, Path} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;
export const createDatasetViewStore = (namespace: string, datasetName: string) => {
  const {subscribe, set, update} = writable<{
    namespace: string;
    datasetName: string;
    visibleColumns: Path[];
    filters: Filter[];
    sortBy?: Path[];
    extraColumns: Column[];
  }>({
    namespace,
    datasetName,
    visibleColumns: [],
    filters: [],
    sortBy: [],
    extraColumns: []
  });

  return {
    subscribe,
    set,
    update,
    addVisibleColumn: (column: Path) =>
      update(state => {
        state.visibleColumns.push(column);
        return state;
      }),
    removeVisibleColumn: (column: Path) =>
      update(state => {
        state.visibleColumns = state.visibleColumns.filter(c => c.join('.') !== column.join('.'));
        return state;
      }),

    addExtraColumn: (column: Column) =>
      update(state => {
        state.extraColumns?.push(column);
        return state;
      }),
    removeExtraColumn: (column: Column) =>
      update(state => {
        state.extraColumns = state.extraColumns.filter(c => c !== column);
        return state;
      })
  };
};

export function setDatasetViewContext(store: DatasetViewStore) {
  setContext(DATASET_VIEW_CONTEXT, store);
}

export function getDatasetViewContext() {
  if (!hasContext(DATASET_VIEW_CONTEXT)) throw new Error('DatasetViewContext not found');
  return getContext<DatasetViewStore>(DATASET_VIEW_CONTEXT);
}
