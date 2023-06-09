<script lang="ts">
  /**
   * Component that renders a single value from a row in the dataset row view
   * In the case of strings with string_spans, it will render the derived string spans as well
   */

  import {notEmpty} from '$lib/utils';
  import {
    L,
    formatValue,
    getValueNodes,
    isOrdinal,
    listFieldParents,
    type LilacSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let schema: LilacSchema;

  $: valueNodes = getValueNodes(row, path);
  $: field = L.field(valueNodes[0]);

  $: parents = field ? listFieldParents(field, schema) : undefined;
  $: dtype = valueNodes.length && L.dtype(valueNodes[0]);
  $: showValue =
    valueNodes.length && // Hide if there are no values
    dtype && // Hide if dtype is not set
    (isOrdinal(dtype) || dtype == 'string') && // Hide if dtype is not ordinal or string
    !parents?.some(parent => parent.dtype === 'string_span'); // Hide if any parent is a string span

  $: values = valueNodes.map(v => L.value(v)).filter(notEmpty);
</script>

{#if showValue && field}
  <div class="flex flex-col">
    <div class="font-mono text-sm text-gray-600">
      {path.join('.')}
    </div>

    <div>
      <StringSpanHighlight text={formatValue(values[0])} {row} {field} />
    </div>
  </div>
{/if}
