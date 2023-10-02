<script lang="ts">
  import {queryManyDatasetStats} from '$lib/queries/datasetQueries';
  import {getDatasetContext} from '$lib/stores/datasetStore';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {displayPath} from '$lib/view_utils';
  import {getFieldsByDtype, serializePath, type StatsResult} from '$lilac';
  import {Dropdown, DropdownSkeleton} from 'carbon-components-svelte';
  import type {
    DropdownItem,
    DropdownItemId
  } from 'carbon-components-svelte/types/Dropdown/Dropdown.svelte';
  import {CicsSystemGroup} from 'carbon-icons-svelte';

  const datasetStore = getDatasetContext();
  const datasetViewStore = getDatasetViewContext();
  let open = false;
  const NONE_ID = '__none__';
  let selectedId = NONE_ID;

  $: schema = $datasetStore.schema;
  $: stringFields = schema ? getFieldsByDtype('string', schema) : null;
  $: stats = stringFields
    ? queryManyDatasetStats(
        $datasetViewStore.namespace,
        $datasetViewStore.datasetName,
        stringFields.map(f => f.path)
      )
    : null;

  interface GroupByItem extends DropdownItem {
    stats: StatsResult;
  }

  function makeItems(stats: StatsResult[], open: boolean): GroupByItem[] {
    const items = stats
      .filter(s => s.total_count > 0)
      .map(s => ({
        id: serializePath(s.path),
        text: displayPath(s.path),
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
    selectedId = e.detail.selectedId;
  }
</script>

<div
  class="groupby-dropdown flex items-center gap-x-1 px-2 py-1"
  class:active={selectedId !== NONE_ID}
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
            <span class="text-xs text-gray-400">
              {count.toLocaleString()} group{count === 1 ? '' : 's'}
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
</style>
