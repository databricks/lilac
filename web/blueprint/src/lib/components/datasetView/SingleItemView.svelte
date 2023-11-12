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

  let index: number | undefined = undefined;
  let limit = 5;
  $: console.log('rowId', $store.rowId, 'index', index);

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

  // Set the index to 0 if both the row id and index are not set.
  $: {
    if ($store.rowId === undefined) {
      console.log('setting index to 0');
      index = 0;
    }
  }

  // Find the index if the row id is set.
  $: {
    if (index == null && $store.rowId != null && $rowsQuery?.data?.rows != null) {
      console.log('row id is set, finding index');
      index = $rowsQuery?.data?.rows.findIndex(
        row => L.value(row[ROWID], 'string') === $store.rowId
      );
    }
  }

  // Find the row id if the index is set.
  $: {
    if (
      $store.rowId == null &&
      $rowsQuery?.data?.rows != null &&
      $rowsQuery.isFetched &&
      index != null &&
      index >= 0 &&
      index < $rowsQuery?.data?.rows.length
    ) {
      console.log('Index is set to', index, '. Finding row id');
      const newRowId = L.value($rowsQuery?.data?.rows[index][ROWID], 'string')!;
      store.setRowId(newRowId);
    }
  }

  // Double the limit of select rows if the row id index is not yet found.
  $: {
    if (
      $rowsQuery?.data?.rows != null &&
      index != null &&
      (index === -1 || index >= $rowsQuery?.data?.rows.length) &&
      $rowsQuery?.data?.total_num_rows &&
      limit < $rowsQuery?.data?.total_num_rows
    ) {
      if (index === -1) {
        index = undefined;
        console.log('Index was not found, doubling limit');
      } else if (index >= $rowsQuery?.data?.rows.length) {
        console.log('Index was out of bounds, doubling limit');
      }
      limit = limit * 2;
    }
  }

  $: settings = querySettings($store.namespace, $store.datasetName);
  $: mediaFields = $settings.data
    ? getMediaFields($selectRowsSchema?.data?.schema, $settings.data)
    : [];
  $: highlightedFields = getHighlightedFields($store.query, $selectRowsSchema?.data);

  function updateRowId(next: boolean) {
    if ($rowsQuery?.data?.rows == null || index == null || index < 0) {
      return;
    }
    let newIndex = next ? index + 1 : index - 1;
    // Unset the row id and set the new index.
    store.setRowId(null);
    index = Math.max(newIndex, 0);
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
          {index}
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
    {#if $store.rowId != null}
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
