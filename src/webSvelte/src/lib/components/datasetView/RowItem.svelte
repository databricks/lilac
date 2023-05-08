<script lang="ts">
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import { L, getValueNode, type LilacSchemaField, type LilacValueNode } from '$lilac';
  import type { DataTypeCasted, Path } from '$lilac/schema';
  import StringSpanHighlight from './StringSpanHighlight.svelte';

  export let row: LilacValueNode;

  let datasetViewStore = getDatasetViewContext();

  /**
   * Get all columns that are derived from the given path.
   */
  function getDerivedFields(itemNode: LilacValueNode): LilacSchemaField[] {
    const field = L.field(itemNode);
    if (!field) return [];
    // TODO: Infer derived_from using a similar impl as db_dataset_duckdb.py::_derived_from_path.
    // return listFields(field).filter((f) => pathIsEqual(f.derived_from as Path, field.path));
    return [];
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
  {#each sortedVisibleColumns as column}
    {@const valueNode = getValueNode(row, column)}
    {#if valueNode}
      {@const value = L.value(valueNode)}
      {@const derivedFields = getDerivedFields(valueNode)}

      <div class="flex flex-col">
        <div class="font-mono text-sm text-gray-600">
          {column.join('.')}
        </div>

        <div class="relative">
          {formatValue(value ?? null)}
          {#if derivedFields}
            {#each derivedFields as derivedField}
              {@const derivedNode = getValueNode(row, derivedField.path)}
              {@const dtype = derivedNode && L.dtype(derivedNode)}
              {#if derivedNode && dtype === 'string_span'}
                {@const value = L.value(derivedNode, dtype)}
                {#if value}
                  <StringSpanHighlight text={formatValue(value ?? null)} stringSpans={value} />
                {/if}
              {/if}
            {/each}
          {/if}
        </div>
      </div>
    {/if}
  {/each}
</div>
