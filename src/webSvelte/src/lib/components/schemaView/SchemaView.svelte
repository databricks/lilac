<script lang="ts">
  import {useGetManifestQuery, useGetSchemaQuery, useSelectRowsSchema} from '$lib/store/apiDataset';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/store/datasetViewStore';
  import {SkeletonText} from 'carbon-components-svelte';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  const schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);
  const manifest = useGetManifestQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess
    ? getSelectRowsOptions($datasetViewStore, $schema.data)
    : undefined;

  // Get the resulting schmema including UDF columns
  $: selectRowsSchema = selectOptions
    ? useSelectRowsSchema($datasetViewStore.namespace, $datasetViewStore.datasetName, selectOptions)
    : undefined;
</script>

<div class="flex flex-col gap-y-4 px-4 py-4">
  {#if $schema.isLoading || $selectRowsSchema?.isLoading}
    <SkeletonText paragraph lines={3} />
  {:else if $schema.isSuccess && $manifest.isSuccess && $selectRowsSchema?.isSuccess && $selectRowsSchema.data.fields}
    <h2 class="text-lg">
      {$datasetViewStore.namespace}/{$datasetViewStore.datasetName} ({$manifest.data.dataset_manifest.num_items.toLocaleString()}
      rows)
    </h2>
    <div>
      {#each Object.keys($selectRowsSchema.data.fields) as key (key)}
        <SchemaField schema={$selectRowsSchema.data} field={$selectRowsSchema.data.fields[key]} />
      {/each}
    </div>
  {/if}
</div>
