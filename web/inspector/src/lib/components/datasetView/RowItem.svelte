<script lang="ts">
  import {querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    isPathVisible
  } from '$lib/stores/datasetViewStore';
  import {listFields, type LilacSchema, type LilacValueNode, type Path} from '$lilac';
  import RowItemValue from './RowItemValue.svelte';

  export let row: LilacValueNode;
  export let schema: LilacSchema;
  export let aliasMapping: Record<string, Path> | undefined;

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
  let searchResultsPaths: Path[] = [];

  $: {
    let allFields = $selectRowsSchema?.isSuccess ? listFields($selectRowsSchema.data.schema) : [];
    sortedVisibleColumns = allFields
      .filter(f => isPathVisible($datasetViewStore.visibleColumns, f.path, aliasMapping))
      .map(f => f.path);
    sortedVisibleColumns.sort((a, b) => (a.join('.') > b.join('.') ? 1 : -1));

    searchResultsPaths = $selectRowsSchema?.isSuccess
      ? $selectRowsSchema.data.searchResultsPaths
      : [];
  }
</script>

<div class="mb-4 flex flex-col gap-y-4 border-b border-gray-300 p-4">
  {#each sortedVisibleColumns as column (column.join('.'))}
    <RowItemValue
      {row}
      path={column}
      visibleColumns={$datasetViewStore.visibleColumns}
      {searchResultsPaths}
      {schema}
      {aliasMapping}
    />
  {/each}
</div>
