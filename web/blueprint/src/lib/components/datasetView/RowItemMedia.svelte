<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */
  import {notEmpty} from '$lib/utils';
  import {
    L,
    childFields,
    formatValue,
    getValueNodes,
    isConceptScoreSignal,
    pathIncludes,
    pathIsEqual,
    type ConceptLabelsSignal,
    type ConceptScoreSignal,
    type LilacField,
    type LilacValueNode,
    type Path,
    type SemanticSimilaritySignal,
    type SubstringSignal
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';
  import type {SpanValueInfo} from './spanHighlight';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;

  $: visibleChildren = childFields(field);

  $: conceptSignals = visibleChildren.filter(f => isConceptScoreSignal(f.signal));
  $: conceptLabelSignals = visibleChildren.filter(f => f.signal?.signal_name === 'concept_labels');
  $: semanticSimilaritySignals = visibleChildren.filter(
    f => f.signal?.signal_name === 'semantic_similarity'
  );
  $: keywordSignals = visibleChildren.filter(f => f.signal?.signal_name === 'substring_search');

  // Find the non-keyword span fields under this field.
  $: visibleSpanFields = visibleChildren.filter(f => f.dtype === 'string_span');
  $: visibleSpanPaths = visibleSpanFields.map(f => f.path);

  let valuePaths: SpanValueInfo[] = [];
  $: {
    for (const visibleSpanField of visibleSpanFields) {
      const spanChildren = childFields(visibleSpanField)
        .filter(f => f.dtype != 'string_span')
        .filter(f => visibleFields?.some(visibleField => pathIsEqual(visibleField.path, f.path)));
      const spanPetalChildren = spanChildren.filter(f => f.dtype != null && f.dtype != 'embedding');
      const spanPath = visibleSpanField.path;

      const keywordSearch = keywordSignals.find(f => pathIncludes(visibleSpanField.path, f.path));

      // Keyword spans don't have values.
      if (keywordSearch != null) {
        const signal = keywordSearch.signal as SubstringSignal;

        valuePaths.push({
          path: visibleSpanField.path,
          spanPath,
          type: 'keyword',
          name: signal.query,
          dtype: visibleSpanField.dtype!,
          signal
        });
      }

      for (const spanPetalChild of spanPetalChildren) {
        const concept = conceptSignals.find(f => pathIncludes(spanPetalChild.path, f.path));
        const conceptLabel = conceptLabelSignals.find(f =>
          pathIncludes(spanPetalChild.path, f.path)
        );
        const semanticSimilarity = semanticSimilaritySignals.find(f =>
          pathIncludes(spanPetalChild.path, f.path)
        );
        if (concept != null) {
          const signal = concept.signal as ConceptScoreSignal;
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
  }

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  const visibleFields = $datasetStore.visibleFields || [];

  $: values = getValueNodes(row, path)
    .map(v => L.value(v))
    .filter(notEmpty);
</script>

{#each values as value, i}
  {@const suffix = values.length > 1 ? `[${i}]` : ''}
  <div class="flex flex-row">
    <div class="flex w-full flex-col">
      <div
        class="sticky top-0 z-10 w-full self-start border-t border-neutral-200 bg-neutral-100 px-2 py-2
               pb-2 font-mono font-medium text-neutral-500"
      >
        {path.join('.') + suffix}
      </div>

      <div class="font-normal">
        <StringSpanHighlight
          text={formatValue(value)}
          {row}
          spanPaths={visibleSpanPaths}
          {valuePaths}
          {datasetViewStore}
          datasetStore={$datasetStore}
        />
      </div>
    </div>
  </div>
{/each}
