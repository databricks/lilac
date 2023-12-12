<script lang="ts">
  import {
    queryDatasetManifest,
    querySelectRowsSchema,
    querySettings
  } from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, getSelectRowsSchemaOptions} from '$lib/stores/datasetViewStore';
  import {getHighlightedFields, getMediaFields} from '$lib/view_utils';
  import {L, ROWID, formatValue, type SelectRowsResponse} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight} from 'carbon-icons-svelte';
  import FilterPanel from './FilterPanel.svelte';
  import PrefetchRowItem from './PrefetchRowItem.svelte';
  import RowItem from './RowItem.svelte';
  import SingleItemSelectRows from './SingleItemSelectRows.svelte';

  const store = getDatasetViewContext();
  const DEFAULT_LIMIT_SELECT_ROW_IDS = 5;

  let limit = DEFAULT_LIMIT_SELECT_ROW_IDS;
  let rowsResponse: SelectRowsResponse | undefined;
  let nextRowsResponse: SelectRowsResponse | undefined;

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: rows = rowsResponse?.rows;

  $: manifest = queryDatasetManifest($store.namespace, $store.datasetName);
  $: firstRowId = rows && rows.length > 0 ? L.value(rows[0][ROWID], 'string') : undefined;
  $: rowId = $store.rowId || firstRowId;

  // Find the index if the row id is known.
  $: index =
    rowId != null && rows != null
      ? rows.findIndex(row => L.value(row[ROWID], 'string') === rowId)
      : undefined;

  // Double the limit of select rows if the row id was not found.
  $: rowIdWasNotFound = rows != null && index != null && (index === -1 || index >= rows.length);
  $: limit =
    rowIdWasNotFound && rowsResponse?.total_num_rows
      ? Math.min(limit * 2, rowsResponse.total_num_rows)
      : limit;

  $: settings = querySettings($store.namespace, $store.datasetName);
  $: mediaFields = $settings.data
    ? getMediaFields($selectRowsSchema?.data?.schema, $settings.data)
    : [];
  $: highlightedFields = getHighlightedFields($store.query, $selectRowsSchema?.data);

  function updateRowId(next: boolean) {
    if (index == null) {
      return;
    }
    const newIndex = next ? index + 1 : Math.max(index - 1, 0);
    const newRowId = L.value(nextRowsResponse?.rows[newIndex][ROWID], 'string');
    if (newRowId != null) {
      store.setRowId(newRowId);
      return;
    }
  }

  function onKeyDown(key: KeyboardEvent) {
    if (key.code === 'ArrowLeft') {
      updateRowId(false);
    } else if (key.code === 'ArrowRight') {
      updateRowId(true);
    }
  }
</script>

<FilterPanel totalNumRows={rowsResponse?.total_num_rows} manifest={$manifest.data} />

<div
  class="mx-5 my-2 flex items-center justify-between rounded-lg border border-neutral-300 bg-neutral-100 py-2"
>
  {#if rows?.length === 0}
    <div class="w-full text-center">No results found</div>
  {:else}
    <div class="flex-0">
      {#if rowId != null && index != null && index > 0}
        <button on:click={() => updateRowId(false)}>
          <ChevronLeft title="Previous item" size={24} />
        </button>
      {/if}
    </div>

    <div class="flex-col items-center justify-items-center">
      <div class="min-w-0 max-w-lg truncate text-center text-lg">
        <span class="inline-flex">
          {#if index != null && index >= 0}
            {index + 1}
          {:else}
            <SkeletonText lines={1} class="!w-10" />
          {/if}
        </span>
        of
        <span class="inline-flex">
          {#if rowsResponse?.total_num_rows != null}
            {formatValue(rowsResponse?.total_num_rows)}
          {:else}
            <SkeletonText lines={1} class="!w-20" />
          {/if}
        </span>
      </div>
    </div>
    <div class="flex-0">
      {#if index != null && index < (rowsResponse?.total_num_rows || 0) - 1}
        <button on:click={() => updateRowId(true)}>
          <ChevronRight title="Next item" size={24} />
        </button>
      {/if}
    </div>
  {/if}
</div>

<SingleItemSelectRows {limit} bind:rowsResponse />
<SingleItemSelectRows limit={limit * 2} bind:rowsResponse={nextRowsResponse} />

{#each rows || [] as row}
  {@const rowId = L.value(row[ROWID], 'string')}
  <PrefetchRowItem {rowId} />
{/each}

{#if rowId != null}
  <div class="flex h-full w-full flex-col overflow-y-scroll pb-32 pl-5 pr-2">
    <RowItem {rowId} {mediaFields} {highlightedFields} />
  </div>
{/if}

<svelte:window on:keydown={onKeyDown} />
