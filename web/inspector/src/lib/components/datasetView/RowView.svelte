<script lang="ts">
  import {
    infiniteQuerySelectRows,
    queryDatasetSchema,
    querySelectRowsAliasUdfPaths,
    querySelectRowsSchema
  } from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess
    ? getSelectRowsOptions($datasetViewStore, $schema.data)
    : undefined;

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
    {
      limit: 40,
      ...selectOptions
    },
    $selectRowsSchema?.isSuccess ? $selectRowsSchema.data : undefined
  );
</script>

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
{:else if $datasetViewStore.visibleColumns.length === 0}
  <div class="mt-12 w-full text-center text-gray-600">Select fields to display</div>
{:else if $rows?.isSuccess && $rows.data.pages.length && $selectRowsSchema?.isSuccess && $schema.isSuccess && $selectRowsAliasPaths?.isSuccess}
  <div class="flex h-full w-full flex-col overflow-scroll">
    {#each $rows.data.pages as page}
      {#each page as row}
        <RowItem {row} schema={$schema.data} aliasMapping={$selectRowsAliasPaths.data} />
      {/each}
    {/each}
    <InfiniteScroll threshold={100} on:loadMore={() => $rows?.fetchNextPage()} />
  </div>
{/if}
