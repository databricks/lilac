import {
  childFields,
  deserializePath,
  getField,
  getFieldsByDtype,
  pathIsEqual,
  serializePath,
  type Column,
  type DataType,
  type LilacField,
  type Path,
  type Search
} from '$lilac';
import type {DatasetStore} from './stores/datasetStore';
import type {IDatasetViewStore} from './stores/datasetViewStore';

export function getVisibleFields(
  store: IDatasetViewStore,
  datasetStore: DatasetStore | null,
  field?: LilacField | null,
  dtype?: DataType
): LilacField[] {
  if (datasetStore?.schema == null) {
    return [];
  }

  let fields: LilacField[] = [];
  if (dtype == null) {
    fields = childFields(field || datasetStore.schema);
  } else {
    fields = getFieldsByDtype(dtype, field || datasetStore.schema);
  }
  return fields.filter(f => isPathVisible(store, datasetStore || null, f.path));
}

export function isPathVisible(
  store: IDatasetViewStore,
  datasetStore: DatasetStore | null,
  path: Path | string
): boolean {
  if (store.selectedColumns == null) return false;
  if (typeof path !== 'string') path = serializePath(path);

  // If a user has explicitly selected a column, return the value of the selection.
  if (store.selectedColumns[path] != null) return store.selectedColumns[path];

  const pathArray = deserializePath(path);

  // If the path is the default, select it.
  const defaultPath = getDefaultSelectedPath(datasetStore);

  if (defaultPath != null && pathIsEqual(pathArray, defaultPath)) return true;

  if (pathArray.length > 1) {
    // When no explicit selection, children inherit from their parent.
    return isPathVisible(
      store,
      datasetStore,
      serializePath(pathArray.slice(0, pathArray.length - 1))
    );
  }

  return false;
}

export function getSearchPath(
  store: IDatasetViewStore,
  datasetStore: DatasetStore | null
): Path | null {
  // If the user explicitly chose a search path, use it.
  if (store.searchPath != null && store.selectedColumns[store.searchPath])
    return deserializePath(store.searchPath);

  // Without explicit selection, choose the default string path.
  return getDefaultSelectedPath(datasetStore);
}

export function getSearchEmbedding(
  store: IDatasetViewStore,
  datasetStore: DatasetStore | null,
  searchPath: Path | null,
  embeddings: string[]
): string | null {
  if (searchPath == null) return null;
  if (store.searchEmbedding != null) return store.searchEmbedding;

  const existingEmbeddings = getComputedEmbeddings(datasetStore, searchPath);
  // Sort embeddings by what have already been precomputed first.
  const sortedEmbeddings =
    existingEmbeddings != null
      ? [...(embeddings || [])].sort((a, b) => {
          const hasA = existingEmbeddings.includes(a);
          const hasB = existingEmbeddings.includes(b);
          if (hasA && hasB) {
            return 0;
          } else if (hasA) {
            return -1;
          } else if (hasB) {
            return 1;
          }
          return 0;
        })
      : [];
  return sortedEmbeddings[0];
}

/** Get the computed embeddings for a path. */
export function getComputedEmbeddings(
  datasetStore: DatasetStore | null,
  path: Path | null
): string[] {
  if (datasetStore?.schema == null || path == null) return [];

  const existingEmbeddings: Set<string> = new Set();
  const embeddingSignalRoots = childFields(getField(datasetStore?.schema, path)).filter(
    f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
  );
  for (const field of embeddingSignalRoots) {
    if (field.signal?.signal_name != null) {
      existingEmbeddings.add(field.signal.signal_name);
    }
  }
  return Array.from(existingEmbeddings);
}

export function udfByAlias(
  store: IDatasetViewStore,
  alias: Path | undefined
): string | Column | string[] | undefined {
  return alias
    ? store.queryOptions.columns?.find(
        c => typeof c === 'object' && !Array.isArray(c) && c.alias === alias?.[0]
      )
    : undefined;
}

/** Gets the search type for a column, if defined. The path is the *input* path to the search. */
export function getSearches(store: IDatasetViewStore, path?: Path | null): Search[] {
  if (path == null) return store.queryOptions.searches || [];
  return (store.queryOptions.searches || []).filter(s => pathIsEqual(s.path, path));
}

export function getDefaultSelectedPath(datasetStore: DatasetStore | null): Path | null {
  // The longest path is auto-selected.
  if (datasetStore?.stats != null && datasetStore?.stats.length > 0) {
    return datasetStore?.stats[0].path;
  }
  return null;
}
