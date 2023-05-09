<script lang="ts">
  import {useGetSchemaQuery, useSelectRowsInfiniteQuery} from '$lib/store/apiDataset';
  import {getDatasetViewContext} from '$lib/store/datasetViewStore';
  import {LILAC_COLUMN, listFields} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = useGetSchemaQuery($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: columns = $schema.isSuccess
    ? [
        ...listFields($schema.data)
          .map(f => f.path)
          .filter(p => p[0] !== LILAC_COLUMN),
        // Add one entry for all lilac columns
        [LILAC_COLUMN],
        ...$datasetViewStore.extraColumns
      ]
    : [];

  $: rows = useSelectRowsInfiniteQuery(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    {
      limit: 40,
      filters: $datasetViewStore.filters,
      sort_by: $datasetViewStore.sortBy,
      columns,
      combine_columns: true
    },
    $schema.isSuccess ? $schema.data : undefined
  );
</script>

{#if $rows?.isLoading || $schema.isLoading}
  <SkeletonText paragraph lines={3} />
{:else if $datasetViewStore.visibleColumns.length === 0}
  <div class="mt-12 w-full text-center text-gray-600">Select fields to display</div>
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
