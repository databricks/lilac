<script lang="ts">
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {isPathVisible} from '$lib/view_utils';
  import {
    childFields,
    type LilacField,
    type LilacSchema,
    type LilacValueNode,
    type Path
  } from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;
  export let visibleFields: LilacField[];

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  // Get the resulting schema including UDF columns
  $: selectRowsSchema = $datasetStore?.selectRowsSchema;

  let sortedVisibleColumns: Path[] = [];

  $: {
    let allFields = childFields(selectRowsSchema?.schema);
    sortedVisibleColumns = allFields
      .filter(f => isPathVisible($datasetViewStore, $datasetStore, f.path))
      .map(f => f.path);
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each sortedVisibleColumns as column (column.join('.'))}
    <RowItemValue {row} path={column} {schema} {visibleFields} />
  {/each}
</div>
