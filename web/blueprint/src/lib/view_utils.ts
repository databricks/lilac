import {
  L,
  VALUE_KEY,
  childFields,
  deserializePath,
  getField,
  getFieldsByDtype,
  pathIsEqual,
  petals,
  serializePath,
  type DataType,
  type DataTypeCasted,
  type LilacField,
  type LilacSchema,
  type LilacSelectRowsSchema,
  type LilacValueNode,
  type LilacValueNodeCasted,
  type Path,
  type Search,
  type SortResult
} from '$lilac';
import type {DatasetStore, StatsInfo} from './stores/datasetStore';
import type {IDatasetViewStore} from './stores/datasetViewStore';

const MEDIA_TEXT_LENGTH_THRESHOLD = 100;

export function getVisibleFields(
  selectedColumns: {[path: string]: boolean} | null,
  stats: StatsInfo[] | null,
  schema: LilacSchema | null,
  field?: LilacField | null,
  dtype?: DataType
): LilacField[] {
  if (schema == null) {
    return [];
  }

  let fields: LilacField[] = [];
  if (dtype == null) {
    fields = childFields(field || schema);
  } else {
    fields = getFieldsByDtype(dtype, field || schema);
  }
  return fields.filter(f => isPathVisible(selectedColumns, stats, f.path));
}

export function getVisibleSchema(
  schema: LilacField,
  visibleFields: LilacField[]
): LilacField | null {
  const fields: {[fieldName: string]: LilacField} = {};
  let repeated_field: LilacField | undefined = undefined;

  if (schema.fields != null) {
    for (const [fieldName, field] of Object.entries(schema.fields)) {
      if (visibleFields.some(f => pathIsEqual(f.path, field.path))) {
        const child = getVisibleSchema(field, visibleFields);
        if (child != null) {
          fields[fieldName] = child;
        }
      }
    }
  } else if (schema.repeated_field != null) {
    if (!visibleFields.some(f => pathIsEqual(f.path, schema.repeated_field?.path))) {
      repeated_field = undefined;
    } else {
      repeated_field = schema.repeated_field;
    }
  }
  if (repeated_field == null && Object.keys(fields).length === 0)
    return {...schema, fields: undefined, repeated_field: undefined};
  const isVisible =
    schema.path.length === 0 || visibleFields.some(f => pathIsEqual(f.path, schema.path));
  if (!isVisible) return null;
  return {...schema, fields, repeated_field};
}

export function getMediaFields(schema: LilacField, stats: StatsInfo[]): LilacField[] {
  const fields: LilacField[] = [];
  for (const petal of petals(schema)) {
    const stat = stats?.find(s => pathIsEqual(s.path, petal.path));
    const textLength = stat?.stats?.data?.avg_text_length;
    if (textLength != null && textLength > MEDIA_TEXT_LENGTH_THRESHOLD) {
      fields.push(petal);
    }
  }
  return fields;
}

export function isPathVisible(
  selectedColumns: {[path: string]: boolean} | null,
  stats: StatsInfo[] | null,
  path: Path | string
): boolean {
  if (selectedColumns == null) return false;
  if (typeof path !== 'string') path = serializePath(path);

  // If a user has explicitly selected a column, return the value of the selection.
  if (selectedColumns[path] != null) return selectedColumns[path];

  const pathArray = deserializePath(path);

  // If the path is the default, select it.
  const defaultPath = stats != null && stats.length > 0 ? stats[0].path : null;

  if (defaultPath != null && pathIsEqual(pathArray, defaultPath)) return true;

  if (pathArray.length > 1) {
    // When no explicit selection, children inherit from their parent.
    return isPathVisible(
      selectedColumns,
      stats,
      serializePath(pathArray.slice(0, pathArray.length - 1))
    );
  }

  return false;
}

export function getSearchPath(store: IDatasetViewStore, datasetStore: DatasetStore): Path | null {
  // If the user explicitly chose a search path, use it.
  if (store.searchPath != null && store.selectedColumns[store.searchPath] != false)
    return deserializePath(store.searchPath);

  // Without explicit selection, choose the default string path.
  return getDefaultSearchPath(datasetStore);
}

export function getSearchEmbedding(
  store: IDatasetViewStore,
  datasetStore: DatasetStore,
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
export function getComputedEmbeddings(datasetStore: DatasetStore, path: Path | null): string[] {
  if (datasetStore.schema == null || path == null) return [];

  const existingEmbeddings: Set<string> = new Set();
  const embeddingSignalRoots = childFields(getField(datasetStore.schema, path)).filter(
    f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
  );
  for (const field of embeddingSignalRoots) {
    if (field.signal?.signal_name != null) {
      existingEmbeddings.add(field.signal.signal_name);
    }
  }
  return Array.from(existingEmbeddings);
}

export function isPreviewSignal(
  selectRowsSchema: LilacSelectRowsSchema | null,
  path: Path | undefined
): boolean {
  if (path == null || selectRowsSchema == null) return false;
  return (selectRowsSchema.udfs || []).some(udf => pathIsEqual(udf.path, path));
}

/** Gets the search type for a column, if defined. The path is the *input* path to the search. */
export function getSearches(store: IDatasetViewStore, path?: Path | null): Search[] {
  if (path == null) return store.queryOptions.searches || [];
  return (store.queryOptions.searches || []).filter(s => pathIsEqual(s.path, path));
}

function getDefaultSearchPath(datasetStore: DatasetStore): Path | null {
  if (datasetStore.stats == null || datasetStore.stats.length === 0) {
    return null;
  }
  const visibleStringPaths = (datasetStore.visibleFields || [])
    .filter(f => f.dtype === 'string')
    .map(f => serializePath(f.path));
  // The longest visible path is auto-selected.
  for (const stat of datasetStore.stats) {
    const stringPath = serializePath(stat.path);
    if (visibleStringPaths.indexOf(stringPath) >= 0) {
      return stat.path;
    }
  }
  return null;
}

export function getSort(datasetStore: DatasetStore): SortResult | null {
  // NOTE: We currently only support sorting by a single column from the UI.
  return (datasetStore.selectRowsSchema?.data?.sorts || [])[0] || null;
}

export interface SpanHoverNamedValue {
  name: string;
  value: DataTypeCasted;
}

export interface MergedSpan {
  text: string;
  span: DataTypeCasted<'string_span'>;
  originalSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]};
  // The paths associated with this merged span.
  paths: string[];
}

/**
 * Merge a set of spans on a single item into a single list of spans, each with points back to
 * the original spans.
 *
 * For example:
 *   {
 *     spans1: [(0, 2), (3, 4)]
 *     spans2: [(0, 1), (2, 4)]
 *   }
 * Transforms into:
 *   [
 *     {span: (0, 1),  originalSpans: {spans1: [(0, 2)], spans2: [(0, 1)]}
 *     {span: (1, 2),  originalSpans: {spans1: [(0, 2)]}}
 *     {span: (2, 3),  originalSpans: {spans2: [(2, 4)]}}
 *     {span: (3, 4),  originalSpans: {spans1: [(3, 4)], spans2: [(2, 4)]}
 *  ]
 */
export function mergeSpans(
  text: string,
  inputSpanSets: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]}
): MergedSpan[] {
  const textLength = text.length;
  // Maps a span set to the index of the spans we're currently processing for each span set.
  // The size of this object is the size of the number of span sets we're computing over (small).
  const spanSetIndices: {[spanSet: string]: number} = Object.fromEntries(
    Object.keys(inputSpanSets).map(spanSet => [spanSet, 0])
  );

  // Sort spans by start index.
  for (const spanSet of Object.keys(inputSpanSets)) {
    inputSpanSets[spanSet].sort((a, b) => {
      const aStart = a[VALUE_KEY]?.start || 0;
      const bStart = b[VALUE_KEY]?.start || 0;
      return aStart - bStart;
    });
  }

  let curStartIdx = 0;
  const mergedSpans: MergedSpan[] = [];
  let spanSetWorkingSpans = Object.fromEntries(
    Object.entries(spanSetIndices).map(([spanSet, spanId]) => [
      spanSet,
      // Include the next span as it may contribute to the end offset of this merged span.
      [inputSpanSets[spanSet][spanId], inputSpanSets[spanSet][spanId + 1]]
    ])
  );

  while (curStartIdx < text.length) {
    // Compute the next end index.
    let curEndIndex = textLength;
    for (const spans of Object.values(spanSetWorkingSpans)) {
      for (const span of spans) {
        const spanValue = (span || {})[VALUE_KEY];
        if (spanValue == null) continue;
        if (spanValue.start < curEndIndex && spanValue.start > curStartIdx) {
          curEndIndex = spanValue.start;
        }
        if (spanValue.end < curEndIndex && spanValue.end > curStartIdx) {
          curEndIndex = spanValue.end;
        }
      }
    }

    // Filter the spans that meet the range.
    const spansInRange = Object.fromEntries(
      Object.entries(spanSetWorkingSpans).map(([spanSet, spans]) => [
        spanSet,
        spans.filter(span => {
          return (
            span != null &&
            span[VALUE_KEY] != null &&
            span[VALUE_KEY].start < curEndIndex &&
            span[VALUE_KEY].end > curStartIdx
          );
        })
      ])
    );
    // Sparsify the keys.
    for (const spanSet of Object.keys(spansInRange)) {
      if (spansInRange[spanSet].length === 0) {
        delete spansInRange[spanSet];
      }
    }

    const paths = Object.values(spansInRange)
      .flat()
      .map(span => L.path(span as LilacValueNode))
      .map(path => serializePath(path!));

    mergedSpans.push({
      text: text.slice(curStartIdx, curEndIndex),
      span: {start: curStartIdx, end: curEndIndex},
      originalSpans: spansInRange,
      paths
    });

    // Advance the spans that have the span end index.
    for (const spanSet of Object.keys(spanSetIndices)) {
      const spanSetIdx = spanSetIndices[spanSet];
      const span = (spanSetWorkingSpans[spanSet][0] || {})[VALUE_KEY];
      if (span == null || spanSetIdx == null) continue;
      if (span.end <= curEndIndex) {
        if (spanSetIdx > inputSpanSets[spanSet].length) {
          delete spanSetIndices[spanSet];
          continue;
        }
        spanSetIndices[spanSet]++;
      }
    }

    curStartIdx = curEndIndex;
    spanSetWorkingSpans = Object.fromEntries(
      Object.entries(spanSetIndices).map(([spanSet, spanId]) => [
        spanSet,
        // Include the next span as it may contribute to the end offset of this merged span.
        [inputSpanSets[spanSet][spanId], inputSpanSets[spanSet][spanId + 1]]
      ])
    );
  }

  // If the text has more characters than spans, emit a final empty span.
  if (curStartIdx < text.length) {
    mergedSpans.push({
      text: text.slice(curStartIdx, text.length),
      span: {start: curStartIdx, end: text.length},
      originalSpans: {},
      paths: []
    });
  }

  return mergedSpans;
}
