<script lang="ts">
  import {queryManyDatasetStats} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath} from '$lib/view_utils';
  import {childFields, isNumeric, serializePath, type Path, type StatsResult} from '$lilac';
  import {Dropdown, DropdownSkeleton} from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {CicsSystemGroup} from 'carbon-icons-svelte';
  import {hoverTooltip} from '../common/HoverTooltip';

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();
  let open = false;
  const NONE_ID = '__none__';
  $: selectedId = $datasetViewStore.groupBy
    ? serializePath($datasetViewStore.groupBy.path)
    : NONE_ID;
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
  $: stats = categoricalFields
    ? queryManyDatasetStats(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        categoricalFields.map(f => f.path)
      )
    : null;

  interface GroupByItem extends DropdownItem {
    stats: StatsResult;
  }

  function shortPath(path: Path): string {
    if (path.length <= 2) {
      return displayPath(path);
    }
    return displayPath([path[0], '...', path[path.length - 1]]);
  }

  function makeItems(stats: StatsResult[], open: boolean): GroupByItem[] {
    const items = stats
      .filter(s => s.total_count > 0)
      .map(s => ({
        id: serializePath(s.path),
        text: open ? displayPath(s.path) : shortPath(s.path),
        stats: s
      }));
    return [{id: NONE_ID, text: open ? 'None' : 'Group by', stats: null!}, ...items];
  }
  $: items = $stats?.data ? makeItems($stats.data, open) : null;

  function selectItem(
    e: CustomEvent<{
      selectedId: DropdownItemId;
      selectedItem: DropdownItem;
    }>
  ) {
    if (e.detail.selectedId === NONE_ID) {
      datasetViewStore.setGroupBy(null, null);
      return;
    }
    const groupByItem = e.detail.selectedItem as GroupByItem;
    datasetViewStore.setGroupBy(groupByItem.stats.path, null);
    selectedId = e.detail.selectedId;
  }
</script>

<div
  class="groupby-dropdown flex items-center gap-x-1 px-2"
  class:active={selectedId !== NONE_ID}
  use:hoverTooltip={selectedPath && !open
    ? {text: `Grouping by ${displayPath(selectedPath)}`}
    : {text: ''}}
>
  {#if items}
    <CicsSystemGroup title={'Group by'} />
    <Dropdown
      bind:open
      size="sm"
      type="inline"
      {selectedId}
      {items}
      let:item
      on:select={selectItem}
    >
      {@const groupByItem = items.find(x => x === item)}
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
    </Dropdown>
  {:else}
    <DropdownSkeleton inline />
  {/if}
</div>

<style lang="postcss">
  .active {
    @apply rounded-lg bg-neutral-100 outline outline-1 outline-neutral-400;
  }
  :global(.groupby-dropdown .bx--list-box__menu) {
    max-height: 26rem !important;
    width: unset;
    right: unset;
  }
  :global(.groupby-dropdown .bx--dropdown) {
    @apply !max-w-xs;
  }
  :global(.groupby-dropdown .bx--dropdown__wrapper--inline) {
    @apply !gap-0;
  }
  :global(.groupby-dropdown .bx--list-box__menu-item__option) {
    @apply pr-0;
  }
</style>
