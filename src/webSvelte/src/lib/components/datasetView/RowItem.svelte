<script lang="ts">
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import type { DataType, Field } from '$lilac/fastapi_client';
  import type { LilacSchema } from '$lilac/schema';
  import {
    LILAC_COLUMN,
    type FieldValue,
    type Item,
    type LeafValue,
    type Path
  } from '$lilac/schema';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let item: Item;
  export let schema: LilacSchema;

  let datasetViewStore = getDatasetViewContext();

  // console.log(schema);
  function getFieldValueForPath(path: Path, item: Item): LeafValue {
    let value: FieldValue = item;
    for (const key of path) {
      if (typeof value === 'object' && !Array.isArray(value) && value?.[key]) {
        value = value[key];
      }
    }
    return value as LeafValue;
  }

  function getFieldForPath(path: Path, schema: LilacSchema): Field | undefined {
    return schema.getLeaf(path);
  }

  /**
   * Get all columns that are derived from the given path.
   */
  function getDerivedColumns(path: Path, columns: Path[], schema: LilacSchema): Path[] {
    const derivedColumns: Path[] = [];
    for (const column of columns) {
      const field = getFieldForPath(column, schema);
      if (field?.derived_from?.join('.') === path.join('.')) {
        derivedColumns.push(column);
      }
    }
    return derivedColumns;
  }

  function formatValue(value: LeafValue, type?: DataType) {
    if (value == null) {
      return 'N/A';
    }
    if (typeof value === 'number') {
      return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
    }
    return value.toString();
  }

  function removeLilacPath(s: string): boolean {
    return s !== LILAC_COLUMN;
  }

  let sortedVisibleColumns: Path[] = [];
  $: {
    sortedVisibleColumns = [...$datasetViewStore.visibleColumns];
    sortedVisibleColumns.sort((a, b) =>
      a.filter(removeLilacPath).join('.') > b.filter(removeLilacPath).join('.') ? 1 : -1
    );
  }
</script>

<div class=" mb-4 flex flex-col gap-y-4 border-b border-solid border-gray-300 pb-4">
  {#each sortedVisibleColumns as column}
    {@const value = getFieldValueForPath(column, item)}
    {@const field = getFieldForPath(column, schema)}
    {@const derivedColumns = getDerivedColumns(column, sortedVisibleColumns, schema)}
    <div class="flex flex-col">
      <div class="font-mono text-sm text-gray-600">
        {column.filter(removeLilacPath).join('.')}
      </div>

      <div class="relative">
        {formatValue(value, field?.dtype)}
        {#if derivedColumns}
          {#each derivedColumns as derivedColumn}
            {@const derivedColumnValue = getFieldValueForPath(derivedColumn, item)}

            <StringSpanHighlight
              text={formatValue(value, field?.dtype)}
              stringSpans={derivedColumnValue}
            />
          {/each}
        {/if}
      </div>
    </div>
  {/each}
</div>
