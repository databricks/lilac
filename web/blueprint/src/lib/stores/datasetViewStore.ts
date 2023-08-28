import {
  isColumn,
  pathIncludes,
  pathIsEqual,
  serializePath,
  type Column,
  type Filter,
  type LilacSelectRowsSchema,
  type Path,
  type Search,
  type SelectRowsOptions,
  type SelectRowsSchemaOptions,
  type SortOrder
} from '$lilac';
import deepEqual from 'deep-equal';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const DATASET_VIEW_CONTEXT = 'DATASET_VIEW_CONTEXT';

export interface DatasetViewState {
  namespace: string;
  datasetName: string;

  // Explicit user-selected columns.
  selectedColumns: {[path: string]: boolean};
  expandedColumns: {[path: string]: boolean};
  query: SelectRowsOptions;

  // View.
  schemaCollapsed: boolean;
}

export type DatasetViewStore = ReturnType<typeof createDatasetViewStore>;

export const datasetViewStores: {[key: string]: DatasetViewStore} = {};

export function datasetKey(namespace: string, datasetName: string) {
  return `${namespace}/${datasetName}`;
}

export function defaultDatasetViewState(namespace: string, datasetName: string): DatasetViewState {
  return {
    namespace,
    datasetName,
    selectedColumns: {},
    expandedColumns: {},
    query: {
      // Add * as default field when supported here
      columns: [],
      combine_columns: true
    },
    schemaCollapsed: true
  };
}

export function createDatasetViewStore(
  namespace: string,
  datasetName: string,
  // Whether the store gets saved to the global dictionary.
  saveGlobally = true
) {
  const defaultState = defaultDatasetViewState(namespace, datasetName);

  const {subscribe, set, update} = writable<DatasetViewState>(
    // Deep copy the initial state so we don't have to worry about mucking the initial state.
    JSON.parse(JSON.stringify(defaultState))
  );

  const store = {
    subscribe,
    set,
    update,
    reset: () => {
      set(JSON.parse(JSON.stringify(defaultState)));
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
        delete state.expandedColumns[serializePath(path)];
        return state;
      });
    },
    addUdfColumn: (column: Column) =>
      update(state => {
        state.query.columns?.push(column);
        return state;
      }),
    removeUdfColumn: (column: Column) =>
      update(state => {
        state.query.columns = state.query.columns?.filter(c => c !== column);
        return state;
      }),
    editUdfColumn: (column: Column) => {
      return update(state => {
        state.query.columns = state.query.columns?.map(c => {
          if (isColumn(c) && pathIsEqual(c.path, column.path)) return column;
          return c;
        });
        return state;
      });
    },
    addSearch: (search: Search) =>
      update(state => {
        state.query.searches = state.query.searches || [];

        // Dedupe searches.
        for (const existingSearch of state.query.searches) {
          if (deepEqual(existingSearch, search)) return state;
        }

        // Remove any sorts if the search is semantic or conceptual.
        if (search.type === 'semantic' || search.type === 'concept') {
          state.query.sort_by = undefined;
          state.query.sort_order = undefined;
        }

        state.query.searches.push(search);
        return state;
      }),
    removeSearch: (search: Search, selectRowsSchema?: LilacSelectRowsSchema | null) =>
      update(state => {
        state.query.searches = state.query.searches?.filter(s => !deepEqual(s, search));
        if ((state.query.searches || []).length === 0) {
          state.query.searches = undefined;
        }
        // Clear any explicit sorts by this alias as it will be an invalid sort.
        if (selectRowsSchema?.sorts != null) {
          state.query.sort_by = state.query.sort_by?.filter(sortBy => {
            return !(selectRowsSchema?.sorts || []).some(s => pathIsEqual(s.path, sortBy));
          });
        }
        return state;
      }),
    setSortBy: (column: Path | null) =>
      update(state => {
        if (column == null) {
          state.query.sort_by = undefined;
        } else {
          state.query.sort_by = [column];
        }
        return state;
      }),
    addSortBy: (column: Path) =>
      update(state => {
        state.query.sort_by = [...(state.query.sort_by || []), column];
        return state;
      }),
    removeSortBy: (column: Path) =>
      update(state => {
        state.query.sort_by = state.query.sort_by?.filter(c => !pathIsEqual(c, column));
        return state;
      }),
    clearSorts: () =>
      update(state => {
        state.query.sort_by = undefined;
        state.query.sort_order = undefined;
        return state;
      }),
    setSortOrder: (sortOrder: SortOrder | null) =>
      update(state => {
        state.query.sort_order = sortOrder || undefined;
        return state;
      }),
    removeFilter: (removedFilter: Filter) =>
      update(state => {
        state.query.filters = state.query.filters?.filter(f => !deepEqual(f, removedFilter));
        if ((state.query.filters || []).length === 0) {
          state.query.filters = undefined;
        }
        return state;
      }),
    addFilter: (filter: Filter) =>
      update(state => {
        const filterExists = state.query.filters?.some(f => filterEquals(f, filter));
        if (filterExists) return state;
        state.query.filters = [...(state.query.filters || []), filter];
        return state;
      }),
    deleteSignal: (signalPath: Path) =>
      update(state => {
        state.query.filters = state.query.filters?.filter(f => !pathIncludes(signalPath, f.path));
        state.query.sort_by = state.query.sort_by?.filter(p => !pathIncludes(signalPath, p));
        return state;
      }),
    deleteConcept(
      namespace: string,
      name: string,
      selectRowsSchema?: LilacSelectRowsSchema | null
    ) {
      function matchesConcept(query: Search) {
        return (
          query.type === 'concept' &&
          query.concept_namespace === namespace &&
          query.concept_name === name
        );
      }
      update(state => {
        const resultPathsToRemove: string[][] = [];
        state.query.searches = state.query.searches?.filter(s => {
          const keep = !matchesConcept(s);
          if (!keep && selectRowsSchema != null && selectRowsSchema.search_results != null) {
            const resultPaths = selectRowsSchema.search_results
              .filter(r => pathIsEqual(r.search_path, s.path))
              .map(r => r.result_path);
            resultPathsToRemove.push(...resultPaths);
          }
          return keep;
        });
        state.query.sort_by = state.query.sort_by?.filter(
          p => !resultPathsToRemove.some(r => pathIsEqual(r, p))
        );
        state.query.filters = state.query.filters?.filter(
          f => !resultPathsToRemove.some(r => pathIsEqual(r, f.path))
        );
        return state;
      });
    }
  };

  if (saveGlobally) {
    datasetViewStores[datasetKey(namespace, datasetName)] = store;
  }
  return store;
}

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
  const columns = ['*', ...(datasetViewStore.query.columns ?? [])];

  return {
    ...datasetViewStore.query,
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

/** Returns if two filters are equall. */
function filterEquals(f1: Filter, f2: Filter): boolean {
  return f1.op == f2.op && f1.value == f2.value && pathIsEqual(f1.path, f2.path);
}
