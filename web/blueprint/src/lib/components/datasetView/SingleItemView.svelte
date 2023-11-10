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
  $: rowId = $store.rowId;

  $: manifest = queryDatasetManifest($store.namespace, $store.datasetName);
  $: selectRowsSchema = querySelectRowsSchema(
    $store.namespace,
    $store.datasetName,
    getSelectRowsSchemaOptions($store)
  );

  $: selectOptions = getSelectRowsOptions($store, true /* implicitSortByRowID */);
  $: rowsQuery = querySelectRows(
    $store.namespace,
    $store.datasetName,
    {...selectOptions, columns: [ROWID]},
    $selectRowsSchema?.isSuccess ? $selectRowsSchema.data.schema : undefined
  );
  $: totalNumRows = $rowsQuery.data?.total_num_rows;
  $: rows = $rowsQuery.data?.rows;

  $: {
    if (rowId == null && rows != null && rows.length > 0) {
      // Choose the first row id automatically.
      rowId = L.value(rows[0][ROWID], 'string')!;
      store.setRowId(rowId);
    }
  }

  $: settings = querySettings($store.namespace, $store.datasetName);
  $: mediaFields = $settings.data
    ? getMediaFields($selectRowsSchema?.data?.schema, $settings.data)
    : [];
  $: highlightedFields = getHighlightedFields($store.query, $selectRowsSchema?.data);

  function updateRowId(next: boolean) {
    console.log('update row id', next);
  }
</script>

<FilterPanel {totalNumRows} manifest={$manifest.data} />

<div
  class="mx-5 my-2 flex items-center justify-between rounded-lg border border-neutral-300 bg-neutral-100 py-2"
>
  <div class="flex-0">
    {#if rowId != null}
      <button on:click={() => updateRowId(false)}>
        <ChevronLeft title="Previous item" size={24} />
      </button>
    {/if}
  </div>

  <div class="flex-col items-center justify-items-center">
    <div class="min-w-0 max-w-lg truncate text-center text-lg">
      {#if rowId != null}
        {formatValue(rowId)}
      {:else}
        <SkeletonText class="!w-40" />
      {/if}
    </div>
  </div>
  <div class="flex-0">
    {#if rowId != null}
      <button on:click={() => updateRowId(true)}>
        <ChevronRight title="Next item" size={24} />
      </button>
    {/if}
  </div>
</div>

{#if rowId != null}
  <div class="flex h-full w-full flex-col overflow-y-scroll px-5 pb-32">
    <RowItem alwaysExpand={true} {rowId} {mediaFields} {highlightedFields} />
  </div>
{/if}

<style lang="postcss">
</style>
