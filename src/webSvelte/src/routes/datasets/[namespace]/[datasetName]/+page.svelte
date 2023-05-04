<script lang="ts">
  import { useGetManifestQuery } from '$lib/store/apiDataset';

  $: namespace = $page.params.namespace;
  $: datasetName = $page.params.datasetName;

  $: manifset = useGetManifestQuery(namespace, datasetName);
</script>

<div class="flex h-full w-full">
  <div class=" h-full w-1/2 border-r border-solid border-gray-200">
    <SchemaView {namespace} {datasetName} />
  </div>
  <div class="h-full w-1/2 p-4">
    {#if $manifset.isLoading}
      <Spinner />
    {:else}
      <RowView {namespace} {datasetName} />
    {/if}
  </div>
</div>
