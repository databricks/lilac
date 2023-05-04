<script lang="ts">
  import { useGetManifestQuery, useSelectRowsInfiniteQuery } from '$lib/store/apiDataset';
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import { LilacSchema } from '$lilac/schema';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import Spinner from '../Spinner.svelte';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: manifest = useGetManifestQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);
  $: schema = $manifest.data
    ? new LilacSchema($manifest.data.dataset_manifest.data_schema)
    : undefined;

  $: rows = useSelectRowsInfiniteQuery($datasetViewStore.namespace, $datasetViewStore.datasetName, {
    limit: 40
  });
</script>

{#if $rows.isLoading || $manifest.isLoading}
  <Spinner />
{:else if $rows.isSuccess && $rows.data.pages.length && $manifest.isSuccess && schema}
  <div class="flex h-full w-full flex-col overflow-scroll">
    {#each $rows.data.pages as page}
      {#each page as row}
        <RowItem item={row} {schema} />
      {/each}
    {/each}
    <InfiniteScroll threshold={100} on:loadMore={() => $rows.fetchNextPage()} />
  </div>
{/if}
