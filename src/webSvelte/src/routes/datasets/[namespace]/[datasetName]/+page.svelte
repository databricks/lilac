<script lang="ts">
  import { page } from '$app/stores';
  import Spinner from '$lib/components/Spinner.svelte';
  import RowView from '$lib/components/datasetView/RowView.svelte';
  import SchemaView from '$lib/components/schemaView/SchemaView.svelte';
  import { useGetManifestQuery } from '$lib/store/apiDataset';
  import { createDatasetViewStore, setDatasetViewContext } from '$lib/store/datasetViewStore';

  $: namespace = $page.params.namespace;
  $: datasetName = $page.params.datasetName;

  $: manifest = useGetManifestQuery(namespace, datasetName);

  $: setDatasetViewContext(createDatasetViewStore(namespace, datasetName));
</script>

<div class="flex h-full w-full">
  <div class=" h-full w-1/2 border-r border-solid border-gray-200">
    <SchemaView />
  </div>
  <div class="h-full w-1/2 p-4">
    {#if $manifest.isLoading}
      <Spinner />
    {:else}
      <RowView />
    {/if}
  </div>
</div>
