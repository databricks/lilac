<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import type {LilacSchema, LilacValueNode, Path} from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;

  let datasetStore = getDatasetContext();

  let sortedVisibleColumns: Path[];

  $: {
    sortedVisibleColumns = ($datasetStore?.visibleFields || []).map(f => f.path);
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each sortedVisibleColumns as column (column.join('.'))}
    <RowItemValue {row} path={column} {schema} />
  {/each}
</div>
