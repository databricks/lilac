import {
  L,
  VALUE_KEY,
  childFields,
  deserializePath,
  getField,
  getFieldsByDtype,
  pathIncludes,
  pathIsEqual,
  serializePath,
  type AuthenticationInfo,
  type ConceptInfo,
  type DataType,
  type DataTypeCasted,
  type DatasetSettings,
  type LilacField,
  type LilacSchema,
  type LilacSelectRowsSchema,
  type LilacValueNode,
  type LilacValueNodeCasted,
  type Path,
  type Search,
  type SortResult
} from '$lilac';
import {
  AssemblyCluster,
  Boolean,
  CharacterDecimal,
  CharacterWholeNumber,
  DataBlob,
  NotAvailable,
  StringText,
  Time,
  type CarbonIcon
} from 'carbon-icons-svelte';
import type {DatasetState} from './stores/datasetStore';
import type {DatasetViewState} from './stores/datasetViewStore';
import type {SettingsState} from './stores/settingsStore';
export const ITEM_SCROLL_CONTAINER_CTX_KEY = 'itemScrollContainer';

export const DTYPE_TO_ICON: Record<DataType, typeof CarbonIcon> = {
  string: StringText,
  string_span: StringText,
  uint8: CharacterWholeNumber,
  uint16: CharacterWholeNumber,
  uint32: CharacterWholeNumber,
  uint64: CharacterWholeNumber,
  int8: CharacterWholeNumber,
  int16: CharacterWholeNumber,
  int32: CharacterWholeNumber,
  int64: CharacterWholeNumber,
  boolean: Boolean,
  float16: CharacterDecimal,
  float32: CharacterDecimal,
  float64: CharacterDecimal,
  time: Time,
  date: Time,
  timestamp: Time,
  interval: Time,
  embedding: AssemblyCluster,
  binary: DataBlob,
  null: NotAvailable
};

export function getVisibleFields(
  selectedColumns: {[path: string]: boolean} | null,
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
  return fields.filter(f => isPathVisible(selectedColumns, f.path));
}

export function isFieldVisible(field: LilacField, visibleFields: LilacField[]): boolean {
  return visibleFields.some(f => pathIsEqual(f.path, field.path));
}

export function isItemVisible(item: LilacValueNode, visibleFields: LilacField[]): boolean {
  const field = L.field(item);
  if (field == null) return false;
  return isFieldVisible(field, visibleFields);
}

export function getVisibleSchema(
  schema: LilacField,
  visibleFields: LilacField[]
): LilacField | null {
  const fields: {[fieldName: string]: LilacField} = {};
  let repeatedField: LilacField | undefined = undefined;

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
      repeatedField = undefined;
    } else {
      repeatedField = schema.repeated_field;
    }
  }
  if (repeatedField == null && Object.keys(fields).length === 0)
    return {...schema, fields: undefined, repeated_field: undefined};
  const isVisible =
    schema.path.length === 0 || visibleFields.some(f => pathIsEqual(f.path, schema.path));
  if (!isVisible) return null;
  return {...schema, fields, repeated_field: repeatedField};
}

export function getMediaFields(
  schema: LilacField | null,
  settings: DatasetSettings | null
): LilacField[] {
  if (schema == null) return [];
  if (settings == null) return [];

  return (settings?.ui?.media_paths || []).map(path => getField(schema!, path)!);
}

export function isPathVisible(
  selectedColumns: {[path: string]: boolean} | null,
  path: Path | string
): boolean {
  if (selectedColumns == null) return false;
  if (typeof path !== 'string') path = serializePath(path);

  // If a user has explicitly selected a column, return the value of the selection.
  if (selectedColumns[path] != null) return selectedColumns[path];

  const pathArray = deserializePath(path);

  if (pathArray.length > 1) {
    // When no explicit selection, children inherit from their parent.
    return isPathVisible(selectedColumns, serializePath(pathArray.slice(0, pathArray.length - 1)));
  }

  // Columns are visible by default.
  return true;
}

export function getSearchPath(store: DatasetViewState, datasetStore: DatasetState): Path | null {
  // If the user explicitly chose a search path, use it.
  if (store.searchPath != null && store.selectedColumns[store.searchPath] != false)
    return deserializePath(store.searchPath);

  // Without explicit selection, choose the default string path.
  return getDefaultSearchPath(datasetStore);
}

export function getSearchEmbedding(
  appSettings: SettingsState,
  datasetSettings: DatasetSettings | undefined,
  store: DatasetViewState,
  datasetStore: DatasetState,
  searchPath: Path | null,
  embeddings: string[]
): string | null {
  if (store.searchEmbedding != null) {
    return store.searchEmbedding;
  }
  if (datasetSettings != null && datasetSettings.preferred_embedding != null) {
    return datasetSettings.preferred_embedding;
  }
  if (appSettings.embedding != null) {
    return appSettings.embedding;
  }
  if (searchPath == null) return null;

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
export function getComputedEmbeddings(datasetStore: DatasetState, path: Path | null): string[] {
  if (datasetStore.schema == null || path == null) return [];

  const existingEmbeddings: Set<string> = new Set();
  const embeddingSignalRoots = childFields(getField(datasetStore.schema, path)).filter(
    f => f.signal != null && childFields(f).some(f => f.dtype === 'embedding')
  );
  for (const field of embeddingSignalRoots) {
    if (field.signal != null) {
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
  return (selectRowsSchema.udfs || []).some(udf => pathIncludes(path, udf.path));
}

/** Gets the search type for a column, if defined. The path is the *input* path to the search. */
export function getSearches(store: DatasetViewState, path?: Path | null): Search[] {
  if (path == null) return store.query.searches || [];
  return (store.query.searches || []).filter(s => pathIsEqual(s.path, path));
}

function getDefaultSearchPath(datasetStore: DatasetState): Path | null {
  if (datasetStore.stats == null || datasetStore.stats.length === 0) {
    return null;
  }
  const visibleStringPaths = (datasetStore.visibleFields || [])
    .filter(f => f.dtype === 'string')
    .map(f => serializePath(f.path));
  // The longest visible path that has an embedding is auto-selected.
  let paths = datasetStore.stats.map(stat => {
    return {
      path: stat.path,
      embeddings: getComputedEmbeddings(datasetStore, stat.path),
      avgTextLength: stat.avg_text_length,
      isVisible: visibleStringPaths.indexOf(serializePath(stat.path)) >= 0
    };
  });
  paths = paths.sort((a, b) => {
    if (!a.isVisible && b.isVisible) {
      return 1;
    } else if (a.isVisible && !b.isVisible) {
      return -1;
    } else if (a.embeddings.length > 0 && b.embeddings.length === 0) {
      return -1;
    } else if (a.embeddings.length === 0 && b.embeddings.length > 0) {
      return 1;
    } else if (a.avgTextLength != null && b.avgTextLength != null) {
      return b.avgTextLength - a.avgTextLength;
    } else {
      return b.embeddings.length - a.embeddings.length;
    }
  });
  return paths[0].path;
}

export function getSortedConcepts(
  concepts: ConceptInfo[],
  userId?: string | null
): {namespace: string; concepts: ConceptInfo[]}[] {
  const namespaceConcepts: Record<string, ConceptInfo[]> = {};
  for (const c of concepts) {
    if (namespaceConcepts[c.namespace] == null) {
      namespaceConcepts[c.namespace] = [];
    }
    namespaceConcepts[c.namespace].push(c);
  }
  const sortPriorities = [userId, 'lilac'];
  return Object.keys(namespaceConcepts)
    .sort((a, b) => sortPriorities.indexOf(a) - sortPriorities.indexOf(b) || a.localeCompare(b))
    .map(namespace => ({
      namespace,
      concepts: namespaceConcepts[namespace].sort((a, b) => a.name.localeCompare(b.name))
    }));
}

export function conceptDisplayName(
  conceptNamespace: string,
  conceptName: string,
  authInfo?: AuthenticationInfo
): string {
  if (authInfo?.auth_enabled && authInfo.user?.id === conceptNamespace) {
    return conceptName;
  }
  return `${conceptNamespace}/${conceptName}`;
}

export function getSort(datasetStore: DatasetState): SortResult | null {
  // NOTE: We currently only support sorting by a single column from the UI.
  return (datasetStore.selectRowsSchema?.data?.sorts || [])[0] || null;
}

export interface MergedSpan {
  text: string;
  span: DataTypeCasted<'string_span'>;
  originalSpans: {[spanSet: string]: LilacValueNodeCasted<'string_span'>[]};
  // The paths associated with this merged span.
  paths: string[];
}

// Split a merged span up into smaller chunks to help with snippeting.
function chunkText(text: string): MergedSpan[] {
  const splitBy = '\n';
  const splits = text.split(splitBy);
  const splitSpans: MergedSpan[] = [];
  let lastEnd = 0;
  for (let i = 0; i < splits.length; i++) {
    const text = splits[i] + (i < splits.length - 1 ? splitBy : '');
    const end = lastEnd + stringLength(text);
    const span = {start: lastEnd, end};
    splitSpans.push({
      text,
      span,
      originalSpans: {},
      paths: []
    });
    lastEnd = end;
  }
  return splitSpans;
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
  // Remove empty span arrays as they don't contribute to the final spans.
  inputSpanSets = Object.fromEntries(Object.entries(inputSpanSets).filter(([, v]) => v.length > 0));

  const spanSetKeys = Object.keys(inputSpanSets);
  if (spanSetKeys.length === 0) {
    return chunkText(text);
  }
  const textChars = getChars(text);
  const textLength = textChars.length;

  // Maps a span set to the index of the spans we're currently processing for each span set.
  // The size of this object is the size of the number of span sets we're computing over (small).
  const spanSetIndices: {[spanSet: string]: number} = Object.fromEntries(
    Object.keys(inputSpanSets).map(spanSet => [spanSet, 0])
  );

  // Sort spans by start index.
  for (const spanSet of spanSetKeys) {
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

  while (curStartIdx < textLength) {
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
      text: textChars.slice(curStartIdx, curEndIndex).join(''),
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
  if (curStartIdx < textLength) {
    mergedSpans.push({
      text: textChars.slice(curStartIdx).join(''),
      span: {start: curStartIdx, end: textLength},
      originalSpans: {},
      paths: []
    });
  }

  return mergedSpans;
}

/** Slices the text by graphemes (like python) instead of by UTF-16 characters. */
export function stringSlice(text: string, start: number, end?: number): string {
  return getChars(text).slice(start, end).join('');
}

export function getChars(text: string): string[] {
  return [...text];
}

/** Counts each grapheme as 1 character (like python) instead of counting UTF-16 characters. */
export function stringLength(text: string): number {
  return getChars(text).length;
}
