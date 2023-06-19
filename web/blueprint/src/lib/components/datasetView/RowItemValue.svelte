<script lang="ts">
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
    pathIsEqual,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;
  export let visibleFields: LilacField[];

  $: visibleChildren = childFields(field).filter(child =>
    visibleFields.find(visible => pathIsEqual(visible.path, child.path))
  );

  // Find the keyword span paths under this field.
  $: visibleKeywordSpanFields = visibleChildren
    .filter(f => f.signal?.signal_name === 'substring_search')
    .flatMap(f => getFieldsByDtype('string_span', f));

  // Find the non-keyword span fields under this field.
  $: visibleSpanFields = visibleChildren
    .filter(f => f.signal?.signal_name !== 'substring_search')
    .filter(f => f.dtype === 'string_span');

  // Find the label fields.
  $: visibleLabelSpanFields = visibleChildren
    .filter(f => f.signal?.signal_name === 'concept_labels')
    .flatMap(f => getFieldsByDtype('string_span', f));

  $: values = getValueNodes(row, path)
    .map(v => L.value(v))
    .filter(notEmpty);
</script>

{#each values as value, i}
  {@const suffix = values.length > 1 ? `[${i}]` : ''}
  <div class="flex flex-col">
    <div class="pb-1 font-mono font-medium text-neutral-900">
      {path.join('.') + suffix}
    </div>

    <div class="font-normal">
      <StringSpanHighlight
        text={formatValue(value)}
        {field}
        {row}
        {visibleKeywordSpanFields}
        {visibleSpanFields}
        {visibleLabelSpanFields}
      />
    </div>
  </div>
{/each}
