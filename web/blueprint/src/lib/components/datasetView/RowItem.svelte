<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {isPathVisible} from '$lib/view_utils';
  import {childFields, type LilacSchema, type LilacValueNode, type Path} from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;

  let datasetViewStore = getDatasetViewContext();
  $: selectOptions = getSelectRowsOptions($datasetViewStore);

  // Get the resulting schema including UDF columns
  $: selectRowsSchema = selectOptions
    ? querySelectRowsSchema(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;

  let sortedVisibleColumns: Path[] = [];

  const datasetStore = getDatasetContext();

  $: {
    let allFields = $selectRowsSchema?.isSuccess ? childFields($selectRowsSchema.data.schema) : [];
    sortedVisibleColumns = allFields
      .filter(f => isPathVisible($datasetViewStore, $datasetStore, f.path))
      .map(f => f.path);
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each sortedVisibleColumns as column (column.join('.'))}
    <RowItemValue {row} path={column} {schema} />
  {/each}
</div>
