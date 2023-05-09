<script lang="ts">
  import {useGetSchemaQuery, useSelectRowsInfiniteQuery} from '$lib/store/apiDataset';
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {SkeletonText} from 'carbon-components-svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: rows = useSelectRowsInfiniteQuery(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    {
      limit: 40,
      filters: $datasetViewStore.filters,
      sort_by: $datasetViewStore.sortBy
    },
    $schema.isSuccess ? $schema.data : undefined
  );
</script>

{#if $rows?.isLoading || $schema.isLoading}
  <SkeletonText paragraph lines={3} />
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
