<script lang="ts">
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import { notEmpty } from '$lib/utils';
  import { L, getValueNode, getValueNodes, listFields, type LilacValueNode } from '$lilac';
  import type { DataTypeCasted, Path } from '$lilac/schema';
  import { isOrdinal, pathIsEqual } from '$lilac/schema';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let row: LilacValueNode;

  let datasetViewStore = getDatasetViewContext();

  /**
   * Get child fields that are of string_span type
   */
  function getDerivedStringSpans(itemNode: LilacValueNode): DataTypeCasted<'string_span'>[] {
    const field = L.field(itemNode);
    if (!field) return [];
    return (
      listFields(field)
        // Filter for string spans
        .filter((field) => field.dtype === 'string_span' && field.is_entity)
        // Filter for visible columns
        .filter((field) => $datasetViewStore.visibleColumns.some((c) => pathIsEqual(c, field.path)))
        .flatMap((f) => getValueNodes(row, f.path))
        .map((v) => L.value<'string_span'>(v))
        .filter(notEmpty)
    );
  }

  function showValue(value: LilacValueNode) {
    const dtype = L.dtype(value);
    if (!dtype) return false;
    if (isOrdinal(dtype) || dtype == 'string') {
      return true;
    }
  }

  function formatValue(value: DataTypeCasted) {
    if (value == null) {
      return 'N/A';
    }
    if (typeof value === 'number') {
      return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
    }
    return value.toString();
  }

  let sortedVisibleColumns: Path[] = [];
  $: {
    sortedVisibleColumns = [...$datasetViewStore.visibleColumns];
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-solid border-gray-300 pb-4">
  {#each sortedVisibleColumns as column (column)}
    {@const valueNode = getValueNode(row, column)}
    {#if valueNode && showValue(valueNode)}
      {@const value = L.value(valueNode)}
      {@const derivedStringSpans = getDerivedStringSpans(valueNode)}

      <div class="flex flex-col">
        <div class="font-mono text-sm text-gray-600">
          {column.join('.')}
        </div>

        <div class="relative">
          {formatValue(value ?? null)}
          {#if derivedStringSpans}
            <StringSpanHighlight
              text={formatValue(value ?? null)}
              stringSpans={derivedStringSpans}
            />
          {/if}
        </div>
      </div>
    {/if}
  {/each}
</div>
