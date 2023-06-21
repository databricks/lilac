<script lang="ts">
  import {queryDatasetStats, querySelectGroups} from '$lib/queries/datasetQueries';
  import {getDatasetViewContext} from '$lib/stores/datasetViewStore';
  import type {LeafValue, LilacField} from '$lilac';
  import {SkeletonText} from 'carbon-components-svelte';
  import Histogram from './Histogram.svelte';

  export let field: LilacField;

  const store = getDatasetViewContext();

  $: statsQuery = queryDatasetStats($store.namespace, $store.datasetName, {leaf_path: field.path});
  $: groupsQuery = querySelectGroups($store.namespace, $store.datasetName, {leaf_path: field.path});

  $: counts =
    $groupsQuery.data != null ? ($groupsQuery.data.counts as [LeafValue, number][]) : null;
  $: stats = $statsQuery.data != null ? $statsQuery.data : null;
</script>

{#if $groupsQuery.error || $statsQuery.error}
  {#if $groupsQuery.error}
    <p>Error: {$groupsQuery.error.message}</p>
  {/if}
  {#if $statsQuery.error}
    <p>Error: {$statsQuery.error.message}</p>
  {/if}
{:else if counts == null || stats == null}
  <!-- Loading... -->
  <SkeletonText paragraph width="50%" />
{:else}
  <div class="p-4">
    <table class="stats-table mb-4">
      <tbody>
        <tr>
          <td>Total count</td>
          <td>{stats.total_count.toLocaleString()}</td>
        </tr>
        <tr>
          <td>Distinct count (approx.)</td>
          <td>{stats.approx_count_distinct.toLocaleString()}</td>
        </tr>
        {#if stats.avg_text_length}
          <tr>
            <td>Avg. text length</td>
            <td>{stats.avg_text_length}</td>
          </tr>
        {/if}
        {#if stats.min_val}
          <tr>
            <td>Min. value</td>
            <td>{stats.min_val}</td>
          </tr>
        {/if}
        {#if stats.max_val}
          <tr>
            <td>Max. value</td>
            <td>{stats.max_val}</td>
          </tr>
        {/if}
      </tbody>
    </table>
    <Histogram {counts} />
  </div>
{/if}

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
