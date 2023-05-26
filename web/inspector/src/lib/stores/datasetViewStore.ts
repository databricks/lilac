import {
  isColumn,
  pathIncludes,
  pathIsEqual,
  type Column,
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
      searches: [],
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
    addVisibleColumn: (column: Path) => {
      return update(state => {
        if (state.visibleColumns.some(c => pathIsEqual(c, column))) return state;
        state.visibleColumns.push(column);
        return state;
      });
    },
    removeVisibleColumn: (column: Path) =>
      update(state => {
        state.visibleColumns = state.visibleColumns.filter(c => !pathIsEqual(c, column));
        return state;
      }),

    addUdfColumn: (column: Column) =>
      update(state => {
        // Parse out current udf aliases, and make sure the new one is unique
        let aliasNumbers = state.queryOptions.columns
          ?.filter(isColumn)
          .map(c => c.alias?.match(/udf(\d+)/)?.[1])
          .filter(Boolean)
          .map(Number);
        if (!aliasNumbers?.length) aliasNumbers = [0];
        // Ensure that UDF's have an alias
        if (!column.alias && column.signal_udf?.signal_name)
          column.alias = `udf${Math.max(...aliasNumbers) + 1}`;
        state.queryOptions.columns?.push(column);
        return state;
      }),
    removeUdfColumn: (column: Column) =>
      update(state => {
        state.queryOptions.columns = state.queryOptions.columns?.filter(c => c !== column);
        return state;
      }),
    editUdfColumn: (alias: string, column: Column) => {
      return update(state => {
        state.queryOptions.columns = state.queryOptions.columns?.map(c => {
          if (isColumn(c) && c.alias == alias) return column;
          return c;
        });
        return state;
      });
    },

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
export function getSelectRowsOptions(datasetViewStore: IDatasetViewStore): SelectRowsOptions {
  const columns = ['*', ...(datasetViewStore.queryOptions.columns ?? [])];

  return {
    ...datasetViewStore.queryOptions,
    columns
  };
}

export function isPathVisible(
  visibleColumns: IDatasetViewStore['visibleColumns'],
  path: Path,
  aliasMapping: Record<string, Path> | undefined
) {
  return (
    visibleColumns
      // Map aliased columns to their full path
      .map(c => (aliasMapping?.[c[0]] && [...aliasMapping[c[0]], ...c.slice(1)]) ?? c)
      .some(c => {
        // Check if path is in the visible columns array
        if (pathIsEqual(c, path)) return true;
        // Check if a child path is in visible rows
        if (pathIncludes(c, path)) return true;
        return false;
      })
  );
}
