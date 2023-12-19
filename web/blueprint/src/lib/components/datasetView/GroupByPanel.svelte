<script lang="ts">
  import {querySelectGroups} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext, type GroupByState} from '$lib/stores/datasetViewStore';
  import {shortFieldName} from '$lib/view_utils';
  import {
    formatValue,
    getField,
    isNumeric,
    type GroupsSortBy,
    type LilacSchema,
    type SortOrder
  } from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import {ChevronLeft, ChevronRight} from 'carbon-icons-svelte';

  export let groupBy: GroupByState;
  export let schema: LilacSchema;

  let store = getDatasetViewContext();
  $: value = groupBy.value;

  $: field = getField(schema, groupBy.path)!;
  $: sortBy = isNumeric(field.dtype) && !field.categorical ? 'value' : 'count';
  $: sortOrder = sortBy === 'value' ? 'ASC' : 'DESC';

  $: groupsQuery = querySelectGroups($store.namespace, $store.datasetName, {
    leaf_path: groupBy.path,
    sort_by: sortBy as GroupsSortBy,
    sort_order: sortOrder as SortOrder,
    // Explicitly set the limit to null to get all the groups, not just the top 100.
    limit: null
  });
  $: allCounts = $groupsQuery.data?.counts.filter(c => c[0] != null);
  $: valueIndex = allCounts?.findIndex(c => c[0] === value);

  $: {
    if (value == null && allCounts != null && allCounts[0] != null && allCounts[0][0] != null) {
      // Choose the first value automatically.
      value = allCounts[0][0];
      store.setGroupBy(groupBy.path, value);
    }
  }

  function updateValue(direction: 'previous' | 'next') {
    if (value == null || allCounts == null || valueIndex == null) {
      return;
    }
    const newValue =
      direction === 'next' ? allCounts[valueIndex + 1][0] : allCounts[valueIndex - 1][0];
    store.setGroupBy(groupBy.path, newValue);
  }
  function onKeyDown(key: KeyboardEvent) {
    key.stopPropagation();
    if (key.code === 'ArrowLeft') {
      updateValue('previous');
    } else if (key.code === 'ArrowRight') {
      updateValue('next');
    }
  }

  $: leftArrowEnabled = valueIndex != null && valueIndex > 0;
  $: rightArrowEnabled = valueIndex != null && allCounts && valueIndex < allCounts.length - 1;
</script>

<!-- svelte-ignore a11y-no-noninteractive-tabindex -->
<!-- A tab index let's us arrow through the groups when the group header is focused. -->
<div
  tabindex="0"
  class="mx-4 my-2 flex items-center justify-center gap-x-2 rounded-lg border border-neutral-300 bg-neutral-100 py-2"
  on:keydown={onKeyDown}
>
  <div class="flex-0">
    <button
      on:click={() => updateValue('previous')}
      class:opacity-30={!leftArrowEnabled}
      disabled={!leftArrowEnabled}
    >
      <ChevronLeft title="Previous group" size={24} />
    </button>
  </div>

  <div class="flex-col items-center justify-items-center truncate">
    <div class="min-w-0 max-w-5xl truncate text-center text-lg">
      <code class="text-gray-600">{shortFieldName(groupBy.path)}: </code>
      {#if value != null}
        {formatValue(value)}
      {:else}
        <SkeletonText class="!w-40" />
      {/if}
    </div>
    <div class="flex-0 text-center text-gray-600">
      {#if allCounts != null && valueIndex != null}
        Group {valueIndex + 1} of {allCounts.length}
      {:else}
        <SkeletonText class="!w-40" />
      {/if}
    </div>
  </div>

  <div class="flex-0">
    <button
      on:click={() => updateValue('next')}
      class:opacity-30={!rightArrowEnabled}
      disabled={!rightArrowEnabled}
    >
      <ChevronRight title="Next group" size={24} />
    </button>
  </div>
</div>
