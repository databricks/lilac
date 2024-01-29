<!-- Prefetches the row item -->
<script lang="ts">
  import {
    queryDatasetSchema,
    queryRowMetadata,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';

  export let rowId: string | null;

  const datasetViewStore = getDatasetViewContext();
  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;
  $: selectRowsSchema = querySelectRowsSchema(
    namespace,
    datasetName,
    getSelectRowsSchemaOptions($datasetViewStore, $schema.data)
  );
  $: selectOptions = getSelectRowsOptions($datasetViewStore, $selectRowsSchema.data?.schema);
  $: readyToQueryRow =
    !$selectRowsSchema.isFetching &&
    $selectRowsSchema?.data?.schema != null &&
    selectOptions != null &&
    rowId != null;
  $: rowQuery = queryRowMetadata(
    namespace,
    datasetName,
    rowId,
    selectOptions,
    $selectRowsSchema.data?.schema,
    readyToQueryRow
  );
</script>

{#if $rowQuery?.data != null}
  <div class="hidden" />
{/if}
