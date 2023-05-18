import {
  listFields,
  pathIsEqual,
  type Column,
  type LilacSchema,
  type Path,
  type SelectRowsOptions
} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {persisted} from './persistedStore';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export interface IDatasetViewStore {
  namespace: string;
  datasetName: string;
  visibleColumns: Path[];
  queryOptions: SelectRowsOptions;
}

const LS_KEY = 'datasetViewStore';

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;
export const createDatasetViewStore = (namespace: string, datasetName: string) => {
  const initialState: IDatasetViewStore = {
    namespace,
    datasetName,
    visibleColumns: [],
    queryOptions: {
      filters: [],
      sort_by: [],
      sort_order: 'ASC',
      // Add * as default field when supported here
      columns: [],
      combine_columns: true
    }
  };

  const {subscribe, set, update} = persisted<IDatasetViewStore>(
    `${LS_KEY}/${namespace}/${datasetName}`,
    initialState,
    {
      storage: 'session'
    }
  );

  return {
    subscribe,
    set,
    update,
    reset: () => {
      set(initialState);
    },
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
        // Ensure that UDF's have an alias
        if (!column.alias && column.signal_udf?.signal_name)
          column.alias = `${column.path.join('_')}_${column.signal_udf?.signal_name}`;
        state.queryOptions.columns?.push(column);
        return state;
      }),
    removeUdfColumn: (column: Column) =>
      update(state => {
        state.queryOptions.columns = state.queryOptions.columns?.filter(c => c !== column);
        return state;
      }),

    addSortBy: (column: Path) =>
      update(state => {
        state.queryOptions.sort_by?.push(column);
        return state;
      }),
    removeSortBy: (column: Path) =>
      update(state => {
        state.queryOptions.sort_by = state.queryOptions.sort_by?.filter(
          c => !pathIsEqual(c, column)
        );
        return state;
      }),

    removeFilters: (column: Path) =>
      update(state => {
        state.queryOptions.filters = state.queryOptions.filters?.filter(
          c => !pathIsEqual(c.path, column)
        );
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
  const columns = [
    ...listFields(schema).map(f => f.path),
    ...(datasetViewStore.queryOptions.columns ?? [])
  ];

  return {
    ...datasetViewStore.queryOptions,
    columns
  };
}
