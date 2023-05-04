<script lang="ts">
  import { LILAC_COLUMN, Schema } from '$lib/schema';
  import { useGetManifestQuery } from '$lib/store/apiDataset';
  import SchemaField from './SchemaField.svelte';

  export let namespace: string;
  export let datasetName: string;

  $: schema = $manifest.isSuccess
    ? new Schema($manifest.data?.dataset_manifest.data_schema)
    : undefined;
  $: fields = schema?.fields;

  const manifest = useGetManifestQuery(namespace, datasetName);

  $: console.log({ manifest: $manifest.data });
</script>

<div class="flex flex-col gap-y-4 px-4 py-4">
  {#if $manifest.isLoading}
    Loading...
  {:else if $manifest.isSuccess && fields && schema}
    <h2 class="text-lg">
      {namespace}/{datasetName} ({$manifest.data.dataset_manifest.num_items.toLocaleString()} rows)
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
