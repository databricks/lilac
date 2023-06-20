<script lang="ts">
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */

  import {
    childFields,
    formatValue,
    getFieldsByDtype,
    getValueNodes,
    L,
    type LilacField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let field: LilacField;

  $: visibleChildren = childFields(field);

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

  $: items = getValueNodes(row, path);
</script>

{#each items as item, i}
  {@const value = L.value(item)}
  {#if value != null}
    {@const suffix = items.length > 1 ? `[${i}]` : ''}
    <div class="flex flex-row">
      <div class="flex flex-col border-gray-900">
        <div class="pb-2 font-mono font-medium text-neutral-500">
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
    </div>
  {/if}
{/each}
