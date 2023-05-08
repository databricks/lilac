<script lang="ts">
  import { useGetManifestQuery, useGetSchemaQuery } from '$lib/store/apiDataset';
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();
  const schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);
  const manifest = useGetManifestQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: console.log({ schema: $schema.data, manifest: $manifest.data });
</script>

<div class="flex flex-col gap-y-4 px-4 py-4">
  {#if $schema.isLoading}
    Loading...
  {:else if $schema.isSuccess && $manifest.isSuccess && $schema.data.fields}
    <h2 class="text-lg">
      {$datasetViewStore.namespace}/{$datasetViewStore.datasetName} ({$manifest.data.dataset_manifest.num_items.toLocaleString()}
      rows)
    </h2>
    <div>
      {#each Object.keys($schema.data.fields) as key}
        <SchemaField schema={$schema.data} field={$schema.data.fields[key]} />
      {/each}
    </div>
  {/if}
</div>
