<script lang="ts">
  import {queryBatchStats} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath, shortPath} from '$lib/view_utils';
  import {childFields, isNumeric, serializePath, type StatsResult} from '$lilac';
  import type {QueryObserverResult} from '@tanstack/svelte-query';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {Folder} from 'carbon-icons-svelte';
  import DropdownPill from '../common/DropdownPill.svelte';

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();
  let open = false;
  $: selectedId = $datasetViewStore.groupBy ? serializePath($datasetViewStore.groupBy.path) : null;
  $: selectedPath = $datasetViewStore.groupBy?.path;
  $: schema = $datasetStore.schema;
  $: categoricalFields = schema
    ? childFields(schema).filter(
        f =>
          (f.categorical || !isNumeric(f.dtype!)) &&
          f.dtype != null &&
          f.dtype !== 'string_span' &&
          f.dtype !== 'embedding'
      )
    : null;

  $: manyStats = queryBatchStats(
    $datasetViewStore.namespace,
    $datasetViewStore.datasetName,
    categoricalFields?.map(f => f.path),
    categoricalFields != null /* enabled */
  );

  interface GroupByItem extends DropdownItem {
    stats: StatsResult;
  }

  function makeItems(
    stats: QueryObserverResult<StatsResult, unknown>[],
    open: boolean
  ): GroupByItem[] {
    return stats
      .filter(s => s.data != null && s.data.total_count > 0)
      .map(s => s.data!)
      .map(s => ({
        id: serializePath(s.path),
        text: open ? displayPath(s.path) : shortPath(s.path),
        stats: s
      }));
  }
  $: items = makeItems($manyStats, open);

  function selectItem(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    if (e.detail.selectedId == null) {
      datasetViewStore.setGroupBy(null, null);
      return;
    }
    const groupByItem = e.detail.selectedItem as GroupByItem;
    datasetViewStore.setGroupBy(groupByItem.stats.path, null);
    selectedId = e.detail.selectedId;
  }
</script>

<DropdownPill
  title="Group by"
  {items}
  bind:open
  on:select={selectItem}
  {selectedId}
  tooltip={selectedPath ? `Grouping by ${displayPath(selectedPath)}` : null}
  let:item
>
  <div slot="icon"><Folder title="Group by" /></div>
  {@const groupByItem = items?.find(x => x === item)}
  {#if groupByItem}
    <div class="flex items-center justify-between gap-x-1">
      <span title={groupByItem.text} class="truncate text-sm">{groupByItem.text}</span>
      {#if groupByItem.stats}
        {@const count = groupByItem.stats.approx_count_distinct}
        <span class="text-xs text-gray-800">
          ~{count.toLocaleString()} group{count === 1 ? '' : 's'}
        </span>
      {/if}
    </div>
  {/if}
</DropdownPill>
