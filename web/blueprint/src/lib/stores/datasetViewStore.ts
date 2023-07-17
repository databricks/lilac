import {
  isColumn,
  pathIncludes,
  pathIsEqual,
  serializePath,
  type BinaryFilter,
  type Column,
  type ConceptQuery,
  type KeywordQuery,
  type LilacSelectRowsSchema,
  type ListFilter,
  type Path,
  type Search,
  type SelectRowsOptions,
  type SelectRowsSchemaOptions,
  type SemanticQuery,
  type SortOrder,
  type UnaryFilter
} from '$lilac';
import deepEqual from 'deep-equal';
import {getContext, hasContext, setContext} from 'svelte';
import {persisted} from './persistedStore';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export interface DatasetViewState {
  namespace: string;
  datasetName: string;

  // Explicit user-selected columns.
  selectedColumns: {[path: string]: boolean};
  expandedColumns: {[path: string]: boolean};
  queryOptions: SelectRowsOptions;

  // Search.
  searchPath: string | null;
  searchEmbedding: string | null;

  // View.
  schemaCollapsed: boolean;
}

const LS_KEY = 'datasetViewStore';

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;

export const datasetViewStores: {[key: string]: DatasetViewStore} = {};

export function datasetKey(namespace: string, datasetName: string) {
  return `${namespace}/${datasetName}`;
}

export const createDatasetViewStore = (namespace: string, datasetName: string) => {
  const initialState: DatasetViewState = {
    namespace,
    datasetName,
    searchPath: null,
    searchEmbedding: null,
    selectedColumns: {},
    expandedColumns: {},
    queryOptions: {
      // Add * as default field when supported here
      columns: [],
      combine_columns: true
    },
    schemaCollapsed: false
  };

  const {subscribe, set, update} = persisted<DatasetViewState>(
    `${LS_KEY}/${datasetKey(namespace, datasetName)}`,
    // Deep copy the initial state so we don't have to worry about mucking the initial state.
    JSON.parse(JSON.stringify(initialState)),
    {
      storage: 'session'
    }
  );

  const store = {
    subscribe,
    set,
    update,
    reset: () => {
      set(JSON.parse(JSON.stringify(initialState)));
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
    addExpandedColumn(path: Path) {
      update(state => {
        state.expandedColumns[serializePath(path)] = true;
        return state;
      });
    },
    removeExpandedColumn(path: Path) {
      update(state => {
        state.expandedColumns[serializePath(path)] = false;
        return state;
      });
    },
    addUdfColumn: (column: Column) =>
      update(state => {
        state.queryOptions.columns?.push(column);
        return state;
      }),
    removeUdfColumn: (column: Column) =>
      update(state => {
        state.queryOptions.columns = state.queryOptions.columns?.filter(c => c !== column);
        return state;
      }),
    editUdfColumn: (column: Column) => {
      return update(state => {
        state.queryOptions.columns = state.queryOptions.columns?.map(c => {
          if (isColumn(c) && pathIsEqual(c.path, column.path)) return column;
          return c;
        });
        return state;
      });
    },

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
        state.queryOptions.searches = state.queryOptions.searches || [];

        // Dedupe searches.
        for (const existingSearch of state.queryOptions.searches) {
          if (deepEqual(existingSearch, search)) return state;
        }

        // Remove any sorts if the search is semantic or conceptual.
        if (search.query.type === 'semantic' || search.query.type === 'concept') {
          state.queryOptions.sort_by = undefined;
          state.queryOptions.sort_order = undefined;
        }

        state.queryOptions.searches.push(search);
        return state;
      }),
    removeSearch: (search: Search, selectRowsSchema?: LilacSelectRowsSchema | null) =>
      update(state => {
        state.queryOptions.searches = state.queryOptions.searches?.filter(
          s => !deepEqual(s, search)
        );
        // Clear any explicit sorts by this alias as it will be an invalid sort.
        if (selectRowsSchema?.sorts != null) {
          state.queryOptions.sort_by = state.queryOptions.sort_by?.filter(sortBy => {
            return !(selectRowsSchema?.sorts || []).some(s => pathIsEqual(s.path, sortBy));
          });
        }
        return state;
      }),
    setSortBy: (column: Path | null) =>
      update(state => {
        if (column == null) {
          state.queryOptions.sort_by = undefined;
        } else {
          state.queryOptions.sort_by = [column];
        }
        return state;
      }),
    addSortBy: (column: Path) =>
      update(state => {
        state.queryOptions.sort_by = [...(state.queryOptions.sort_by || []), column];
        return state;
      }),
    removeSortBy: (column: Path) =>
      update(state => {
        state.queryOptions.sort_by = state.queryOptions.sort_by?.filter(
          c => !pathIsEqual(c, column)
        );
        return state;
      }),
    clearSorts: () =>
      update(state => {
        state.queryOptions.sort_by = undefined;
        state.queryOptions.sort_order = undefined;
        return state;
      }),
    setSortOrder: (sortOrder: SortOrder | null) =>
      update(state => {
        state.queryOptions.sort_order = sortOrder || undefined;
        return state;
      }),
    removeFilter: (removedFilter: BinaryFilter | UnaryFilter | ListFilter) =>
      update(state => {
        state.queryOptions.filters = state.queryOptions.filters?.filter(
          f => !deepEqual(f, removedFilter)
        );
        return state;
      }),
    addFilter: (filter: BinaryFilter | UnaryFilter | ListFilter) =>
      update(state => {
        state.queryOptions.filters = [...(state.queryOptions.filters || []), filter];
        return state;
      }),
    deleteSignal: (signalPath: Path) =>
      update(state => {
        state.queryOptions.filters = state.queryOptions.filters?.filter(
          f => !pathIncludes(signalPath, f.path)
        );
        state.queryOptions.sort_by = state.queryOptions.sort_by?.filter(
          p => !pathIncludes(signalPath, p)
        );
        return state;
      }),
    deleteConcept(
      namespace: string,
      name: string,
      selectRowsSchema?: LilacSelectRowsSchema | null
    ) {
      function matchesConcept(query: KeywordQuery | SemanticQuery | ConceptQuery) {
        return (
          query.type === 'concept' &&
          query.concept_namespace === namespace &&
          query.concept_name === name
        );
      }
      update(state => {
        const resultPathsToRemove: string[][] = [];
        state.queryOptions.searches = state.queryOptions.searches?.filter(s => {
          const keep = !matchesConcept(s.query);
          if (!keep && selectRowsSchema != null && selectRowsSchema.search_results != null) {
            const resultPaths = selectRowsSchema.search_results
              .filter(r => pathIsEqual(r.search_path, s.path))
              .map(r => r.result_path);
            resultPathsToRemove.push(...resultPaths);
          }
          return keep;
        });
        state.queryOptions.sort_by = state.queryOptions.sort_by?.filter(
          p => !resultPathsToRemove.some(r => pathIsEqual(r, p))
        );
        state.queryOptions.filters = state.queryOptions.filters?.filter(
          f => !resultPathsToRemove.some(r => pathIsEqual(r, f.path))
        );
        return state;
      });
    }
  };

  datasetViewStores[datasetKey(namespace, datasetName)] = store;
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
export function getSelectRowsOptions(datasetViewStore: DatasetViewState): SelectRowsOptions {
  const columns = ['*', ...(datasetViewStore.queryOptions.columns ?? [])];

  return {
    ...datasetViewStore.queryOptions,
    columns
  };
}

export function getSelectRowsSchemaOptions(
  datasetViewStore: DatasetViewState
): SelectRowsSchemaOptions {
  const options = getSelectRowsOptions(datasetViewStore);
  return {
    columns: options.columns,
    searches: options.searches,
    combine_columns: options.combine_columns,
    sort_by: options.sort_by,
    sort_order: options.sort_order
  };
}
