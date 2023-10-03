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
  import {ArrowLeft, ArrowRight} from 'carbon-icons-svelte';

  export let groupBy: GroupByState;
  export let schema: LilacSchema;

  let store = getDatasetViewContext();
  $: value = groupBy.value;

  $: field = getField(schema, groupBy.path)!;
  $: sortBy = isNumeric(field.dtype!) && !field.categorical ? 'value' : 'count';
  $: sortOrder = sortBy === 'value' ? 'ASC' : 'DESC';

  $: groupsQuery = querySelectGroups($store.namespace, $store.datasetName, {
    leaf_path: groupBy.path,
    sort_by: sortBy as GroupsSortBy,
    sort_order: sortOrder as SortOrder
  });
  $: allCounts = $groupsQuery.data?.counts.filter(c => c[0] != null);
  $: valueIndex = allCounts?.findIndex(c => c[0] === value);
  $: valueCount =
    valueIndex != null && valueIndex >= 0 && allCounts != null && allCounts[valueIndex] != null
      ? (allCounts[valueIndex][1] as number)
      : null;

  $: {
    if (value == null && allCounts != null && allCounts[0] != null && allCounts[0][0] != null) {
      // Choose the first value automatically.
      value = allCounts[0][0];
      store.setGroupBy(groupBy.path, value);
    }
  }

  function updateValue(next: boolean) {
    if (value == null || allCounts == null || valueIndex == null) {
      return;
    }
    const newValue = next ? allCounts[valueIndex + 1][0] : allCounts[valueIndex - 1][0];
    store.setGroupBy(groupBy.path, newValue);
  }
</script>

<div class="mx-5 my-2 flex items-center justify-between">
  <div class="flex-0">
    {#if valueIndex != null && valueIndex > 0}
      <button on:click={() => updateValue(false)}><ArrowLeft /></button>
    {/if}
  </div>

  <div class="flex overflow-x-hidden">
    <div class="flex-0"><code>{shortFieldName(groupBy.path)}</code>&nbsp;is&nbsp;</div>
    <div class="min-w-0 max-w-lg truncate">
      {#if value != null}
        "{formatValue(value)}" ({valueCount} items)
      {:else}
        <SkeletonText class="!w-40" />
      {/if}
    </div>
  </div>
  <div class="flex-0">
    {#if valueIndex != null && allCounts && valueIndex < allCounts.length - 1}
      <button on:click={() => updateValue(true)}><ArrowRight /></button>
    {/if}
  </div>
</div>
