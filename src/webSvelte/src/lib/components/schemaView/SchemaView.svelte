<script lang="ts">
  import { useGetManifestQuery } from '$lib/store/apiDataset';
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import { LILAC_COLUMN, LilacSchema } from '$lilac';
  import SchemaField from './SchemaField.svelte';

  const datasetViewStore = getDatasetViewContext();

  $: schema = $manifest.isSuccess
    ? new LilacSchema($manifest.data?.dataset_manifest.data_schema)
    : undefined;
  $: fields = schema?.fields;

  const manifest = useGetManifestQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: console.log({ manifest: $manifest.data });
</script>

<div class="flex flex-col gap-y-4 px-4 py-4">
  {#if $manifest.isLoading}
    Loading...
  {:else if $manifest.isSuccess && fields && schema}
    <h2 class="text-lg">
      {$datasetViewStore.namespace}/{$datasetViewStore.datasetName} ({$manifest.data.dataset_manifest.num_items.toLocaleString()}
      rows)
    </h2>
    <div>
      {#each Object.keys(fields) as key}
        {#if key !== LILAC_COLUMN}
          <SchemaField {schema} path={[key]} annotations={fields[LILAC_COLUMN]?.fields?.[key]} />
        {/if}
      {/each}
    </div>
  {/if}
</div>
