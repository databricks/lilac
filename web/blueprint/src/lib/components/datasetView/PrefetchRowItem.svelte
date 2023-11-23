<!-- Prefetches the row item -->
<script lang="ts">
  import {queryRowMetadata, querySelectRowsSchema} from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';

  export let rowId: string | null;

  const datasetViewStore = getDatasetViewContext();
  $: namespace = $datasetViewStore.namespace;
  $: datasetName = $datasetViewStore.datasetName;
  $: selectOptions = getSelectRowsOptions($datasetViewStore);
  $: selectRowsSchema = querySelectRowsSchema(
    namespace,
    datasetName,
    getSelectRowsSchemaOptions($datasetViewStore)
  );
  $: rowQuery =
    !$selectRowsSchema.isFetching &&
    $selectRowsSchema?.data?.schema != null &&
    selectOptions != null &&
    rowId != null
      ? queryRowMetadata(
          namespace,
          datasetName,
          rowId,
          selectOptions,
          $selectRowsSchema.data.schema
        )
      : null;
</script>

{#if $rowQuery?.data != null}
  <div class="hidden" />
{/if}
