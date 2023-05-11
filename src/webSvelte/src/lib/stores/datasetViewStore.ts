import {
  listFields,
  pathIsEqual,
  type Column,
  type Filter,
  type LilacSchema,
  type Path,
  type SelectRowsOptions,
  type SortOrder
} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export interface IDatasetViewStore {
  namespace: string;
  datasetName: string;
  visibleColumns: Path[];
  filters: Filter[];
  sortBy: Path[];
  sortOrder: SortOrder;
  udfColumns: Column[];
}

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;
export const createDatasetViewStore = (namespace: string, datasetName: string) => {
  const {subscribe, set, update} = writable<IDatasetViewStore>({
    namespace,
    datasetName,
    visibleColumns: [],
    filters: [],
    sortBy: [],
    sortOrder: 'ASC',
    udfColumns: []
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
        state.visibleColumns = state.visibleColumns.filter(c => !pathIsEqual(c, column));
        return state;
      }),

    addUdfColumn: (column: Column) =>
      update(state => {
        state.udfColumns?.push(column);
        return state;
      }),
    removeUdfColumn: (column: Column) =>
      update(state => {
        state.udfColumns = state.udfColumns.filter(c => c !== column);
        return state;
      }),

    addSortBy: (column: Path) =>
      update(state => {
        state.sortBy.push(column);
        return state;
      }),
    removeSortBy: (column: Path) =>
      update(state => {
        state.sortBy = state.sortBy.filter(c => !pathIsEqual(c, column));
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

/**
 * Get the options to pass to the selectRows API call
 * based on the current state of the dataset view store
 */
export function getSelectRowsOptions(
  datasetViewStore: IDatasetViewStore,
  schema: LilacSchema
): SelectRowsOptions {
  // TODO: Replace with * when supported
  const columns: (Column | Path)[] = listFields(schema).map(f => f.path);

  // Add extra columns (UDF's)
  columns.push(...datasetViewStore.udfColumns);

  return {
    filters: datasetViewStore.filters,
    sort_by: datasetViewStore.sortBy,
    sort_order: datasetViewStore.sortOrder,
    columns,
    combine_columns: true
  };
}
