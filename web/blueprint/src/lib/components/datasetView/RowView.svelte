<script lang="ts">
  import {
    infiniteQuerySelectRows,
    queryDatasetSchema,
    querySelectRowsAliasUdfPaths,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {getVisibleFields} from '$lib/view_utils';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import FilterPanel from './FilterPanel.svelte';
  import RowItem from './RowItem.svelte';
  import SearchPanel from './SearchPanel.svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess ? getSelectRowsOptions($datasetViewStore) : undefined;

  $: selectRowsSchema = selectOptions
    ? querySelectRowsSchema(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;

  $: selectRowsAliasPaths = selectOptions
    ? querySelectRowsAliasUdfPaths(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        selectOptions
      )
    : undefined;

  $: rows = infiniteQuerySelectRows(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    selectOptions || {},
    $selectRowsSchema?.isSuccess ? $selectRowsSchema.data.schema : undefined
  );

  $: visibleFields = getVisibleFields(
    $datasetViewStore,
    $datasetStore,
    $selectRowsSchema?.data?.schema
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
{:else if $selectRowsSchema?.isError}
  <InlineNotification
    lowContrast
    title="Could not fetch schema:"
    subtitle={$selectRowsSchema.error.body?.detail || $selectRowsSchema.error.message}
  />
{:else if $rows?.isLoading || $schema.isLoading || $selectRowsSchema?.isLoading}
  <SkeletonText paragraph lines={3} />
{:else if visibleFields.length === 0}
  <div class="mt-12 w-full text-center text-gray-600">Select fields to display</div>
{:else if $rows?.isSuccess && $rows.data.pages.length === 1 && $rows.data.pages[0].length === 0}
  <div class="mx-4 mt-8 w-full text-gray-600">No results.</div>
{:else if $rows?.isSuccess && $rows.data.pages.length && $selectRowsSchema?.isSuccess && $schema.isSuccess && $selectRowsAliasPaths?.isSuccess}
  <div class="flex h-full w-full flex-col overflow-scroll">
    {#each $rows.data.pages as page}
      {#each page as row}
        <RowItem {row} schema={$schema.data} {visibleFields} />
      {/each}
    {/each}
    <InfiniteScroll threshold={100} on:loadMore={() => $rows?.fetchNextPage()} />
  </div>
{/if}
