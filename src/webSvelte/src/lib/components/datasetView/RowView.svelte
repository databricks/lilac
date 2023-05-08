<script lang="ts">
  import { useGetSchemaQuery, useSelectRowsInfiniteQuery } from '$lib/store/apiDataset';
  import { getDatasetViewContext } from '$lib/store/datasetViewStore';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import Spinner from '../Spinner.svelte';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: rows = $schema.isSuccess
    ? useSelectRowsInfiniteQuery(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        {
          limit: 40
        },
        $schema.data
      )
    : undefined;
</script>

{#if $rows?.isLoading || $schema.isLoading}
  <Spinner />
{:else if $rows?.isSuccess && $rows.data.pages.length && $schema.isSuccess && $schema.isSuccess}
  <div class="flex h-full w-full flex-col overflow-scroll">
    {#each $rows.data.pages as page}
      {#each page as row}
        <RowItem {row} />
      {/each}
    {/each}
    <InfiniteScroll threshold={100} on:loadMore={() => $rows?.fetchNextPage()} />
  </div>
{/if}
