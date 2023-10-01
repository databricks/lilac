import {
  L,
  PATH_WILDCARD,
  childFields,
  getField,
  isConceptSignal,
  pathIncludes,
  pathIsEqual,
  serializePath,
  type AuthenticationInfo,
  type ConceptInfo,
  type ConceptLabelsSignal,
  type ConceptSignal,
  type DataType,
  type DataTypeCasted,
  type DatasetInfo,
  type DatasetSettings,
  type LilacField,
  type LilacSchema,
  type LilacSelectRowsSchema,
  type LilacValueNode,
  type LilacValueNodeCasted,
  type Path,
  type Search,
  type SelectRowsOptions,
  type SemanticSimilaritySignal,
  type SortResult,
  type SubstringSignal
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
import type {NavigationGroupItem, NavigationTagGroup} from './components/NavigationGroup.svelte';
import type {SpanValueInfo} from './components/datasetView/spanHighlight';
import type {DatasetState} from './stores/datasetStore';
import type {DatasetViewState} from './stores/datasetViewStore';
import type {SettingsState} from './stores/settingsStore';
import {conceptLink, datasetLink} from './utils';
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

export function getHighlightedFields(
  selectRowsOptions: SelectRowsOptions,
  selectRowsSchema: LilacSelectRowsSchema | undefined
): LilacField[] {
  if (selectRowsSchema == null) {
    return [];
  }
  return childFields(selectRowsSchema.schema).filter(f =>
    isPathHighlighted(selectRowsSchema, selectRowsOptions, f.path)
  );
}

export function getMediaFields(
  schema: LilacSchema | undefined,
  settings: DatasetSettings | null
): LilacField[] {
  if (schema == null) return [];
  if (settings == null) return [];

  return (settings?.ui?.media_paths || []).map(path => getField(schema!, path)!);
}

function isPathHighlighted(
  selectRowsSchema: LilacSelectRowsSchema,
  selectRowsOptions: SelectRowsOptions,
  path: Path
): boolean {
  const pathIsFiltered = selectRowsOptions.filters?.some(f => pathIsEqual(f.path, path));
  const pathIsSortedBy = selectRowsSchema?.sorts?.some(s => pathIsEqual(s.path, path));
  if (pathIsFiltered || pathIsSortedBy) {
    return true;
  }
  if (isPreviewSignal(selectRowsSchema, path)) {
    return true;
  }
  return false;
}

export function getSearchEmbedding(
  datasetSettings: DatasetSettings | undefined,
  appSettings: SettingsState,
  datasetStore: DatasetState,
  searchPath: Path | undefined,
  embeddings: string[]
): string | null {
  if (datasetSettings != null && datasetSettings.preferred_embedding != null) {
    return datasetSettings.preferred_embedding;
  }
  if (appSettings.embedding != null) {
    return appSettings.embedding;
  }
  if (searchPath == null) return null;

  const existingEmbeddings = getComputedEmbeddings(datasetStore.schema, searchPath);
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
  schema: LilacSchema | undefined | null,
  path: Path | undefined
): string[] {
  if (schema == null || path == null) return [];

  const existingEmbeddings: Set<string> = new Set();
  const embeddingSignalRoots = childFields(getField(schema, path)).filter(
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

export function getDefaultSearchPath(
  datasetStore: DatasetState,
  mediaPaths: Path[]
): Path | undefined {
  if (datasetStore.stats == null || datasetStore.stats.length === 0) {
    return undefined;
  }
  // The longest visible path that has an embedding is auto-selected.
  const mediaPathsStats = datasetStore.stats.filter(s =>
    mediaPaths.some(p => pathIsEqual(s.path, p))
  );
  if (mediaPathsStats.length === 0) {
    return undefined;
  }
  let paths = mediaPathsStats.map(stat => {
    return {
      path: stat.path,
      embeddings: getComputedEmbeddings(datasetStore.schema, stat.path),
      avgTextLength: stat.avg_text_length
    };
  });
  paths = paths.sort((a, b) => {
    if (a.embeddings.length > 0 && b.embeddings.length === 0) {
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

export function getTaggedDatasets(
  selectedDataset: {namespace: string; datasetName: string} | null,
  datasets: DatasetInfo[]
): NavigationTagGroup<DatasetInfo>[] {
  const tagDatasets: Record<string, Record<string, DatasetInfo[]>> = {};
  for (const dataset of datasets) {
    let tags = [''];
    if (dataset.tags != null && dataset.tags.length > 0) {
      tags = dataset.tags;
    }
    for (const tag of tags) {
      if (tagDatasets[tag] == null) {
        tagDatasets[tag] = {};
      }
      if (tagDatasets[tag][dataset.namespace] == null) {
        tagDatasets[tag][dataset.namespace] = [];
      }
      tagDatasets[tag][dataset.namespace].push(dataset);
    }
  }
  const tagSortPriorities = ['machine-learning'];
  const sortedTags = Object.keys(tagDatasets).sort(
    (a, b) => tagSortPriorities.indexOf(b) - tagSortPriorities.indexOf(a) || a.localeCompare(b)
  );

  const namespaceSortPriorities = ['lilac'];
  // TODO(nsthorat): Don't hard-code this. Let's make this a config.
  const pinnedDatasets = ['OpenOrca-100k'];

  // Sort each tag by namespace and then dataset name.
  const taggedDatasetGroups: NavigationTagGroup<DatasetInfo>[] = [];
  for (const tag of sortedTags) {
    const sortedNamespaceDatasets: NavigationGroupItem<DatasetInfo>[] = Object.keys(
      tagDatasets[tag]
    )
      .sort(
        (a, b) =>
          namespaceSortPriorities.indexOf(b) - namespaceSortPriorities.indexOf(a) ||
          a.localeCompare(b)
      )
      .map(namespace => ({
        group: namespace,
        items: tagDatasets[tag][namespace]
          .sort(
            (a, b) =>
              pinnedDatasets.indexOf(b.dataset_name) - pinnedDatasets.indexOf(a.dataset_name) ||
              a.dataset_name.localeCompare(b.dataset_name)
          )
          .map(d => ({
            name: d.dataset_name,
            link: datasetLink(d.namespace, d.dataset_name),
            isSelected:
              selectedDataset?.namespace === d.namespace &&
              selectedDataset?.datasetName === d.dataset_name,
            item: d
          }))
      }));
    taggedDatasetGroups.push({tag, groups: sortedNamespaceDatasets});
  }
  return taggedDatasetGroups;
}

export function getTaggedConcepts(
  selectedConcept: {namespace: string; name: string} | null,
  concepts: ConceptInfo[],
  userId: string | undefined,
  username: string | undefined
): NavigationTagGroup<ConceptInfo>[] {
  const tagConcepts: Record<string, Record<string, ConceptInfo[]>> = {};
  for (const concept of concepts) {
    let tags = [''];
    if (concept.metadata.tags != null && concept.metadata.tags.length > 0) {
      tags = concept.metadata.tags;
    }
    for (const tag of tags) {
      if (tagConcepts[tag] == null) {
        tagConcepts[tag] = {};
      }
      if (tagConcepts[tag][concept.namespace] == null) {
        tagConcepts[tag][concept.namespace] = [];
      }
      tagConcepts[tag][concept.namespace].push(concept);
    }
  }

  const namespaceSortPriorities = ['lilac'];

  // Sort each tag by namespace and then dataset name.
  const taggedDatasetGroups: NavigationTagGroup<ConceptInfo>[] = [];
  for (const tag of Object.keys(tagConcepts).sort()) {
    const sortedNamespaceDatasets: NavigationGroupItem<ConceptInfo>[] = Object.keys(
      tagConcepts[tag]
    )
      .sort(
        (a, b) =>
          namespaceSortPriorities.indexOf(a) - namespaceSortPriorities.indexOf(b) ||
          a.localeCompare(b)
      )
      .map(namespace => ({
        group: namespace === userId ? `${username}'s concepts` : namespace,
        items: tagConcepts[tag][namespace]
          .sort((a, b) => a.name.localeCompare(b.name))
          .map(c => ({
            name: c.name,
            link: conceptLink(c.namespace, c.name),
            isSelected:
              selectedConcept?.namespace === c.namespace && selectedConcept?.name === c.name,
            item: c
          }))
      }));
    taggedDatasetGroups.push({tag, groups: sortedNamespaceDatasets});
  }
  return taggedDatasetGroups;
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

export function getSpanValuePaths(
  field: LilacField,
  highlightedFields?: LilacField[]
): {spanPaths: Path[]; valuePaths: SpanValueInfo[]} {
  // Include the field.
  const children = childFields(field);
  // Find the non-keyword span fields under this field.
  const conceptSignals = children.filter(f => isConceptSignal(f.signal));
  const conceptLabelSignals = children.filter(f => f.signal?.signal_name === 'concept_labels');
  const semanticSimilaritySignals = children.filter(
    f => f.signal?.signal_name === 'semantic_similarity'
  );
  const keywordSignals = children.filter(f => f.signal?.signal_name === 'substring_search');
  // Find the non-keyword span fields under this field.
  let spanFields = children
    .filter(f => f.dtype === 'string_span')
    // Ignore embedding spans.
    .filter(f => !childFields(f).some(c => c.dtype === 'embedding'));
  if (highlightedFields != null) {
    // Keep only spans that have visible children.
    spanFields = spanFields.filter(f =>
      childFields(f).some(c => highlightedFields.some(v => pathIncludes(c.path, v.path)))
    );
  }

  const spanPaths = spanFields.map(f => f.path);

  const valuePaths: SpanValueInfo[] = [];
  for (const spanField of spanFields) {
    const spanChildren = childFields(spanField)
      .filter(f => f.dtype != 'string_span')
      .filter(
        f => highlightedFields == null || highlightedFields.some(v => pathIsEqual(v.path, f.path))
      );
    const spanPetalChildren = spanChildren.filter(f => f.dtype != null && f.dtype != 'embedding');
    const spanPath = spanField.path;

    const keywordSearch = keywordSignals.find(f => pathIncludes(spanField.path, f.path));

    // Keyword spans don't have values.
    if (keywordSearch != null) {
      const signal = keywordSearch.signal as SubstringSignal;

      valuePaths.push({
        path: spanField.path,
        spanPath,
        type: 'keyword',
        name: signal.query,
        dtype: spanField.dtype!,
        signal
      });
    } else if (spanPetalChildren.length === 0) {
      // If the span is a leaf, we still show it highlighted.
      valuePaths.push({
        path: spanField.path,
        spanPath,
        type: 'leaf_span',
        // Remove the '*'.
        name: serializePath(spanField.path.slice(0, -1)),
        dtype: spanField.dtype!
      });
    }

    for (const spanPetalChild of spanPetalChildren) {
      const concept = conceptSignals.find(f => pathIncludes(spanPetalChild.path, f.path));
      const conceptLabel = conceptLabelSignals.find(f => pathIncludes(spanPetalChild.path, f.path));
      const semanticSimilarity = semanticSimilaritySignals.find(f =>
        pathIncludes(spanPetalChild.path, f.path)
      );
      if (concept != null) {
        const signal = concept.signal as ConceptSignal;
        valuePaths.push({
          path: spanPetalChild.path,
          spanPath,
          type: 'concept_score',
          name: `${signal.namespace}/${signal.concept_name}`,
          dtype: spanPetalChild.dtype!,
          signal
        });
      } else if (conceptLabel != null) {
        const signal = conceptLabel.signal as ConceptLabelsSignal;
        valuePaths.push({
          path: spanPetalChild.path,
          spanPath,
          type: 'label',
          name: `${signal.namespace}/${signal.concept_name} label`,
          dtype: spanPetalChild.dtype!,
          signal
        });
      } else if (semanticSimilarity != null) {
        const signal = semanticSimilarity.signal as SemanticSimilaritySignal;
        valuePaths.push({
          path: spanPetalChild.path,
          spanPath,
          type: 'semantic_similarity',
          name: `similarity: ${signal.query}`,
          dtype: spanPetalChild.dtype!,
          signal
        });
      } else {
        valuePaths.push({
          path: spanPetalChild.path,
          spanPath,
          type: 'metadata',
          name: spanPetalChild.path[spanPetalChild.path.length - 1],
          dtype: spanPetalChild.dtype!
        });
      }
    }
  }
  return {spanPaths, valuePaths};
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
  // Remove empty span arrays as they don't contribute to the final spans.
  inputSpanSets = Object.fromEntries(Object.entries(inputSpanSets).filter(([, v]) => v.length > 0));

  const spanSetKeys = Object.keys(inputSpanSets);
  if (spanSetKeys.length === 0) {
    return [
      {
        text,
        span: {start: 0, end: stringLength(text)},
        originalSpans: {},
        paths: []
      }
    ];
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
      const aStart = L.span(a)?.start || 0;
      const bStart = L.span(b)?.start || 0;
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
        const spanValue = L.span(span);
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
          if (span == null) return false;
          const spanValue = L.span(span);
          if (spanValue == null) return false;
          return spanValue.start < curEndIndex && spanValue.end > curStartIdx;
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
      const span = L.span(spanSetWorkingSpans[spanSet][0]);
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

/** Returns a short-form field name for displaying. */
export function shortFieldName(path: Path): string {
  if (path.length === 0) {
    throw new Error('Cannot get short name for empty path');
  }
  return [...path].reverse().find(p => p !== PATH_WILDCARD)!;
}

export function displayPath(path: Path | string): string {
  if (!Array.isArray(path)) {
    path = [path];
  }
  const result = path.join(' › ');
  return result.replaceAll(` › ${PATH_WILDCARD}`, '[]');
}
