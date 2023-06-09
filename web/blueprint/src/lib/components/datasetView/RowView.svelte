<script lang="ts">
  import {infiniteQuerySelectRows, queryDatasetSchema} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import FilterPanel from './FilterPanel.svelte';
  import RowItem from './RowItem.svelte';
  import SearchPanel from './SearchPanel.svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess ? getSelectRowsOptions($datasetViewStore) : undefined;

  $: selectRowsSchema = $datasetStore?.selectRowsSchema;

  $: rows = infiniteQuerySelectRows(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    selectOptions || {},
    selectRowsSchema?.isSuccess ? selectRowsSchema.data.schema : undefined
  );
</script>

<SearchPanel />
<FilterPanel />

{#if $rows.isError}
  <InlineNotification
    lowContrast
    title="Could not fetch rows:"
    subtitle={$rows.error.body?.detail || $rows.error.message}
  />
{:else if selectRowsSchema?.isError}
  <InlineNotification
    lowContrast
    title="Could not fetch schema:"
    subtitle={selectRowsSchema.error.body?.detail || selectRowsSchema?.error.message}
  />
{:else if $rows?.isLoading || $schema.isLoading || selectRowsSchema?.isLoading}
  <SkeletonText paragraph lines={3} />
{:else if $datasetStore?.visibleFields?.length === 0}
  <div class="mt-12 w-full text-center text-gray-600">Select fields to display</div>
{:else if $rows?.isSuccess && $rows.data.pages.length === 1 && $rows.data.pages[0].length === 0}
  <div class="mx-4 mt-8 w-full text-gray-600">No results.</div>
{:else if $rows?.isSuccess && $rows.data.pages.length && selectRowsSchema?.isSuccess && $schema.isSuccess}
  <div class="flex h-full w-full flex-col overflow-scroll">
    {#each $rows.data.pages as page}
      {#each page as row}
        <RowItem {row} schema={$schema.data} />
      {/each}
    {/each}
    <InfiniteScroll threshold={100} on:loadMore={() => $rows?.fetchNextPage()} />
  </div>
{/if}
