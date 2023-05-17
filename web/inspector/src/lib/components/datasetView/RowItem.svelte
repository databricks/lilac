<script lang="ts">
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {LilacSchema, LilacValueNode, Path} from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;

  let datasetViewStore = getDatasetViewContext();

  let sortedVisibleColumns: Path[] = [];
  $: {
    sortedVisibleColumns = [...$datasetViewStore.visibleColumns];
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 pb-4">
  {#each sortedVisibleColumns as column (column.join('.'))}
    <RowItemValue {row} path={column} visibleColumns={$datasetViewStore.visibleColumns} {schema} />
  {/each}
</div>
