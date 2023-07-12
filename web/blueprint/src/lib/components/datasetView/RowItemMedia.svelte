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
    getFieldsByDtype,
    getValueNodes,
    pathIncludes,
    pathIsEqual,
    petals,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight, {type SpanHighlightValuePaths} from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;

  $: visibleChildren = childFields(field);

  $: console.log('field=', field);

  // Find the non-keyword span fields under this field.
  $: visibleSpanFields = visibleChildren.filter(f => f.dtype === 'string_span');

  let valuePaths: SpanHighlightValuePaths[] = [];
  $: {
    for (const visibleSpanField of visibleSpanFields) {
      const children = petals(visibleSpanField)
        .filter(f => f.dtype != 'string_span')
        .filter(f => visibleFields?.some(visibleField => pathIsEqual(visibleField.path, f.path)));

      const conceptSignals = children.filter(f => f.signal?.signal_name === 'concept_score');
      const conceptLabelSignals = children.filter(f => f.signal?.signal_name === 'concept_labels');
      const semanticSimilaritySignals = children.filter(
        f => f.signal?.signal_name === 'semantic_similarity'
      );
      const keywordSignals = children.filter(f => f.signal?.signal_name === 'substring_search');
      for (const child of children) {
        let type: SpanHighlightValuePaths['type'];
        if (conceptSignals.some(f => pathIncludes(child.path, f.path))) {
          type = 'concept_score';
        } else {
          type = 'metadata';
        }
        valuePaths.push({
          path: child.path,
          type
        });
      }
    }
  }

  $: console.log(visibleSpanFields, valuePaths);

  // Find the keyword span paths under this field.
  $: visibleKeywordSpanFields = visibleChildren
    .filter(f => f.signal?.signal_name === 'substring_search')
    .flatMap(f => getFieldsByDtype('string_span', f));

  // Find the label fields.
  $: visibleLabelSpanFields = visibleChildren
    .filter(f => f.signal?.signal_name === 'concept_labels')
    .flatMap(f => getFieldsByDtype('string_span', f));

  const datasetViewStore = getDatasetViewContext();
  const datasetStore = getDatasetContext();
  const visibleFields = $datasetStore.visibleFields || [];

  $: values = getValueNodes(row, path)
    .map(v => L.value(v))
    .filter(notEmpty);

  $: console.log('path=', path, values);
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
          spanPaths={visibleSpanFields}
          {datasetViewStore}
          datasetStore={$datasetStore}
        />
      </div>
    </div>
  </div>
{/each}
