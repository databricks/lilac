import {
  isColumn,
  pathIncludes,
  pathIsEqual,
  serializePath,
  type Column,
  type Path,
  type Search,
  type SearchType,
  type SelectRowsOptions
} from '$lilac';
import {getContext, hasContext, setContext} from 'svelte';
import {persisted} from './persistedStore';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export const SEARCH_TABS: {[key: number]: 'Keyword' | 'Semantic' | 'Concepts'} = {
  0: 'Keyword',
  1: 'Semantic',
  2: 'Concepts'
};

export interface IDatasetViewStore {
  namespace: string;
  datasetName: string;

  // Explicit user-selected columns.
  selectedColumns: {[path: string]: boolean};
  queryOptions: SelectRowsOptions;

  // Search.
  searchTab: (typeof SEARCH_TABS)[keyof typeof SEARCH_TABS];
  searchPath: string | null;
  searchEmbedding: string | null;
}

const LS_KEY = 'datasetViewStore';

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;

export const datasetStores: {[key: string]: DatasetViewStore} = {};

export function datasetKey(namespace: string, datasetName: string) {
  return `${namespace}/${datasetName}`;
}

export const createDatasetViewStore = (namespace: string, datasetName: string) => {
  const initialState: IDatasetViewStore = {
    namespace,
    datasetName,
    searchTab: 'Keyword',
    searchPath: null,
    searchEmbedding: null,
    selectedColumns: {},
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
    `${LS_KEY}/${datasetKey(namespace, datasetName)}`,
    initialState,
    {
      storage: 'session'
    }
  );

  const store = {
    subscribe,
    set,
    update,
    reset: () => {
      set(initialState);
    },

    addSelectedColumn: (path: Path | string) =>
      update(state => {
        state.selectedColumns[serializePath(path)] = true;
        return state;
      }),
    removeSelectedColumn: (path: Path | string) =>
      update(state => {
        state.selectedColumns[serializePath(path)] = false;
        // Remove any explicit children.
        for (const childPath of Object.keys(state.selectedColumns)) {
          if (pathIncludes(childPath, path) && !pathIsEqual(path, childPath)) {
            delete state.selectedColumns[childPath];
          }
        }
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

    setSearchTab: (tab: (typeof SEARCH_TABS)[keyof typeof SEARCH_TABS]) =>
      update(state => {
        state.searchTab = tab;
        return state;
      }),
    setSearchPath: (path: Path | string) =>
      update(state => {
        state.searchPath = serializePath(path);
        return state;
      }),
    setSearchEmbedding: (embedding: string) =>
      update(state => {
        state.searchEmbedding = embedding;
        return state;
      }),
    addSearch: (search: Search) =>
      update(state => {
        if (search.type === 'semantic' || search.type == 'contains') {
          // Remove existing searches with this type. Semantic and keyword search only allow a
          // single search.
          state.queryOptions.searches = state.queryOptions.searches?.filter(
            s => s.type !== search.type
          );
        }

        state.queryOptions.searches = state.queryOptions.searches || [];
        state.queryOptions.searches.push(search);

        return state;
      }),
    clearSearch: (search: Search) =>
      update(state => {
        state.queryOptions.searches = state.queryOptions.searches?.filter(s => s !== search);

        return state;
      }),
    clearSearchType: (searchType: SearchType) =>
      update(state => {
        // Remove existing searches with this type. Semantic and keyword search only allow a
        // single search.
        state.queryOptions.searches = state.queryOptions.searches?.filter(
          s => s.type !== searchType
        );

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

  datasetStores[datasetKey(namespace, datasetName)] = store;
  return store;
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
