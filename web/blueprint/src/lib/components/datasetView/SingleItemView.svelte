<script lang="ts">
  import {
    queryDatasetManifest,
    querySelectRows,
    querySelectRowsSchema,
    querySettings
  } from '$lib/queries/datasetQueries';
  import {
    getDatasetViewContext,
    getSelectRowsOptions,
    getSelectRowsSchemaOptions
  } from '$lib/stores/datasetViewStore';
  import {getHighlightedFields, getMediaFields} from '$lib/view_utils';
  import {L, ROWID, formatValue} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight} from 'carbon-icons-svelte';
  import FilterPanel from './FilterPanel.svelte';
  import RowItem from './RowItem.svelte';

  const store = getDatasetViewContext();
  const DEFAULT_LIMIT_SELECT_ROW_IDS = 100;

  let limit = DEFAULT_LIMIT_SELECT_ROW_IDS;
  let index: number | undefined = undefined;

  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );
  $: selectOptions = getSelectRowsOptions($store, true /* implicitSortByRowID */);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID], limit},
    $selectRowsSchema.data?.schema
  );

  $: manifest = queryDatasetManifest($store.namespace, $store.datasetName);

  // Reset the index to 0 if the row id is not set.
  $: index = $store.rowId === undefined ? 0 : index;

  // Find the index if the row id is known.
  $: findIndexFromRowId = $store.rowId != null && $rowsQuery?.data?.rows != null;
  $: index = findIndexFromRowId
    ? $rowsQuery?.data?.rows.findIndex(row => L.value(row[ROWID], 'string') === $store.rowId)
    : index;

  // Set the row id if the index is known.
  $: setRowIdFromIndex =
    $store.rowId == null &&
    $rowsQuery?.data?.rows != null &&
    $rowsQuery.isFetched &&
    index != null &&
    index >= 0 &&
    index < $rowsQuery?.data?.rows.length;
  $: setRowIdFromIndex && store.setRowId(L.value($rowsQuery?.data?.rows[index!][ROWID], 'string')!);

  // Double the limit of select rows if the row id was not found.
  $: rowIdWasNotFound =
    index != null && (index === -1 || index >= ($rowsQuery?.data?.rows?.length || 0));
  $: limit =
    rowIdWasNotFound && $rowsQuery?.data?.total_num_rows
      ? Math.min(limit * 2, $rowsQuery.data.total_num_rows)
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
    // Unset the row id and set the new index.
    store.setRowId(null);
    index = next ? index + 1 : Math.max(index - 1, 0);
  }
</script>

<FilterPanel totalNumRows={$rowsQuery?.data?.total_num_rows} manifest={$manifest.data} />

<div
  class="mx-5 my-2 flex items-center justify-between rounded-lg border border-neutral-300 bg-neutral-100 py-2"
>
  <div class="flex-0">
    {#if $store.rowId != null && index != null && index > 0}
      <button on:click={() => updateRowId(false)}>
        <ChevronLeft title="Previous item" size={24} />
      </button>
    {/if}
  </div>

  <div class="flex-col items-center justify-items-center">
    <div class="min-w-0 max-w-lg truncate text-center text-lg">
      Item
      <span class="inline-flex">
        {#if index != null && index >= 0}
          {index + 1}
        {:else}
          <SkeletonText lines={1} class="!w-10" />
        {/if}
      </span>
      of
      <span class="inline-flex">
        {#if $rowsQuery?.data?.total_num_rows != null}
          {formatValue($rowsQuery?.data?.total_num_rows)}
        {:else}
          <SkeletonText lines={1} class="!w-20" />
        {/if}
      </span>
    </div>
  </div>
  <div class="flex-0">
    {#if index != null && index < ($rowsQuery?.data?.total_num_rows || 0) - 1}
      <button on:click={() => updateRowId(true)}>
        <ChevronRight title="Next item" size={24} />
      </button>
    {/if}
  </div>
</div>

{#if $store.rowId != null}
  <div class="flex h-full w-full flex-col overflow-y-scroll px-5 pb-32">
    <RowItem alwaysExpand={true} rowId={$store.rowId} {mediaFields} {highlightedFields} />
  </div>
{/if}

<style lang="postcss">
</style>
