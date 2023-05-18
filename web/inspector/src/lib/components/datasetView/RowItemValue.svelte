<script lang="ts">
  import {isPathVisible} from '$lib/stores/datasetViewStore';
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
    listFields,
    type LilacSchema,
    type LilacSchemaField,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let path: Path;
  export let row: LilacValueNode;
  export let visibleColumns: Path[];
  export let schema: LilacSchema;
  export let aliasMapping: Record<string, Path> | undefined;

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

  // If type is a string, figure out if there are any children that are string_span
  // Only do this if the column is visible, and it isn't a repeated field
  $: stringSpanFields =
    showValue && field && dtype === 'string' && valueNodes.length === 1
      ? getDerivedStringSpanFields(field)
      : [];

  /**
   * Get child fields that are of string_span type
   */
  function getDerivedStringSpanFields(field: LilacSchemaField): LilacSchemaField[] {
    if (!field) return [];
    return (
      listFields(field)
        // Filter for string spans
        .filter(field => field.dtype === 'string_span')
        // Filter for visible columns
        .filter(field => isPathVisible(visibleColumns, field.path, aliasMapping))
    );
  }
</script>

{#if showValue}
  <div class="flex flex-col">
    <div class="font-mono text-sm text-gray-600">
      {path.join('.')}
    </div>

    <div>
      {#if !stringSpanFields.length}
        {values.map(formatValue).join(', ')}
      {:else}
        <StringSpanHighlight
          text={formatValue(values[0])}
          {stringSpanFields}
          {row}
          {visibleColumns}
          {aliasMapping}
        />
      {/if}
    </div>
  </div>
{/if}
