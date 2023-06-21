<script lang="ts">
  import {queryDatasetStats, querySelectGroups} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import {formatValue, type LeafValue, type LilacField} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import Histogram from './Histogram.svelte';

  export let field: LilacField;

  const store = getDatasetViewContext();

  $: statsQuery = queryDatasetStats($store.namespace, $store.datasetName, {leaf_path: field.path});
  $: groupsQuery = querySelectGroups($store.namespace, $store.datasetName, {leaf_path: field.path});

  $: counts =
    $groupsQuery.data != null ? ($groupsQuery.data.counts as [LeafValue, number][]) : null;
  $: stats = $statsQuery.data != null ? $statsQuery.data : null;

  $: bins =
    $groupsQuery.data != null
      ? ($groupsQuery.data.bins as [string, number | null, number | null][])
      : null;
</script>

<div class="p-4">
  {#if $statsQuery.error}
    <p>Error: {$statsQuery.error.message}</p>
  {:else if stats == null}
    <!-- Loading... -->
    <SkeletonText paragraph width="50%" />
  {:else}
    <table class="stats-table mb-4">
      <tbody>
        <tr>
          <td>Total count</td>
          <td>{formatValue(stats.total_count)}</td>
        </tr>
        <tr>
          <td>Distinct count (approx.)</td>
          <td>{formatValue(stats.approx_count_distinct)}</td>
        </tr>
        {#if stats.avg_text_length}
          <tr>
            <td>Avg. text length</td>
            <td>{stats.avg_text_length}</td>
          </tr>
        {/if}
        {#if stats.min_val && stats.max_val}
          <tr>
            <td>Range</td>
            <td>{formatValue(stats.min_val)} .. {formatValue(stats.max_val)}</td>
          </tr>
        {/if}
      </tbody>
    </table>
  {/if}

  {#if $groupsQuery.error}
    <p>Error: {$groupsQuery.error.message}</p>
  {:else if counts == null}
    <!-- Loading... -->
    <SkeletonText paragraph width="50%" />
  {:else}
    <Histogram {counts} {bins} {field} />
  {/if}
</div>

<style lang="postcss">
  .stats-table td {
    @apply w-48;
  }
  .stats-table td:first-child {
    @apply truncate py-2 pr-2;
  }
  .stats-table td:last-child {
    @apply truncate py-2 pl-2;
  }
  .stats-table tbody {
    @apply border-y border-gray-300;
  }
</style>
