<script lang="ts">
  import {
    infiniteQuerySelectRows,
    queryDatasetManifest,
    queryDatasetSchema
  } from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext, getSelectRowsOptions} from '$lib/stores/datasetViewStore';
  import {ITEM_SCROLL_CONTAINER_CTX_KEY, getMediaFields, getVisibleSchema} from '$lib/view_utils';
  import {L, UUID_COLUMN, serializePath} from '$lilac';
  import {InlineNotification, SkeletonText} from 'carbon-components-svelte';
  import {setContext} from 'svelte';
  import InfiniteScroll from 'svelte-infinite-scroll';
  import {writable} from 'svelte/store';
  import FilterPanel from './FilterPanel.svelte';
  import RowItem from './RowItem.svelte';

  let datasetViewStore = getDatasetViewContext();
  let datasetStore = getDatasetContext();

  const manifest = queryDatasetManifest($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: schema = queryDatasetSchema($datasetViewStore.namespace, $datasetViewStore.datasetName);

  $: selectOptions = $schema.isSuccess ? getSelectRowsOptions($datasetViewStore) : undefined;

  $: selectRowsSchema = $datasetStore.selectRowsSchema;

  $: rows = infiniteQuerySelectRows(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    selectOptions || {},
    selectRowsSchema?.isSuccess ? selectRowsSchema.data.schema : undefined
  );

  $: totalNumRows = $rows.data?.pages[0].total_num_rows;

  $: items = $rows.data?.pages.flatMap(x => x.rows);

  $: visibleFields = ($datasetStore.visibleFields || []).sort((a, b) =>
    serializePath(a.path) > serializePath(b.path) ? 1 : -1
  );
  $: visibleSchema =
    selectRowsSchema?.data?.schema != null
      ? getVisibleSchema(selectRowsSchema?.data?.schema, visibleFields)!
      : null;
  $: mediaFields = getMediaFields(visibleSchema, $datasetStore.settings);

  // Pass the item scroll container to children so they can handle scroll events.
  let itemScrollContainer: HTMLDivElement | null = null;
  const writableStore = writable<HTMLDivElement | null>(itemScrollContainer);
  $: setContext(ITEM_SCROLL_CONTAINER_CTX_KEY, writableStore);
  $: writableStore.set(itemScrollContainer);
</script>

<FilterPanel {totalNumRows} manifest={$manifest.data} />

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
{:else if visibleFields.length === 0}
  <div class="mt-12 w-full text-center text-gray-600">Select fields to display</div>
{:else if $rows?.isSuccess && items && items.length === 0}
  <div class="mx-4 mt-8 w-full text-gray-600">No results.</div>
{/if}

{#if items && visibleFields.length > 0 && $schema.isSuccess && mediaFields != null}
  <div class="flex h-full w-full flex-col overflow-y-scroll" bind:this={itemScrollContainer}>
    {#each items as row (L.value(row[UUID_COLUMN]))}
      <RowItem {visibleFields} {row} {mediaFields} />
    {/each}
    {#if items.length > 0}
      <InfiniteScroll threshold={100} on:loadMore={() => $rows?.fetchNextPage()} />
    {/if}
  </div>
{/if}
